# David COROS Actions

Private REST API for a personal ChatGPT GPT Action. It translates explicit,
structured requests into calls to the unofficial COROS web API.

## Security

- Every `/api/*` endpoint requires `Authorization: Bearer <ACTION_API_KEY>`.
- `COROS_EMAIL`, `COROS_PASSWORD`, `COROS_REGION`, and `ACTION_API_KEY` are
  Render secrets. They must never be committed to this repository.
- Write operations require an explicit `confirmed: true` flag.
- Deletion requires the exact plan identifiers returned by COROS.
- The service does not store ChatGPT conversations.

## Render environment

Set these private environment variables in Render:

- `ACTION_API_KEY`: long random secret used only by the GPT Action
- `COROS_EMAIL`: COROS login email
- `COROS_PASSWORD`: COROS login password
- `COROS_REGION`: `eu`
- `COROS_TIMEZONE`: `2` in summer, `1` in winter (display only)

The OpenAPI schema for the private GPT Action is served at `/openapi.json`.
