"""Tests for MCP plugin discovery and integration."""

from typing import Any
from unittest.mock import MagicMock, patch

from mcp.types import TextContent, Tool

from ros2_medkit_mcp.plugin import discover_plugins


class FakePlugin:
    @property
    def name(self) -> str:
        return "fake"

    def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="fake_tool",
                description="A fake tool",
                inputSchema={"type": "object", "properties": {}},
            )
        ]

    async def call_tool(self, name: str, _arguments: dict[str, Any]) -> list[TextContent]:
        if name == "fake_tool":
            return [TextContent(type="text", text="fake result")]
        raise ValueError(f"Unknown tool: {name}")

    async def startup(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass


class TestDiscoverPlugins:
    @patch("ros2_medkit_mcp.plugin.entry_points")
    def test_discovers_installed_plugins(self, mock_eps: MagicMock) -> None:
        mock_ep = MagicMock()
        mock_ep.name = "fake"
        mock_ep.value = "fake_package.plugin:FakePlugin"
        mock_ep.load.return_value = FakePlugin
        mock_eps.return_value = [mock_ep]
        plugins = discover_plugins()
        assert len(plugins) == 1
        assert plugins[0].name == "fake"

    @patch("ros2_medkit_mcp.plugin.entry_points")
    def test_no_plugins_installed(self, mock_eps: MagicMock) -> None:
        mock_eps.return_value = []
        plugins = discover_plugins()
        assert plugins == []

    @patch("ros2_medkit_mcp.plugin.entry_points")
    def test_broken_plugin_skipped(self, mock_eps: MagicMock) -> None:
        mock_ep = MagicMock()
        mock_ep.name = "broken"
        mock_ep.load.side_effect = ImportError("no such module")
        mock_eps.return_value = [mock_ep]
        plugins = discover_plugins()
        assert plugins == []
