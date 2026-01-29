# Copilot Instructions

## Project Overview

Python MCP (Model Context Protocol) server that wraps the ros2_medkit SOVD HTTP API, enabling LLM tools to interact with ROS 2 diagnostics. Provides 40+ tools for entity discovery, fault management, operations, configurations, and data access.

## Architecture

```
src/ros2_medkit_mcp/
├── __init__.py
├── config.py           # Pydantic settings (base_url, timeout, auth)
├── models.py           # Pydantic models for tool arguments
├── client.py           # Async HTTP client (SovdClient) wrapping gateway API
├── mcp_app.py          # MCP server with tool definitions and dispatcher
├── server_stdio.py     # stdio transport entrypoint
└── server_http.py      # HTTP/SSE transport entrypoint
```

## Key Components

### SovdClient (client.py)

Async HTTP client using httpx for all gateway API calls:

```python
class SovdClient:
    async def get_version(self) -> dict[str, Any]
    async def list_entities(self) -> list[dict[str, Any]]
    async def list_areas(self) -> list[dict[str, Any]]
    async def list_components(self) -> list[dict[str, Any]]
    async def list_faults(self, component_id: str) -> list[dict[str, Any]]
    async def create_execution(self, entity_id, operation_name, request_data, entity_type) -> dict
    async def get_execution_status(self, entity_id, operation_name, execution_id, entity_type) -> dict
    # ... 30+ more methods
```

### MCP Tools (mcp_app.py)

Tools are registered via `@mcp.tool()` decorator and dispatched by name:

```python
@mcp.tool()
async def sovd_version() -> str:
    """Get SOVD API version information."""
    ...

@mcp.tool()
async def sovd_entities_list(filter: str | None = None) -> str:
    """List all SOVD entities with optional filtering."""
    ...

@mcp.tool()
async def sovd_call_operation(
    entity_id: str,
    operation_name: str,
    request_data: dict | None = None,
    entity_type: str = "components"
) -> str:
    """Execute a SOVD operation (ROS 2 service call)."""
    ...
```

### Tool Categories

| Category | Tools | Description |
|----------|-------|-------------|
| Discovery | `sovd_version`, `sovd_entities_list`, `sovd_entities_get` | API info and entity listing |
| Areas | `sovd_areas_list`, `sovd_area_components`, `sovd_area_subareas` | Namespace hierarchy |
| Components | `sovd_components_list`, `sovd_component_data`, `sovd_component_subcomponents` | Component management |
| Apps | `sovd_apps_list`, `sovd_apps_get`, `sovd_apps_dependencies` | ROS 2 node info |
| Functions | `sovd_functions_list`, `sovd_functions_get`, `sovd_functions_hosts` | Functional view |
| Faults | `sovd_faults_list`, `sovd_faults_get`, `sovd_faults_clear`, `sovd_all_faults_list` | Diagnostics |
| Operations | `sovd_list_operations`, `sovd_call_operation`, `sovd_operation_status`, `sovd_cancel_operation` | Service/action invocation |
| Configurations | `sovd_list_configurations`, `sovd_get_configuration`, `sovd_set_configuration` | Parameter management |
| Data | `sovd_component_data`, `sovd_component_topic_data`, `sovd_publish_topic` | Topic access |

## SOVD Execution Model

Operations follow SOVD's async execution pattern:

1. **Create execution**: `POST /{entity_type}/{id}/operations/{name}` → returns `execution_id`
2. **Poll status**: `GET /{entity_type}/{id}/operations/{name}/executions/{execution_id}`
3. **Cancel if needed**: `DELETE /{entity_type}/{id}/operations/{name}/executions/{execution_id}`

The `sovd_call_operation` tool handles this automatically with configurable polling.

## Configuration

Environment variables (loaded via Pydantic Settings):

| Variable | Default | Description |
|----------|---------|-------------|
| `ROS2_MEDKIT_BASE_URL` | `http://localhost:8080/api/v1` | Gateway API base URL |
| `ROS2_MEDKIT_TIMEOUT` | `30.0` | HTTP request timeout (seconds) |
| `ROS2_MEDKIT_AUTH_TOKEN` | `None` | Optional Bearer token |

## Running the Server

```bash
# stdio transport (for Claude Desktop, etc.)
poetry run ros2-medkit-mcp-stdio

# HTTP/SSE transport (for VS Code, web clients)
poetry run ros2-medkit-mcp-http  # Default: http://0.0.0.0:8000

# Docker
docker run -e ROS2_MEDKIT_BASE_URL=http://host.docker.internal:8080/api/v1 \
  ghcr.io/selfpatch/ros2-medkit-mcp:latest
```

## Development

```bash
# Install dependencies
poetry install

# Run tests (avoids ROS 2 pytest plugin conflicts)
poetry run python run_tests.py -v

# Linting and formatting
poetry run ruff check src/ tests/
poetry run ruff format src/ tests/

# Type checking
poetry run mypy src/

# Install pre-commit hooks
poetry run pre-commit install
```

## Conventions

- Python 3.11+ with strict typing
- Use `X | None` instead of `Optional[X]`
- Pydantic for all data models and settings
- httpx for async HTTP client
- All tool responses are JSON-formatted strings
- Error responses include structured error details from gateway

## Gateway API Reference

Default base URL: `http://localhost:8080/api/v1`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/version` | API version info |
| GET | `/entities` | List all entities |
| GET | `/areas` | List areas |
| GET | `/components` | List components |
| GET | `/apps` | List apps |
| GET | `/functions` | List functions |
| GET | `/{type}/{id}/data` | List data topics |
| GET | `/{type}/{id}/operations` | List operations |
| GET | `/{type}/{id}/configurations` | List configurations |
| GET | `/{type}/{id}/faults` | List faults |
| POST | `/{type}/{id}/operations/{name}` | Create execution |
| GET | `/{type}/{id}/operations/{name}/executions/{exec_id}` | Get execution status |
| DELETE | `/{type}/{id}/operations/{name}/executions/{exec_id}` | Cancel execution |

## Important Notes

- This MCP server connects to `ros2_medkit_gateway` running on port 8080
- Entity IDs are alphanumeric + underscore + hyphen only
- Entity types for API: `areas`, `components`, `apps`, `functions` (plural)
- Tool names use `sovd_` prefix and snake_case
