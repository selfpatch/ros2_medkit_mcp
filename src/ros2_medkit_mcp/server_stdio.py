"""stdio transport entrypoint for ros2_medkit MCP server.

This module provides the main entrypoint for running the MCP server
using stdio transport, suitable for use with Claude Desktop and similar tools.
"""

import asyncio
import logging
import sys

from mcp.server.stdio import stdio_server

from ros2_medkit_mcp.client import SovdClient
from ros2_medkit_mcp.config import get_settings
from ros2_medkit_mcp.mcp_app import create_mcp_server, setup_mcp_app
from ros2_medkit_mcp.plugin import discover_plugins

# Configure logging to stderr to avoid interfering with stdio transport
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


async def run_server() -> None:
    """Run the MCP server with stdio transport."""
    settings = get_settings()
    logger.info("Starting ros2_medkit MCP server (stdio transport)")
    logger.info("Connecting to SOVD API at %s", settings.base_url)

    server = create_mcp_server()
    client = SovdClient(settings)
    plugins = discover_plugins()

    try:
        # Start plugins
        for plugin in plugins:
            try:
                await plugin.startup()
                logger.info("Plugin started: %s", plugin.name)
            except Exception:
                logger.exception("Failed to start plugin: %s", plugin.name)

        setup_mcp_app(server, settings, client, plugins=plugins)

        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
    finally:
        # Shutdown plugins
        for plugin in plugins:
            try:
                await plugin.shutdown()
            except Exception:
                logger.exception("Failed to shutdown plugin: %s", plugin.name)
        await client.close()
        logger.info("Server shutdown complete")


def main() -> None:
    """Main entrypoint for stdio transport."""
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.exception("Server failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
