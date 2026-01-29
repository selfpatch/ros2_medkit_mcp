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
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.types import Receive, Scope, Send

from ros2_medkit_mcp.client import SovdClient
from ros2_medkit_mcp.config import get_settings
from ros2_medkit_mcp.mcp_app import create_mcp_server, setup_mcp_app

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
    setup_mcp_app(mcp_server, settings, client)

    # Create SSE transport
    sse_transport = SseServerTransport("/mcp/messages/")

    async def handle_sse(scope: Scope, receive: Receive, send: Send) -> None:
        """Handle SSE connections for MCP as an ASGI endpoint."""
        async with sse_transport.connect_sse(scope, receive, send) as streams:
            await mcp_server.run(
                streams[0],
                streams[1],
                mcp_server.create_initialization_options(),
            )

    async def handle_messages(scope: Scope, receive: Receive, send: Send) -> None:
        """Handle incoming MCP messages via POST as an ASGI endpoint."""
        await sse_transport.handle_post_message(scope, receive, send)

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

    async def on_startup() -> None:
        """Application startup handler."""
        logger.info("ros2_medkit MCP server starting (HTTP transport)")
        logger.info("Connecting to SOVD API at %s", settings.base_url)

    async def on_shutdown() -> None:
        """Application shutdown handler."""
        await client.close()
        logger.info("Server shutdown complete")

    # Build the Starlette app
    app = Starlette(
        debug=False,
        routes=[
            Route("/health", health_check, methods=["GET"]),
            Route("/mcp", handle_sse, methods=["GET"]),
            Route("/mcp/messages/", handle_messages, methods=["POST"]),
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
