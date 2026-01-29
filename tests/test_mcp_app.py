"""Tests for MCP app call_tool dispatcher."""

import httpx
import pytest
import respx
from mcp.types import TextContent

from ros2_medkit_mcp.client import SovdClient, SovdClientError
from ros2_medkit_mcp.config import Settings
from ros2_medkit_mcp.mcp_app import TOOL_ALIASES, format_error, format_json_response
from ros2_medkit_mcp.models import (
    EntitiesListArgs,
    FaultsListArgs,
    ListOperationsArgs,
    filter_entities,
)


@pytest.fixture
def settings() -> Settings:
    """Create test settings."""
    return Settings(
        base_url="http://test-sovd:8080/api/v1",
        bearer_token=None,
        timeout_seconds=5.0,
    )


@pytest.fixture
def client(settings: Settings) -> SovdClient:
    """Create test client."""
    return SovdClient(settings)


class TestToolAliases:
    """Tests for tool alias resolution."""

    def test_alias_dot_notation(self) -> None:
        """Test dot-notation aliases resolve to underscore names."""
        assert TOOL_ALIASES.get("sovd.version") == "sovd_version"
        assert TOOL_ALIASES.get("sovd.entities.list") == "sovd_entities_list"
        assert TOOL_ALIASES.get("sovd.faults.list") == "sovd_faults_list"

    def test_canonical_name_unchanged(self) -> None:
        """Test canonical names resolve to themselves."""
        assert TOOL_ALIASES.get("sovd_version") == "sovd_version"
        assert TOOL_ALIASES.get("sovd_entities_list") == "sovd_entities_list"


class TestFormatFunctions:
    """Tests for response formatting functions."""

    def test_format_json_response(self) -> None:
        """Test JSON response formatting."""
        data = {"key": "value", "number": 42}
        result = format_json_response(data)

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert '"key": "value"' in result[0].text
        assert '"number": 42' in result[0].text

    def test_format_json_response_list(self) -> None:
        """Test JSON response formatting with list."""
        data = [{"id": "1"}, {"id": "2"}]
        result = format_json_response(data)

        assert len(result) == 1
        assert '"id": "1"' in result[0].text
        assert '"id": "2"' in result[0].text

    def test_format_error(self) -> None:
        """Test error response formatting."""
        result = format_error("Something went wrong")

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "Something went wrong" in result[0].text
        assert "error" in result[0].text  # lowercase 'error' key in JSON


class TestCallToolIntegration:
    """Integration tests for call_tool via client methods."""

    @respx.mock
    async def test_version_call(self, client: SovdClient) -> None:
        """Test version tool integration."""
        expected = {"version": "1.0.0", "name": "ros2_medkit"}
        respx.get("http://test-sovd:8080/api/v1/version-info").mock(
            return_value=httpx.Response(200, json=expected)
        )

        result = await client.get_version()
        formatted = format_json_response(result)

        assert "1.0.0" in formatted[0].text
        await client.close()

    @respx.mock
    async def test_entities_list_call(self, client: SovdClient) -> None:
        """Test entities_list tool integration."""
        areas = [{"id": "powertrain", "type": "Area"}]
        components = [{"id": "temp_sensor", "type": "Component"}]
        respx.get("http://test-sovd:8080/api/v1/areas").mock(
            return_value=httpx.Response(200, json=areas)
        )
        respx.get("http://test-sovd:8080/api/v1/components").mock(
            return_value=httpx.Response(200, json=components)
        )
        respx.get("http://test-sovd:8080/api/v1/apps").mock(
            return_value=httpx.Response(200, json=[])
        )
        respx.get("http://test-sovd:8080/api/v1/functions").mock(
            return_value=httpx.Response(200, json=[])
        )

        entities = await client.list_entities()
        # Apply filter like the tool does
        args = EntitiesListArgs(filter=None)
        filtered = filter_entities(entities, args.filter)
        formatted = format_json_response(filtered)

        assert "powertrain" in formatted[0].text
        assert "temp_sensor" in formatted[0].text
        await client.close()

    @respx.mock
    async def test_entities_list_with_filter(self, client: SovdClient) -> None:
        """Test entities_list tool with filter."""
        areas = [{"id": "powertrain", "type": "Area"}]
        components = [
            {"id": "temp_sensor", "type": "Component"},
            {"id": "rpm_sensor", "type": "Component"},
        ]
        respx.get("http://test-sovd:8080/api/v1/areas").mock(
            return_value=httpx.Response(200, json=areas)
        )
        respx.get("http://test-sovd:8080/api/v1/components").mock(
            return_value=httpx.Response(200, json=components)
        )
        respx.get("http://test-sovd:8080/api/v1/apps").mock(
            return_value=httpx.Response(200, json=[])
        )
        respx.get("http://test-sovd:8080/api/v1/functions").mock(
            return_value=httpx.Response(200, json=[])
        )

        entities = await client.list_entities()
        args = EntitiesListArgs(filter="temp")
        filtered = filter_entities(entities, args.filter)
        formatted = format_json_response(filtered)

        assert "temp_sensor" in formatted[0].text
        assert "rpm_sensor" not in formatted[0].text
        await client.close()

    @respx.mock
    async def test_faults_list_call(self, client: SovdClient) -> None:
        """Test faults_list tool integration."""
        faults = [{"id": "fault-1", "severity": "high"}]
        respx.get("http://test-sovd:8080/api/v1/components/test-comp/faults").mock(
            return_value=httpx.Response(200, json=faults)
        )

        args = FaultsListArgs(entity_id="test-comp", entity_type="components")
        result = await client.list_faults(args.entity_id, args.entity_type)
        formatted = format_json_response(result)

        assert "fault-1" in formatted[0].text
        await client.close()

    @respx.mock
    async def test_list_operations_call(self, client: SovdClient) -> None:
        """Test list_operations tool integration."""
        operations = [{"name": "test_service", "type": "service"}]
        respx.get("http://test-sovd:8080/api/v1/components/test-comp/operations").mock(
            return_value=httpx.Response(200, json=operations)
        )

        args = ListOperationsArgs(entity_id="test-comp", entity_type="components")
        result = await client.list_operations(args.entity_id, args.entity_type)
        formatted = format_json_response(result)

        assert "test_service" in formatted[0].text
        await client.close()

    @respx.mock
    async def test_client_error_formatting(self, client: SovdClient) -> None:
        """Test client error is properly formatted."""
        respx.get("http://test-sovd:8080/api/v1/version-info").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )

        with pytest.raises(SovdClientError) as exc_info:
            await client.get_version()

        error_formatted = format_error(str(exc_info.value))
        assert "500" in error_formatted[0].text
        await client.close()


class TestArgumentModels:
    """Tests for argument model validation."""

    def test_faults_list_args_defaults(self) -> None:
        """Test FaultsListArgs default entity_type."""
        args = FaultsListArgs(entity_id="test-comp")
        assert args.entity_type == "components"

    def test_faults_list_args_custom_type(self) -> None:
        """Test FaultsListArgs with custom entity_type."""
        args = FaultsListArgs(entity_id="test-app", entity_type="apps")
        assert args.entity_type == "apps"

    def test_list_operations_args_defaults(self) -> None:
        """Test ListOperationsArgs default entity_type."""
        args = ListOperationsArgs(entity_id="test-comp")
        assert args.entity_type == "components"

    def test_entities_list_args_optional_filter(self) -> None:
        """Test EntitiesListArgs filter is optional."""
        args = EntitiesListArgs()
        assert args.filter is None

        args_with_filter = EntitiesListArgs(filter="test")
        assert args_with_filter.filter == "test"
