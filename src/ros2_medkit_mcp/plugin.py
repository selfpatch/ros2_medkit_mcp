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
            logger.info("Discovered plugin: %s (from %s)", plugin.name, ep.value)
            plugins.append(plugin)
        except Exception:
            logger.exception("Failed to load plugin: %s", ep.name)
    return plugins
