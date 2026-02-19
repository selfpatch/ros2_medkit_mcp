"""Streamable HTTP transport entrypoint for ros2_medkit MCP server.

This module provides the main entrypoint for running the MCP server
using streamable HTTP transport via uvicorn.
"""

import argparse
import logging
import sys

import uvicorn
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from ros2_medkit_mcp.client import SovdClient
from ros2_medkit_mcp.config import get_settings
from ros2_medkit_mcp.mcp_app import create_mcp_server, setup_mcp_app
from ros2_medkit_mcp.plugin import discover_plugins

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> Starlette:
    """Create the Starlette ASGI application with MCP endpoints.

    Returns:
        Configured Starlette application.
    """
    settings = get_settings()
    mcp_server = create_mcp_server()
    client = SovdClient(settings)
    plugins = discover_plugins()
    setup_mcp_app(mcp_server, settings, client, plugins=plugins)

    # Create SSE transport - path is where clients POST messages
    sse_transport = SseServerTransport("/mcp/messages/")

    async def handle_sse(request: Request) -> Response:
        """Handle SSE connections for MCP.

        Note: We use request._send (private attribute) because the MCP SDK requires
        direct access to the ASGI send callable. This is the documented approach
        in mcp/server/sse.py - there is no public Starlette API alternative.

        Must return Response() to avoid NoneType error on disconnect.
        """
        try:
            async with sse_transport.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await mcp_server.run(
                    streams[0],
                    streams[1],
                    mcp_server.create_initialization_options(),
                )
        except Exception:
            logger.exception("Unhandled exception in SSE handler")
        return Response()

    async def health_check(_request: Request) -> JSONResponse:
        """Health check endpoint.

        Returns:
            JSON response with status.
        """
        return JSONResponse(
            {
                "status": "healthy",
                "service": "ros2_medkit_mcp",
                "sovd_url": settings.base_url,
            }
        )

    started_plugins: list = []

    async def on_startup() -> None:
        """Application startup handler."""
        logger.info("ros2_medkit MCP server starting (HTTP transport)")
        logger.info("Connecting to SOVD API at %s", settings.base_url)
        # Start plugins
        for plugin in plugins:
            try:
                await plugin.startup()
                started_plugins.append(plugin)
                logger.info("Plugin started: %s", plugin.name)
            except Exception:
                logger.exception("Failed to start plugin: %s", plugin.name)

    async def on_shutdown() -> None:
        """Application shutdown handler."""
        # Only shutdown plugins that started successfully
        for plugin in started_plugins:
            try:
                await plugin.shutdown()
            except Exception:
                logger.exception("Failed to shutdown plugin: %s", plugin.name)
        await client.close()
        logger.info("Server shutdown complete")

    # Build the Starlette app
    # SSE endpoint uses Route with Request, messages uses Mount with ASGI handler
    app = Starlette(
        debug=False,
        routes=[
            Route("/health", health_check, methods=["GET"]),
            Route("/mcp", handle_sse, methods=["GET"]),
            Mount("/mcp/messages/", app=sse_transport.handle_post_message),
        ],
        on_startup=[on_startup],
        on_shutdown=[on_shutdown],
    )

    return app


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(description="ros2_medkit MCP server with HTTP transport")
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port to bind to (default: 8765)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )
    return parser.parse_args()


def main() -> None:
    """Main entrypoint for HTTP transport."""
    args = parse_args()

    logger.info("Starting server on %s:%d", args.host, args.port)

    try:
        uvicorn.run(
            "ros2_medkit_mcp.server_http:create_app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            factory=True,
            log_level="info",
        )
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.exception("Server failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
