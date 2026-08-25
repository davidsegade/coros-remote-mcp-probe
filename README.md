# COROS Remote MCP probe

Minimal, stateless MCP service used only to verify remote connectivity from
ChatGPT/Codex. It exposes one `estado` tool and does not contain COROS code,
credentials, tokens, personal data, or write operations.

The probe is intentionally unauthenticated because it returns only fixed
non-sensitive status data. Authentication must be added before connecting any
COROS capability.
