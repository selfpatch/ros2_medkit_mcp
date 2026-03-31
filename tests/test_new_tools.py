"""Tests for new MCP tools (v0.2.0-v0.4.0 features)."""

import httpx
import pytest
import respx

from ros2_medkit_mcp.client import SovdClient
from ros2_medkit_mcp.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        base_url="http://test-sovd:8080/api/v1",
        bearer_token=None,
        timeout_seconds=5.0,
    )


@pytest.fixture
def client(settings: Settings) -> SovdClient:
    return SovdClient(settings)


class TestLogsTools:
    @respx.mock
    async def test_list_logs(self, client: SovdClient) -> None:
        respx.get("http://test-sovd:8080/api/v1/components/motor/logs").mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "log-001",
                            "timestamp": "2026-01-01T00:00:00Z",
                            "severity": "info",
                            "message": "Started",
                        }
                    ]
                },
            )
        )
        result = await client.list_logs("motor")
        assert len(result) == 1
        assert result[0]["severity"] == "info"
        await client.close()

    @respx.mock
    async def test_list_logs_apps_entity_type(self, client: SovdClient) -> None:
        respx.get("http://test-sovd:8080/api/v1/apps/my_node/logs").mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        result = await client.list_logs("my_node", "apps")
        assert result == []
        await client.close()

    @respx.mock
    async def test_get_log_configuration(self, client: SovdClient) -> None:
        respx.get("http://test-sovd:8080/api/v1/components/motor/logs/configuration").mock(
            return_value=httpx.Response(
                200,
                json={"max_entries": 1000, "severity_filter": "info"},
            )
        )
        result = await client.get_log_configuration("motor")
        assert result["severity_filter"] == "info"
        assert result["max_entries"] == 1000
        await client.close()

    @respx.mock
    async def test_set_log_configuration(self, client: SovdClient) -> None:
        respx.put("http://test-sovd:8080/api/v1/components/motor/logs/configuration").mock(
            return_value=httpx.Response(204)
        )
        result = await client.set_log_configuration(
            "motor", {"max_entries": 500, "severity_filter": "debug"}
        )
        # 204 No Content returns empty dict
        assert result == {}
        await client.close()
