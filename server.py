import hmac
import os
from datetime import datetime
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Query, Security, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, model_validator

from coros_mcp.server import (
    list_activities,
    list_planned_activities,
    remove_scheduled_workout,
    schedule_workout,
)

app = FastAPI(
    title="David COROS Actions",
    description="Private API used by David's ChatGPT GPT to manage COROS workouts.",
    version="1.0.0",
    servers=[{"url": "https://coros-remote-mcp-probe.onrender.com"}],
)
bearer = HTTPBearer(auto_error=False)
MADRID = ZoneInfo("Europe/Madrid")


def require_api_key(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer)],
) -> None:
    expected = os.environ.get("ACTION_API_KEY", "")
    supplied = credentials.credentials if credentials else ""
    if not expected or not hmac.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )


Private = Annotated[None, Depends(require_api_key)]
Day = Annotated[str, Field(pattern=r"^\d{8}$", examples=["20260825"])]


class Step(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    duration_minutes: float = Field(gt=0, le=600)
    intensity_low: int = Field(ge=0, le=2500)
    intensity_high: int = Field(ge=0, le=2500)

    @model_validator(mode="after")
    def validate_range(self):
        if self.intensity_high and self.intensity_high < self.intensity_low:
            raise ValueError("intensity_high must be 0 or >= intensity_low")
        return self


class RepeatBlock(BaseModel):
    repeat: int = Field(ge=2, le=100)
    steps: list[Step] = Field(min_length=1, max_length=20)


class ScheduleWorkoutRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    happen_day: Day
    sport: Literal["indoor_cycling", "road_cycling", "running", "trail_running"]
    intensity: Literal["power", "heart_rate", "open"]
    steps: list[Step | RepeatBlock] = Field(min_length=1, max_length=40)
    confirmed: bool = Field(
        description="True only after the user reviews name, date, sport and every step."
    )


class RemoveWorkoutRequest(BaseModel):
    plan_id: str = Field(min_length=1)
    id_in_plan: str = Field(min_length=1)
    plan_program_id: str = ""
    confirmed: bool = Field(
        description="True only after the user explicitly confirms deletion."
    )


class TodayResponse(BaseModel):
    day: str
    completed: Any
    planned: Any


class CalendarResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    schedule: Any | None = None
    count: int | None = None
    date_range: str | None = None
    error: str | None = None


class ScheduleResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    scheduled: bool | None = None
    name: str | None = None
    happen_day: str | None = None
    total_minutes: float | None = None
    response: Any | None = None
    warning: str | None = None


class RemoveResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    removed: bool | None = None
    plan_id: str | None = None
    id_in_plan: str | None = None
    error: str | None = None


SPORT_IDS = {
    "indoor_cycling": 2,
    "road_cycling": 200,
    "running": 100,
    "trail_running": 102,
}
INTENSITY_IDS = {"power": 6, "heart_rate": 2, "open": 5}


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def home() -> str:
    return """<!doctype html><html lang=\"es\"><meta name=\"viewport\" content=\"width=device-width\"><title>COROS Actions</title><style>body{font:17px system-ui;max-width:42rem;margin:4rem auto;padding:0 1rem;color:#17202a}code{background:#eef2f5;padding:.2rem .4rem;border-radius:.3rem}</style><h1>COROS Actions</h1><p>Servicio privado para el GPT de David.</p><p>Estado: <strong>activo</strong>. Las operaciones requieren autenticación.</p></html>"""


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    configured = bool(os.environ.get("COROS_EMAIL") and os.environ.get("COROS_PASSWORD"))
    return {"status": "active", "coros_credentials_configured": str(configured).lower()}


@app.get("/privacy", response_class=HTMLResponse, include_in_schema=False)
async def privacy() -> str:
    return """<!doctype html><html lang=\"es\"><meta name=\"viewport\" content=\"width=device-width\"><title>Privacidad</title><body style=\"font:17px system-ui;max-width:42rem;margin:4rem auto;padding:0 1rem\"><h1>Privacidad</h1><p>Servicio personal y privado. Procesa únicamente los datos necesarios para consultar y modificar la cuenta COROS de su propietario. No vende, comparte ni conserva conversaciones de ChatGPT. Las credenciales se almacenan como secretos del proveedor de alojamiento y no se incluyen en el código fuente.</p></body></html>"""


@app.get(
    "/api/today",
    operation_id="getTodayCorosSummary",
    response_model=TodayResponse,
)
async def get_today(_: Private) -> TodayResponse:
    """Return today's completed activities and scheduled workouts in COROS."""
    day = datetime.now(MADRID).strftime("%Y%m%d")
    completed = await list_activities(day, day, page=1, size=100)
    planned = await list_planned_activities(day, day)
    return TodayResponse(day=day, completed=completed, planned=planned)


@app.get(
    "/api/calendar",
    operation_id="getCorosCalendar",
    response_model=CalendarResponse,
)
async def get_calendar(
    _: Private,
    start_day: Annotated[str, Query(pattern=r"^\d{8}$")],
    end_day: Annotated[str, Query(pattern=r"^\d{8}$")],
) -> CalendarResponse:
    """Return scheduled COROS workouts for an inclusive date range."""
    return CalendarResponse.model_validate(
        await list_planned_activities(start_day, end_day)
    )


@app.post(
    "/api/workouts/schedule",
    operation_id="scheduleStructuredCorosWorkout",
    response_model=ScheduleResponse,
)
async def create_scheduled_workout(
    payload: ScheduleWorkoutRequest, _: Private
) -> ScheduleResponse:
    """Create one structured workout directly on a specific COROS calendar day."""
    if not payload.confirmed:
        raise HTTPException(409, "User confirmation is required before scheduling")
    result = await schedule_workout(
        name=payload.name,
        steps=[step.model_dump(exclude_none=True) for step in payload.steps],
        happen_day=payload.happen_day,
        sport_type=SPORT_IDS[payload.sport],
        intensity_type=INTENSITY_IDS[payload.intensity],
    )
    if result.get("error"):
        raise HTTPException(502, result["error"])
    return ScheduleResponse.model_validate(result)


@app.post(
    "/api/workouts/remove",
    operation_id="removeExactCorosWorkout",
    response_model=RemoveResponse,
)
async def remove_exact_workout(
    payload: RemoveWorkoutRequest, _: Private
) -> RemoveResponse:
    """Remove one exact workout using identifiers returned by a calendar query."""
    if not payload.confirmed:
        raise HTTPException(409, "Explicit user confirmation is required before deletion")
    result = await remove_scheduled_workout(
        payload.plan_id,
        payload.id_in_plan,
        payload.plan_program_id,
    )
    if result.get("error"):
        raise HTTPException(502, result["error"])
    return RemoveResponse.model_validate(result)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))
