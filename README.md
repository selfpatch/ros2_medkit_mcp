# ros2_medkit_mcp

[![CI](https://github.com/selfpatch/ros2_medkit_mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/selfpatch/ros2_medkit_mcp/actions/workflows/ci.yml)
[![GHCR](https://img.shields.io/badge/GHCR-ghcr.io%2Fselfpatch%2Fros2__medkit__mcp-blue?logo=github)](https://github.com/selfpatch/ros2_medkit_mcp/pkgs/container/ros2_medkit_mcp)
[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://selfpatch.github.io/ros2_medkit/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Discord](https://img.shields.io/badge/Discord-Join%20Us-7289DA?logo=discord&logoColor=white)](https://discord.gg/fEbWKTah)

A thin MCP (Model Context Protocol) adapter that connects an LLM to an existing SOVD HTTP API exposed by [ros2_medkit](https://github.com/selfpatch/ros2_medkit).

## Overview

This server does **not** implement SOVD itself. It provides MCP tools that call the existing HTTP endpoints of a running ros2_medkit gateway.

## Features

- **Full ros2_medkit gateway coverage**: Discovery, component data, operations (services/actions), and configurations (ROS 2 parameters)
- **Dual transport support**: stdio and streamable-http
- **Async HTTP client** using httpx
- **Pydantic validation** for configuration and models
- **Bearer token authentication** support

## Quick Start

### Prerequisites

- Python 3.11+
- Poetry
- A running ros2_medkit gateway (default: `http://localhost:8080`)

### Installation

```bash
# Clone the repository
git clone https://github.com/selfpatch/ros2_medkit_mcp.git
cd ros2_medkit_mcp

# Install dependencies
poetry install
```

### Configuration

The server is configured via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `ROS2_MEDKIT_BASE_URL` | `http://localhost:8080/api/v1` | Base URL of the ros2_medkit SOVD API |
| `ROS2_MEDKIT_BEARER_TOKEN` | *(none)* | Optional Bearer token for authentication |
| `ROS2_MEDKIT_TIMEOUT_S` | `30` | HTTP request timeout in seconds |

### Running the Server

#### stdio Transport (for Claude Desktop, etc.)

```bash
poetry run ros2-medkit-mcp-stdio
```

For Claude Desktop, add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ros2_medkit": {
      "command": "poetry",
      "args": ["run", "ros2-medkit-mcp-stdio"],
      "cwd": "/path/to/ros2_medkit_mcp",
      "env": {
        "ROS2_MEDKIT_BASE_URL": "http://localhost:8080/api/v1"
      }
    }
  }
}
```

#### Streamable HTTP Transport

```bash
poetry run ros2-medkit-mcp-http --host 0.0.0.0 --port 8765
```

The server will be available at `http://0.0.0.0:8765/mcp`.

#### VS Code MCP Configuration

See the [examples/](examples/) directory for ready-to-use MCP configuration files:
- `mcp-stdio.json` - Local stdio transport
- `mcp-http.json` - HTTP transport for remote server

### Docker

```bash
# Build image
docker build -t ros2-medkit-mcp .

# Run HTTP server (default)
docker run -p 8765:8765 ros2-medkit-mcp

# Run with stdio transport
docker run -i ros2-medkit-mcp stdio

# With custom gateway URL
docker run -p 8765:8765 -e ROS2_MEDKIT_BASE_URL=http://host.docker.internal:8080/api/v1 ros2-medkit-mcp
```

Using docker-compose:

```bash
docker-compose up
```

#### Using Docker Image as MCP Server in VS Code

To use the Docker image as an MCP server in VS Code with the GitHub Copilot extension:

1. **Start the MCP server container:**

   ```bash
   docker run -d --name ros2-medkit-mcp -p 8765:8765 \
     -e ROS2_MEDKIT_BASE_URL=http://host.docker.internal:8080/api/v1 \
     ghcr.io/selfpatch/ros2_medkit_mcp:latest
   ```

2. **Configure VS Code MCP settings** (`.vscode/mcp.json` or user settings):

   ```json
   {
     "servers": {
       "ros2_medkit": {
         "type": "sse",
         "url": "http://localhost:8765/mcp",
         "headers": {}
       }
     }
   }
   ```

3. **Verify the connection** by checking the health endpoint:

   ```bash
   curl http://localhost:8765/health
   ```

   Expected response:
   ```json
   {"status": "healthy", "service": "ros2_medkit_mcp", "sovd_url": "http://host.docker.internal:8080/api/v1"}
   ```

4. **Use with Copilot Chat** - the MCP tools will be available for querying ROS 2 system state via SOVD API.

> **Note:** Use `host.docker.internal` to connect from the container to services running on your host machine (like ros2_medkit gateway).

## MCP Tools

### Discovery Tools

#### `sovd_version`
Get the SOVD API version information.

**Arguments:** None
**Returns:** JSON version object from `GET /version-info`

#### `sovd_entities_list`
List all SOVD entities (areas, components, apps, and functions) with optional filtering.

**Arguments:**
- `filter` (optional, string): Substring filter applied to entity `id` and `name` fields

**Returns:** Combined array of areas from `GET /areas`, components from `GET /components`, apps from `GET /apps`, and functions from `GET /functions` (when those endpoints are available)

#### `sovd_entities_get`
Get a specific entity by ID with live data if available.

**Arguments:**
- `entity_id` (required, string): The entity identifier

**Returns:** Entity object with optional `data` field for components

#### `sovd_faults_list`
List faults for a specific component.

**Arguments:**
- `component_id` (required, string): The component identifier

**Returns:** Array of fault objects from `GET /components/{component_id}/faults`

#### `sovd_faults_get`
Get a specific fault by ID.

**Arguments:**
- `component_id` (required, string): The component identifier
- `fault_id` (required, string): The fault identifier

**Returns:** Fault object from `GET /components/{component_id}/faults/{fault_id}`

#### `sovd_faults_clear`
Clear (acknowledge/dismiss) a fault.

**Arguments:**
- `component_id` (required, string): The component identifier
- `fault_id` (required, string): The fault identifier to clear

**Returns:** Response from `DELETE /components/{component_id}/faults/{fault_id}`

#### `sovd_area_components`
List all components within a specific area.

**Arguments:**
- `area_id` (required, string): The area identifier (e.g., 'powertrain', 'chassis', 'body')

**Returns:** Array of component objects from `GET /areas/{area_id}/components`

### Entity Data Tools

#### `sovd_entity_data`
Read all topic data from an entity (component or app).

**Arguments:**
- `entity_id` (required, string): The entity identifier
- `entity_type` (optional, string): Entity type - 'components' or 'apps' (default: 'components')

**Returns:** Array of topic data from `GET /{entity_type}/{entity_id}/data`

#### `sovd_entity_topic_data`
Read data from a specific topic within an entity.

**Arguments:**
- `entity_id` (required, string): The entity identifier
- `topic_name` (required, string): The topic name (e.g., 'temperature', 'rpm')
- `entity_type` (optional, string): Entity type - 'components' or 'apps' (default: 'components')

**Returns:** Topic data from `GET /{entity_type}/{entity_id}/data/{topic_name}`

#### `sovd_publish_topic`
Publish data to a component's topic.

**Arguments:**
- `component_id` (required, string): The component identifier
- `topic_name` (required, string): The topic name to publish to
- `data` (required, object): The message data to publish as JSON object

**Returns:** Response from `PUT /components/{component_id}/data/{topic_name}`

### Operations Tools (Services & Actions)

#### `sovd_list_operations`
List all operations (services and actions) available for a component.

**Arguments:**
- `component_id` (required, string): The component identifier

**Returns:** Array of operations from `GET /components/{component_id}/operations`

#### `sovd_create_execution`
Call a ROS 2 service or send an action goal.

**Arguments:**
- `entity_id` (required, string): The entity identifier
- `operation_name` (required, string): The operation name (service or action)
- `request_data` (optional, object): Request data (parameters for actions/services)
- `entity_type` (optional, string): Entity type - 'components', 'apps', 'areas', or 'functions' (default: 'components')

**Returns:** Response from `POST /{entity_type}/{entity_id}/operations/{operation_name}/executions`

#### `sovd_get_execution`
Get the current status of a running action execution.

**Arguments:**
- `entity_id` (required, string): The entity identifier
- `operation_name` (required, string): The action name
- `execution_id` (required, string): The execution ID (goal_id)
- `entity_type` (optional, string): Entity type (default: 'components')

**Returns:** Status from `GET /{entity_type}/{entity_id}/operations/{operation_name}/executions/{execution_id}`

#### `sovd_list_executions`
List all executions for an operation.

**Arguments:**
- `entity_id` (required, string): The entity identifier
- `operation_name` (required, string): The action name
- `entity_type` (optional, string): Entity type (default: 'components')

**Returns:** List from `GET /{entity_type}/{entity_id}/operations/{operation_name}/executions`

#### `sovd_cancel_execution`
Cancel a running action execution.

**Arguments:**
- `entity_id` (required, string): The entity identifier
- `operation_name` (required, string): The action name
- `execution_id` (required, string): The execution ID (goal_id)
- `entity_type` (optional, string): Entity type (default: 'components')

**Returns:** Response from `DELETE /{entity_type}/{entity_id}/operations/{operation_name}/executions/{execution_id}`

### Configuration Tools (ROS 2 Parameters)

#### `sovd_list_configurations`
List all configurations (ROS 2 parameters) for a component.

**Arguments:**
- `component_id` (required, string): The component identifier

**Returns:** Array of parameters from `GET /components/{component_id}/configurations`

#### `sovd_get_configuration`
Get a specific configuration (parameter) value.

**Arguments:**
- `component_id` (required, string): The component identifier
- `param_name` (required, string): The parameter name

**Returns:** Parameter value from `GET /components/{component_id}/configurations/{param_name}`

#### `sovd_set_configuration`
Set a configuration (parameter) value.

**Arguments:**
- `component_id` (required, string): The component identifier
- `param_name` (required, string): The parameter name
- `value` (required, any): The new parameter value (string, number, boolean, or array)

**Returns:** Response from `PUT /components/{component_id}/configurations/{param_name}`

#### `sovd_delete_configuration`
Reset a configuration (parameter) to its default value.

**Arguments:**
- `component_id` (required, string): The component identifier
- `param_name` (required, string): The parameter name

**Returns:** Response from `DELETE /components/{component_id}/configurations/{param_name}`

#### `sovd_delete_all_configurations`
Reset all configurations (parameters) to their default values.

**Arguments:**
- `component_id` (required, string): The component identifier

**Returns:** Response from `DELETE /components/{component_id}/configurations`

## MCP Resources

### `sovd://openapi`

Returns information about the OpenAPI specification location.

## Development

### Setup

```bash
# Install dependencies including dev tools
poetry install

# Install pre-commit hooks
poetry run pre-commit install
```

### Running Tests

```bash
# Use the test runner script (recommended, avoids ROS 2 plugin conflicts)
poetry run python run_tests.py -v

# Or directly if not in a ROS 2 environment
poetry run pytest -v
```

### Code Quality

```bash
# Run all pre-commit hooks
poetry run pre-commit run --all-files

# Or run individually:
poetry run ruff check src/ tests/     # Linting
poetry run ruff format src/ tests/    # Formatting
poetry run mypy src/                   # Type checking
```

## License
