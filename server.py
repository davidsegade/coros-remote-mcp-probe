import os
from datetime import datetime, timezone

from fastmcp import FastMCP


mcp = FastMCP("COROS Remote Probe")


@mcp.tool
def estado() -> dict[str, str]:
    """Confirm that the remote MCP is online. It does not access COROS."""
    return {
        "status": "activo",
        "service": "coros-remote-probe",
        "coros_connected": "no",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    mcp.run(
        transport="http",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "10000")),
        path="/mcp",
        stateless_http=True,
    )
