"""Tests for MCP tools with mocked HTTP responses."""

import httpx
import pytest
import respx
from pydantic import ValidationError

from ros2_medkit_mcp.client import SovdClient, SovdClientError
from ros2_medkit_mcp.config import Settings
from ros2_medkit_mcp.models import filter_entities


@pytest.fixture
def settings() -> Settings:
    """Create test settings."""
    return Settings(
        base_url="http://test-sovd:8080/api/v1",
        bearer_token=None,
        timeout_seconds=5.0,
    )


@pytest.fixture
def settings_with_auth() -> Settings:
    """Create test settings with authentication."""
    return Settings(
        base_url="http://test-sovd:8080/api/v1",
        bearer_token="test-token-123",
        timeout_seconds=5.0,
    )


@pytest.fixture
def client(settings: Settings) -> SovdClient:
    """Create test client."""
    return SovdClient(settings)


@pytest.fixture
def client_with_auth(settings_with_auth: Settings) -> SovdClient:
    """Create test client with authentication."""
    return SovdClient(settings_with_auth)


class TestSovdClient:
    """Tests for SovdClient."""

    @respx.mock
    async def test_get_version_success(self, client: SovdClient) -> None:
        """Test successful version retrieval."""
        respx.get("http://test-sovd:8080/api/v1/version-info").mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "base_uri": "/api/v1",
                            "version": "1.0.0",
                            "api_name": "ros2_medkit",
                            "api_version": "1.0.0",
                        }
                    ]
                },
            )
        )

        result = await client.get_version()

        assert result["items"][0]["version"] == "1.0.0"
        assert result["items"][0]["api_name"] == "ros2_medkit"
        await client.close()

    @respx.mock
    async def test_get_version_with_request_id(self, client: SovdClient) -> None:
        """Test version retrieval with request ID in response headers."""
        respx.get("http://test-sovd:8080/api/v1/version-info").mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "base_uri": "/api/v1",
                            "version": "1.0.0",
                            "api_name": "test",
                            "api_version": "1.0.0",
                        }
                    ]
                },
                headers={"X-Request-ID": "req-123"},
            )
        )

        result = await client.get_version()

        assert result["items"][0]["version"] == "1.0.0"
        await client.close()

    @respx.mock
    async def test_get_version_error(self, client: SovdClient) -> None:
        """Test version retrieval with error response."""
        respx.get("http://test-sovd:8080/api/v1/version-info").mock(
            return_value=httpx.Response(
                500,
                json={
                    "error_code": "internal-error",
                    "message": "Internal Server Error",
                },
            )
        )

        with pytest.raises(SovdClientError):
            await client.get_version()

        await client.close()

    @respx.mock
    async def test_list_entities_success(self, client: SovdClient) -> None:
        """Test successful entities listing."""
        respx.get("http://test-sovd:8080/api/v1/areas").mock(
            return_value=httpx.Response(
                200, json={"items": [{"id": "powertrain", "name": "powertrain", "type": "Area"}]}
            )
        )
        respx.get("http://test-sovd:8080/api/v1/components").mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [
                        {"id": "temp_sensor", "name": "Temperature Sensor", "type": "Component"},
                        {"id": "rpm_sensor", "name": "RPM Sensor", "type": "Component"},
                    ]
                },
            )
        )
        respx.get("http://test-sovd:8080/api/v1/apps").mock(
            return_value=httpx.Response(
                200, json={"items": [{"id": "node_1", "name": "node_1", "type": "App"}]}
            )
        )
        respx.get("http://test-sovd:8080/api/v1/functions").mock(
            return_value=httpx.Response(200, json={"items": []})
        )

        result = await client.list_entities()

        assert len(result) == 4  # 1 area + 2 components + 1 app
        await client.close()

    @respx.mock
    async def test_list_entities_wrapped_response(self, client: SovdClient) -> None:
        """Test entities listing when some endpoints return errors."""
        respx.get("http://test-sovd:8080/api/v1/areas").mock(
            return_value=httpx.Response(
                200, json={"items": [{"id": "powertrain", "name": "powertrain", "type": "Area"}]}
            )
        )
        respx.get("http://test-sovd:8080/api/v1/components").mock(
            return_value=httpx.Response(
                200,
                json={"items": [{"id": "temp_sensor", "name": "temp_sensor", "type": "Component"}]},
            )
        )
        # Apps and functions return 404 - should be caught
        respx.get("http://test-sovd:8080/api/v1/apps").mock(
            return_value=httpx.Response(
                404, json={"error_code": "not-found", "message": "Not Found"}
            )
        )
        respx.get("http://test-sovd:8080/api/v1/functions").mock(
            return_value=httpx.Response(
                404, json={"error_code": "not-found", "message": "Not Found"}
            )
        )

        result = await client.list_entities()

        assert len(result) == 2
        await client.close()

    @respx.mock
    async def test_get_entity_success(self, client: SovdClient) -> None:
        """Test successful entity retrieval."""
        respx.get("http://test-sovd:8080/api/v1/areas").mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        respx.get("http://test-sovd:8080/api/v1/components").mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "temp_sensor",
                            "name": "Temperature Sensor",
                            "type": "Component",
                        }
                    ]
                },
            )
        )
        respx.get("http://test-sovd:8080/api/v1/apps").mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        respx.get("http://test-sovd:8080/api/v1/functions").mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        respx.get("http://test-sovd:8080/api/v1/components/temp_sensor/data").mock(
            return_value=httpx.Response(
                200, json={"items": [{"id": "temperature", "name": "temperature"}]}
            )
        )

        result = await client.get_entity("temp_sensor")

        assert result["id"] == "temp_sensor"
        assert "data" in result
        await client.close()

    @respx.mock
    async def test_get_entity_not_found(self, client: SovdClient) -> None:
        """Test entity retrieval when entity does not exist."""
        respx.get("http://test-sovd:8080/api/v1/areas").mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        respx.get("http://test-sovd:8080/api/v1/components").mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        respx.get("http://test-sovd:8080/api/v1/apps").mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        respx.get("http://test-sovd:8080/api/v1/functions").mock(
            return_value=httpx.Response(200, json={"items": []})
        )

        with pytest.raises(SovdClientError) as exc_info:
            await client.get_entity("nonexistent")

        assert exc_info.value.status_code == 404
        await client.close()

    @respx.mock
    async def test_list_faults_success(self, client: SovdClient) -> None:
        """Test successful faults listing."""
        fault_items = [
            {"fault_code": "fault-1", "severity": "high", "status": "active"},
            {"fault_code": "fault-2", "severity": "low", "status": "active"},
        ]
        respx.get("http://test-sovd:8080/api/v1/components/test-component/faults").mock(
            return_value=httpx.Response(200, json={"items": fault_items})
        )

        result = await client.list_faults("test-component")

        assert len(result) == 2
        assert result[0]["fault_code"] == "fault-1"
        await client.close()

    @respx.mock
    async def test_list_faults_different_component(self, client: SovdClient) -> None:
        """Test faults listing for different component."""
        respx.get("http://test-sovd:8080/api/v1/components/other-component/faults").mock(
            return_value=httpx.Response(
                200,
                json={"items": [{"fault_code": "fault-1", "severity": "high", "status": "active"}]},
            )
        )

        result = await client.list_faults("other-component")

        assert len(result) == 1
        assert result[0]["fault_code"] == "fault-1"
        await client.close()

    @respx.mock
    async def test_list_faults_wrapped_response(self, client: SovdClient) -> None:
        """Test faults listing with items wrapper."""
        faults = [{"fault_code": "fault-1", "severity": "high", "status": "active"}]
        respx.get("http://test-sovd:8080/api/v1/components/test-component/faults").mock(
            return_value=httpx.Response(200, json={"items": faults})
        )

        result = await client.list_faults("test-component")

        assert len(result) == 1
        assert result[0]["fault_code"] == "fault-1"
        await client.close()

    @respx.mock
    async def test_authentication_header(self, client_with_auth: SovdClient) -> None:
        """Test that authentication header is sent when configured."""
        route = respx.get("http://test-sovd:8080/api/v1/version-info").mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "base_uri": "/api/v1",
                            "version": "1.0.0",
                            "api_name": "test",
                            "api_version": "1.0.0",
                        }
                    ]
                },
            )
        )

        await client_with_auth.get_version()

        auth_header = route.calls[0].request.headers.get("Authorization")
        assert auth_header == "Bearer test-token-123"
        await client_with_auth.close()

    @respx.mock
    async def test_timeout_handling(self, client: SovdClient) -> None:
        """Test timeout error handling."""
        respx.get("http://test-sovd:8080/api/v1/version-info").mock(
            side_effect=httpx.ReadTimeout("Connection timed out")
        )

        with pytest.raises(SovdClientError, match="timed out"):
            await client.get_version()

        await client.close()

    @respx.mock
    async def test_non_json_response(self, client: SovdClient) -> None:
        """Test handling of non-JSON responses with 2xx status."""
        respx.get("http://test-sovd:8080/api/v1/version-info").mock(
            return_value=httpx.Response(
                200, text="<html>not json</html>", headers={"Content-Type": "text/html"}
            )
        )

        with pytest.raises((SovdClientError, Exception)):
            await client.get_version()

        await client.close()

    @respx.mock
    async def test_connection_error_handling(self, client: SovdClient) -> None:
        """Test connection error handling."""
        respx.get("http://test-sovd:8080/api/v1/version-info").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        with pytest.raises(SovdClientError, match="failed"):
            await client.get_version()

        await client.close()


