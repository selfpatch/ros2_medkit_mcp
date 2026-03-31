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


class TestTriggersTools:
    """Tests for trigger management tools.

    The generated client models (Trigger, TriggerList, TriggerCreateRequest,
    TriggerUpdateRequest) require specific SOVD-compliant fields in request/response
    bodies. Mock responses must include all required fields for the model's from_dict()
    to succeed.
    """

    # Reusable trigger response matching the generated Trigger model schema
    TRIGGER_RESPONSE = {
        "id": "t1",
        "event_source": "/events",
        "observed_resource": "/data/temperature",
        "protocol": "sse",
        "status": "active",
        "trigger_condition": {"condition_type": "on_change"},
    }

    @respx.mock
    async def test_list_triggers(self, client: SovdClient) -> None:
        respx.get("http://test-sovd:8080/api/v1/components/motor/triggers").mock(
            return_value=httpx.Response(
                200,
                json={"items": [self.TRIGGER_RESPONSE]},
            )
        )
        result = await client.list_triggers("motor")
        assert len(result) == 1
        assert result[0]["id"] == "t1"
        assert result[0]["observed_resource"] == "/data/temperature"
        await client.close()

    @respx.mock
    async def test_get_trigger(self, client: SovdClient) -> None:
        respx.get("http://test-sovd:8080/api/v1/components/motor/triggers/t1").mock(
            return_value=httpx.Response(200, json=self.TRIGGER_RESPONSE)
        )
        result = await client.get_trigger("motor", "t1")
        assert result["id"] == "t1"
        assert result["status"] == "active"
        await client.close()

    @respx.mock
    async def test_create_trigger(self, client: SovdClient) -> None:
        respx.post("http://test-sovd:8080/api/v1/components/motor/triggers").mock(
            return_value=httpx.Response(201, json=self.TRIGGER_RESPONSE)
        )
        result = await client.create_trigger(
            "motor",
            {
                "resource": "/data/temperature",
                "trigger_condition": {"condition_type": "on_change"},
            },
        )
        assert result["id"] == "t1"
        await client.close()

    @respx.mock
    async def test_update_trigger(self, client: SovdClient) -> None:
        respx.put("http://test-sovd:8080/api/v1/components/motor/triggers/t1").mock(
            return_value=httpx.Response(200, json=self.TRIGGER_RESPONSE)
        )
        result = await client.update_trigger("motor", "t1", {"lifetime": 120})
        assert result["id"] == "t1"
        await client.close()

    @respx.mock
    async def test_delete_trigger(self, client: SovdClient) -> None:
        respx.delete("http://test-sovd:8080/api/v1/components/motor/triggers/t1").mock(
            return_value=httpx.Response(204)
        )
        result = await client.delete_trigger("motor", "t1")
        assert result == {}
        await client.close()
