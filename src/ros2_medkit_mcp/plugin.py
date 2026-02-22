"""Plugin interface for ros2_medkit_mcp.

Third-party packages can register as plugins via entry_points:

    [project.entry-points."ros2_medkit_mcp.plugins"]
    my_plugin = "my_package.plugin:MyPlugin"

Plugins must implement the McpPlugin protocol.
"""

from __future__ import annotations

import logging
from importlib.metadata import entry_points
from typing import Any, Protocol

from mcp.types import TextContent, Tool

logger = logging.getLogger(__name__)

PLUGIN_GROUP = "ros2_medkit_mcp.plugins"


class McpPlugin(Protocol):
    """Interface for MCP server plugins."""

    @property
    def name(self) -> str: ...

    def list_tools(self) -> list[Tool]: ...

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> list[TextContent]: ...

    async def startup(self) -> None: ...

    async def shutdown(self) -> None: ...


def discover_plugins() -> list[McpPlugin]:
    """Discover and instantiate plugins registered via entry_points."""
    plugins: list[McpPlugin] = []
    for ep in entry_points(group=PLUGIN_GROUP):
        try:
            plugin_cls = ep.load()
            plugin = plugin_cls()
            if not hasattr(plugin, "name") or not hasattr(plugin, "list_tools"):
                logger.warning("Plugin %s does not implement McpPlugin, skipping", ep.name)
                continue
            logger.info("Discovered plugin: %s (from %s)", plugin.name, ep.value)
            plugins.append(plugin)
        except Exception:
            logger.exception("Failed to load plugin: %s", ep.name)
    return plugins


async def start_plugins(plugins: list[McpPlugin]) -> list[McpPlugin]:
    """Start plugins, returning only those that started successfully."""
    started: list[McpPlugin] = []
    for plugin in plugins:
        try:
            await plugin.startup()
            started.append(plugin)
            logger.info("Plugin started: %s", plugin.name)
        except Exception:
            logger.exception("Failed to start plugin: %s", plugin.name)
    return started


async def shutdown_plugins(plugins: list[McpPlugin]) -> None:
    """Shut down plugins, logging errors without raising."""
    for plugin in plugins:
        try:
            await plugin.shutdown()
        except Exception:
            logger.exception("Failed to shutdown plugin: %s", plugin.name)