class TestFilterEntities:
    """Tests for entity filtering logic."""

    def test_filter_by_id(self) -> None:
        """Test filtering entities by ID."""
        entities = [
            {"id": "robot-arm", "name": "Arm Module"},
            {"id": "sensor-unit", "name": "Sensor Unit"},
        ]

        result = filter_entities(entities, "robot")

        assert len(result) == 1
        assert result[0]["id"] == "robot-arm"

    def test_filter_by_name(self) -> None:
        """Test filtering entities by name."""
        entities = [
            {"id": "entity-1", "name": "Robot Arm"},
            {"id": "entity-2", "name": "Sensor Module"},
        ]

        result = filter_entities(entities, "sensor")

        assert len(result) == 1
        assert result[0]["id"] == "entity-2"

    def test_filter_case_insensitive(self) -> None:
        """Test case-insensitive filtering."""
        entities = [
            {"id": "ROBOT-ARM", "name": "Arm"},
            {"id": "sensor", "name": "Sensor"},
        ]

        result = filter_entities(entities, "robot")

        assert len(result) == 1
        assert result[0]["id"] == "ROBOT-ARM"

    def test_filter_no_match(self) -> None:
        """Test filtering with no matches."""
        entities = [{"id": "entity-1", "name": "Robot Arm"}]

        result = filter_entities(entities, "nonexistent")

        assert result == []

    def test_filter_none_returns_all(self) -> None:
        """Test that None filter returns all entities."""
        entities = [
            {"id": "entity-1", "name": "Robot Arm"},
            {"id": "entity-2", "name": "Sensor Module"},
        ]

        result = filter_entities(entities, None)

        assert result == entities

    def test_filter_empty_string_returns_all(self) -> None:
        """Test that empty string filter returns all entities."""
        entities = [{"id": "entity-1", "name": "Robot Arm"}]

        result = filter_entities(entities, "")

        assert result == entities

    def test_filter_missing_fields(self) -> None:
        """Test filtering handles missing id/name fields."""
        entities = [
            {"id": "entity-1"},  # No name
            {"name": "Robot Arm"},  # No id
            {"other": "data"},  # Neither
        ]

        result = filter_entities(entities, "entity")

        assert len(result) == 1
        assert result[0]["id"] == "entity-1"


class TestConfigSettings:
    """Tests for configuration settings."""

    def test_default_settings(self) -> None:
        """Test default settings values."""
        settings = Settings()

        assert settings.base_url == "http://localhost:8080/api/v1"
        assert settings.bearer_token is None
        assert settings.timeout_seconds == 30.0

    def test_custom_settings(self) -> None:
        """Test custom settings values."""
        settings = Settings(
            base_url="http://custom:9000",
            bearer_token="my-token",
            timeout_seconds=60.0,
        )

        assert settings.base_url == "http://custom:9000"
        assert settings.bearer_token == "my-token"
        assert settings.timeout_seconds == 60.0

    def test_settings_immutable(self) -> None:
        """Test that settings are immutable."""
        settings = Settings()

        with pytest.raises(ValidationError):
            settings.base_url = "http://new-url:8080"

    def test_timeout_empty_env_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empty timeout env should fall back to default 30s."""
        monkeypatch.setenv("ROS2_MEDKIT_TIMEOUT_S", "")

        settings = Settings()

        assert settings.timeout_seconds == 30.0
        monkeypatch.delenv("ROS2_MEDKIT_TIMEOUT_S", raising=False)
