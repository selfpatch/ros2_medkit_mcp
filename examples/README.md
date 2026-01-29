# MCP Configuration Examples

This directory contains example MCP configuration files for different transport modes.

## stdio Transport (`mcp-stdio.json`)

Use this configuration when running the MCP server locally via stdio transport.
This is the recommended mode for Claude Desktop and VS Code.

**Setup:**

1. Copy `mcp-stdio.json` to your VS Code workspace as `.vscode/mcp.json`
2. Update `cwd` to point to your `ros2_medkit_mcp` directory
3. Update `ROS2_MEDKIT_BASE_URL` to match your ros2_medkit gateway

**Requirements:**
- Poetry installed
- Dependencies installed (`poetry install`)
- ros2_medkit gateway running

## HTTP Transport (`mcp-http.json`)

Use this configuration when connecting to a remote MCP server running in HTTP mode.

**Setup:**

1. Start the HTTP server:
   ```bash
   poetry run ros2-medkit-mcp-http --host 0.0.0.0 --port 8765
   ```
   Or with Docker:
   ```bash
   docker-compose up
   ```

2. Copy `mcp-http.json` to your VS Code workspace as `.vscode/mcp.json`
3. Update `url` if the server is running on a different host/port

**Requirements:**
- MCP HTTP server running and accessible
- ros2_medkit gateway accessible from the MCP server

## Environment Variables

Both configurations support these environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `ROS2_MEDKIT_BASE_URL` | `http://localhost:8080/api/v1` | ros2_medkit gateway URL (include `/api/v1`) |
| `ROS2_MEDKIT_BEARER_TOKEN` | *(none)* | Optional Bearer token for authentication |
| `ROS2_MEDKIT_TIMEOUT_S` | `30` | HTTP request timeout in seconds |

**Note:** For HTTP transport, environment variables are configured on the server side,
not in the MCP client configuration.
