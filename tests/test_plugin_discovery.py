"""Tests for MCP plugin discovery and integration."""

import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.types import TextContent, Tool

from ros2_medkit_mcp.plugin import discover_plugins, shutdown_plugins, start_plugins


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

    @patch("ros2_medkit_mcp.plugin.entry_points")
    def test_non_conforming_plugin_skipped(self, mock_eps: MagicMock) -> None:
        """Plugin without required attributes is skipped with warning."""

        class BadPlugin:
            pass

        mock_ep = MagicMock()
        mock_ep.name = "bad"
        mock_ep.load.return_value = BadPlugin
        mock_eps.return_value = [mock_ep]
        plugins = discover_plugins()
        assert plugins == []


class TestPluginLifecycle:
    @pytest.mark.asyncio
    async def test_start_plugins_returns_started(self) -> None:
        plugin = FakePlugin()
        started = await start_plugins([plugin])
        assert len(started) == 1
        assert started[0] is plugin

    @pytest.mark.asyncio
    async def test_start_plugins_skips_failed(self) -> None:
        good = FakePlugin()
        bad = MagicMock()
        bad.name = "bad"
        bad.startup = AsyncMock(side_effect=RuntimeError("init failed"))
        started = await start_plugins([good, bad])
        assert len(started) == 1
        assert started[0] is good

    @pytest.mark.asyncio
    async def test_shutdown_plugins_calls_all(self) -> None:
        p1 = MagicMock()
        p1.name = "p1"
        p1.shutdown = AsyncMock()
        p2 = MagicMock()
        p2.name = "p2"
        p2.shutdown = AsyncMock()
        await shutdown_plugins([p1, p2])
        p1.shutdown.assert_awaited_once()
        p2.shutdown.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_shutdown_plugins_continues_on_error(self) -> None:
        p1 = MagicMock()
        p1.name = "p1"
        p1.shutdown = AsyncMock(side_effect=RuntimeError("boom"))
        p2 = MagicMock()
        p2.name = "p2"
        p2.shutdown = AsyncMock()
        await shutdown_plugins([p1, p2])
        p2.shutdown.assert_awaited_once()


class TestPluginToolRegistration:
    """Tests for plugin tool registration and dispatch in mcp_app.register_tools."""

    def _make_server_mock(self) -> tuple[MagicMock, dict[str, Any]]:
        """Create a mock Server that captures registered handlers."""
        server = MagicMock()
        handlers: dict[str, Any] = {}

        def list_tools_decorator():
            def wrapper(fn: Any) -> Any:
                handlers["list_tools"] = fn
                return fn

            return wrapper

        def call_tool_decorator():
            def wrapper(fn: Any) -> Any:
                handlers["call_tool"] = fn
                return fn

            return wrapper

        server.list_tools = list_tools_decorator
        server.call_tool = call_tool_decorator
        return server, handlers

    @pytest.mark.asyncio
    async def test_plugin_tool_dispatch(self) -> None:
        """Plugin tools are dispatched via plugin_tool_map."""
        from ros2_medkit_mcp.mcp_app import register_tools

        server, handlers = self._make_server_mock()
        client = MagicMock()
        plugin = FakePlugin()

        register_tools(server, client, plugins=[plugin])

        # list_tools should include the plugin tool
        tools = await handlers["list_tools"]()
        tool_names = {t.name for t in tools}
        assert "fake_tool" in tool_names

        # call_tool should dispatch to plugin
        result = await handlers["call_tool"]("fake_tool", {})
        assert len(result) == 1
        assert result[0].text == "fake result"

    @pytest.mark.asyncio
    async def test_builtin_collision_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        """Plugin tool colliding with built-in is skipped with warning."""
        from ros2_medkit_mcp.mcp_app import register_tools

        class CollidingPlugin:
            @property
            def name(self) -> str:
                return "colliding"

            def list_tools(self) -> list[Tool]:
                return [
                    Tool(
                        name="sovd_health",
                        description="Collides with built-in",
                        inputSchema={"type": "object", "properties": {}},
                    )
                ]

            async def call_tool(self, _name: str, _arguments: dict[str, Any]) -> list[TextContent]:
                return [TextContent(type="text", text="should not reach")]

            async def startup(self) -> None:
                pass

            async def shutdown(self) -> None:
                pass

        server, handlers = self._make_server_mock()
        client = MagicMock()
        register_tools(server, client, plugins=[CollidingPlugin()])

        with caplog.at_level(logging.WARNING):
            tools = await handlers["list_tools"]()

        assert "collides with built-in tool" in caplog.text

        # sovd_health should appear exactly once (the built-in)
        plugin_tool_names = [t.name for t in tools if t.name == "sovd_health"]
        assert len(plugin_tool_names) == 1

    @pytest.mark.asyncio
    async def test_inter_plugin_collision_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        """Second plugin declaring same tool name is skipped."""
        from ros2_medkit_mcp.mcp_app import register_tools

        class PluginA:
            @property
            def name(self) -> str:
                return "plugin_a"

            def list_tools(self) -> list[Tool]:
                return [
                    Tool(
                        name="shared_tool",
                        description="From A",
                        inputSchema={"type": "object", "properties": {}},
                    )
                ]

            async def call_tool(self, _name: str, _arguments: dict[str, Any]) -> list[TextContent]:
                return [TextContent(type="text", text="from A")]

            async def startup(self) -> None:
                pass

            async def shutdown(self) -> None:
                pass

        class PluginB:
            @property
            def name(self) -> str:
                return "plugin_b"

            def list_tools(self) -> list[Tool]:
                return [
                    Tool(
                        name="shared_tool",
                        description="From B",
                        inputSchema={"type": "object", "properties": {}},
                    )
                ]

            async def call_tool(self, _name: str, _arguments: dict[str, Any]) -> list[TextContent]:
                return [TextContent(type="text", text="from B")]

            async def startup(self) -> None:
                pass

            async def shutdown(self) -> None:
                pass

        server, handlers = self._make_server_mock()
        client = MagicMock()
        register_tools(server, client, plugins=[PluginA(), PluginB()])

        with caplog.at_level(logging.WARNING):
            await handlers["list_tools"]()

        assert "collides with another plugin tool" in caplog.text

        # Dispatch should go to plugin A (first registered)
        result = await handlers["call_tool"]("shared_tool", {})
        assert result[0].text == "from A"
