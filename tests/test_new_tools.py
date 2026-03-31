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


class TestScriptsTools:
    """Tests for script management tools.

    Scripts are only supported on components and apps (not areas or functions).
    """

    SCRIPT_METADATA = {
        "id": "s1",
        "name": "diagnostics.py",
        "content_type": "application/octet-stream",
        "size": 1024,
    }

    SCRIPT_EXECUTION = {
        "id": "exec-1",
        "script_id": "s1",
        "status": "running",
        "started_at": "2026-01-01T00:00:00Z",
    }

    @respx.mock
    async def test_list_scripts(self, client: SovdClient) -> None:
        respx.get("http://test-sovd:8080/api/v1/components/motor/scripts").mock(
            return_value=httpx.Response(
                200,
                json={"items": [self.SCRIPT_METADATA]},
            )
        )
        result = await client.list_scripts("motor")
        assert len(result) == 1
        assert result[0]["id"] == "s1"
        await client.close()

    @respx.mock
    async def test_list_scripts_apps(self, client: SovdClient) -> None:
        respx.get("http://test-sovd:8080/api/v1/apps/my_node/scripts").mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        result = await client.list_scripts("my_node", "apps")
        assert result == []
        await client.close()

    @respx.mock
    async def test_get_script(self, client: SovdClient) -> None:
        respx.get("http://test-sovd:8080/api/v1/components/motor/scripts/s1").mock(
            return_value=httpx.Response(200, json=self.SCRIPT_METADATA)
        )
        result = await client.get_script("motor", "s1")
        assert result["id"] == "s1"
        assert result["name"] == "diagnostics.py"
        await client.close()

    @respx.mock
    async def test_upload_script(self, client: SovdClient) -> None:
        respx.post("http://test-sovd:8080/api/v1/components/motor/scripts").mock(
            return_value=httpx.Response(
                201,
                json={"id": "s2", "name": "uploaded.py"},
            )
        )
        result = await client.upload_script("motor", "print('hello')")
        assert result["id"] == "s2"
        await client.close()

    @respx.mock
    async def test_execute_script(self, client: SovdClient) -> None:
        # Generated client expects 202 Accepted for script execution start
        respx.post("http://test-sovd:8080/api/v1/components/motor/scripts/s1/executions").mock(
            return_value=httpx.Response(202, json=self.SCRIPT_EXECUTION)
        )
        result = await client.execute_script("motor", "s1", {"timeout": 30})
        assert result["id"] == "exec-1"
        assert result["status"] == "running"
        await client.close()

    @respx.mock
    async def test_get_script_execution(self, client: SovdClient) -> None:
        respx.get(
            "http://test-sovd:8080/api/v1/components/motor/scripts/s1/executions/exec-1"
        ).mock(return_value=httpx.Response(200, json=self.SCRIPT_EXECUTION))
        result = await client.get_script_execution("motor", "s1", "exec-1")
        assert result["id"] == "exec-1"
        assert result["status"] == "running"
        await client.close()

    @respx.mock
    async def test_control_script_execution(self, client: SovdClient) -> None:
        execution_stopped = {**self.SCRIPT_EXECUTION, "status": "stopped"}
        respx.put(
            "http://test-sovd:8080/api/v1/components/motor/scripts/s1/executions/exec-1"
        ).mock(return_value=httpx.Response(200, json=execution_stopped))
        result = await client.control_script_execution("motor", "s1", "exec-1", {"command": "stop"})
        assert result["status"] == "stopped"
        await client.close()

    @respx.mock
    async def test_delete_script(self, client: SovdClient) -> None:
        respx.delete("http://test-sovd:8080/api/v1/components/motor/scripts/s1").mock(
            return_value=httpx.Response(204)
        )
        result = await client.delete_script("motor", "s1")
        assert result == {}
        await client.close()


class TestLockingTools:
    """Tests for lock management tools.

    Locks are only supported on components and apps (not areas or functions).
    """

    # Lock model requires: id, lock_expiration (ISO 8601), owned (bool)
    LOCK_RESPONSE = {
        "id": "lock-1",
        "lock_expiration": "2026-01-01T01:00:00Z",
        "owned": True,
        "scopes": ["write"],
    }

    LOCK_REQUEST = {
        "id": "lock-1",
        "lock_expiration": "2026-01-01T01:00:00Z",
        "owned": True,
    }

    @respx.mock
    async def test_acquire_lock(self, client: SovdClient) -> None:
        respx.post("http://test-sovd:8080/api/v1/components/motor/locks").mock(
            return_value=httpx.Response(201, json=self.LOCK_RESPONSE)
        )
        result = await client.acquire_lock("motor", self.LOCK_REQUEST)
        assert result["id"] == "lock-1"
        assert result["owned"] is True
        await client.close()

    @respx.mock
    async def test_list_locks(self, client: SovdClient) -> None:
        respx.get("http://test-sovd:8080/api/v1/components/motor/locks").mock(
            return_value=httpx.Response(
                200,
                json={"items": [self.LOCK_RESPONSE]},
            )
        )
        result = await client.list_locks("motor")
        assert len(result) == 1
        assert result[0]["id"] == "lock-1"
        await client.close()

    @respx.mock
    async def test_get_lock(self, client: SovdClient) -> None:
        respx.get("http://test-sovd:8080/api/v1/components/motor/locks/lock-1").mock(
            return_value=httpx.Response(200, json=self.LOCK_RESPONSE)
        )
        result = await client.get_lock("motor", "lock-1")
        assert result["id"] == "lock-1"
        assert result["owned"] is True
        await client.close()

    @respx.mock
    async def test_extend_lock(self, client: SovdClient) -> None:
        extended_response = {
            **self.LOCK_RESPONSE,
            "lock_expiration": "2026-01-01T02:00:00Z",
        }
        extend_body = {
            "id": "lock-1",
            "lock_expiration": "2026-01-01T02:00:00Z",
            "owned": True,
        }
        respx.put("http://test-sovd:8080/api/v1/components/motor/locks/lock-1").mock(
            return_value=httpx.Response(200, json=extended_response)
        )
        result = await client.extend_lock("motor", "lock-1", extend_body)
        assert result["id"] == "lock-1"
        assert result["lock_expiration"] == "2026-01-01T02:00:00+00:00"
        await client.close()

    @respx.mock
    async def test_release_lock(self, client: SovdClient) -> None:
        respx.delete("http://test-sovd:8080/api/v1/components/motor/locks/lock-1").mock(
            return_value=httpx.Response(204)
        )
        result = await client.release_lock("motor", "lock-1")
        assert result == {}
        await client.close()


class TestSubscriptionsTools:
    """Tests for cyclic subscription management tools.

    Cyclic subscriptions are supported on components, apps, and functions (not areas).
    """

    # CyclicSubscription model requires: id, event_source, interval, observed_resource, protocol
    SUBSCRIPTION_RESPONSE = {
        "id": "sub-1",
        "event_source": "/events",
        "interval": "fast",
        "observed_resource": "/data/temperature",
        "protocol": "sse",
    }

    @respx.mock
    async def test_create_cyclic_subscription(self, client: SovdClient) -> None:
        respx.post("http://test-sovd:8080/api/v1/components/motor/cyclic-subscriptions").mock(
            return_value=httpx.Response(201, json=self.SUBSCRIPTION_RESPONSE)
        )
        result = await client.create_cyclic_subscription(
            "motor",
            {"resource": "/data/temperature", "interval": "fast", "duration": 60},
        )
        assert result["id"] == "sub-1"
        assert result["observed_resource"] == "/data/temperature"
        await client.close()

    @respx.mock
    async def test_list_cyclic_subscriptions(self, client: SovdClient) -> None:
        respx.get("http://test-sovd:8080/api/v1/components/motor/cyclic-subscriptions").mock(
            return_value=httpx.Response(200, json={"items": [self.SUBSCRIPTION_RESPONSE]})
        )
        result = await client.list_cyclic_subscriptions("motor")
        assert len(result) == 1
        assert result[0]["id"] == "sub-1"
        await client.close()

    @respx.mock
    async def test_get_cyclic_subscription(self, client: SovdClient) -> None:
        respx.get("http://test-sovd:8080/api/v1/components/motor/cyclic-subscriptions/sub-1").mock(
            return_value=httpx.Response(200, json=self.SUBSCRIPTION_RESPONSE)
        )
        result = await client.get_cyclic_subscription("motor", "sub-1")
        assert result["id"] == "sub-1"
        assert result["protocol"] == "sse"
        await client.close()

    @respx.mock
    async def test_update_cyclic_subscription(self, client: SovdClient) -> None:
        updated = {**self.SUBSCRIPTION_RESPONSE, "interval": "slow"}
        respx.put("http://test-sovd:8080/api/v1/components/motor/cyclic-subscriptions/sub-1").mock(
            return_value=httpx.Response(200, json=updated)
        )
        result = await client.update_cyclic_subscription(
            "motor",
            "sub-1",
            {**self.SUBSCRIPTION_RESPONSE, "interval": "slow"},
        )
        assert result["interval"] == "slow"
        await client.close()

    @respx.mock
    async def test_delete_cyclic_subscription(self, client: SovdClient) -> None:
        respx.delete(
            "http://test-sovd:8080/api/v1/components/motor/cyclic-subscriptions/sub-1"
        ).mock(return_value=httpx.Response(204))
        result = await client.delete_cyclic_subscription("motor", "sub-1")
        assert result == {}
        await client.close()


class TestUpdatesTools:
    """Tests for software update management tools.

    Updates are global endpoints (no entity type dispatch).
    URLs are /updates, /updates/{update_id}, etc.
    """

    UPDATE_RESPONSE = {
        "id": "upd-1",
        "name": "firmware-v2",
        "version": "2.0.0",
        "status": "pending",
    }

    UPDATE_STATUS_RESPONSE = {
        "status": "inProgress",
        "progress": 50,
    }

    @respx.mock
    async def test_list_updates(self, client: SovdClient) -> None:
        respx.get("http://test-sovd:8080/api/v1/updates").mock(
            return_value=httpx.Response(
                200,
                json={"items": [self.UPDATE_RESPONSE]},
            )
        )
        result = await client.list_updates()
        assert len(result) == 1
        assert result[0]["id"] == "upd-1"
        assert result[0]["name"] == "firmware-v2"
        await client.close()

    @respx.mock
    async def test_register_update(self, client: SovdClient) -> None:
        respx.post("http://test-sovd:8080/api/v1/updates").mock(
            return_value=httpx.Response(201, json=self.UPDATE_RESPONSE)
        )
        result = await client.register_update(
            {"name": "firmware-v2", "version": "2.0.0", "uri": "https://example.com/fw.bin"}
        )
        assert result["id"] == "upd-1"
        assert result["status"] == "pending"
        await client.close()

    @respx.mock
    async def test_get_update(self, client: SovdClient) -> None:
        respx.get("http://test-sovd:8080/api/v1/updates/upd-1").mock(
            return_value=httpx.Response(200, json=self.UPDATE_RESPONSE)
        )
        result = await client.get_update("upd-1")
        assert result["id"] == "upd-1"
        assert result["version"] == "2.0.0"
        await client.close()

    @respx.mock
    async def test_get_update_status(self, client: SovdClient) -> None:
        respx.get("http://test-sovd:8080/api/v1/updates/upd-1/status").mock(
            return_value=httpx.Response(200, json=self.UPDATE_STATUS_RESPONSE)
        )
        result = await client.get_update_status("upd-1")
        assert result["status"] == "inProgress"
        assert result["progress"] == 50
        await client.close()

    @respx.mock
    async def test_delete_update(self, client: SovdClient) -> None:
        respx.delete("http://test-sovd:8080/api/v1/updates/upd-1").mock(
            return_value=httpx.Response(204)
        )
        result = await client.delete_update("upd-1")
        assert result == {}
        await client.close()

    @respx.mock
    async def test_prepare_update(self, client: SovdClient) -> None:
        # prepare_update returns 202 Accepted; generated client returns None for 202
        respx.put("http://test-sovd:8080/api/v1/updates/upd-1/prepare").mock(
            return_value=httpx.Response(202)
        )
        result = await client.prepare_update("upd-1", {"verify_checksum": True})
        assert result == {}
        await client.close()

    @respx.mock
    async def test_execute_update(self, client: SovdClient) -> None:
        # execute_update returns 202 Accepted; generated client returns None for 202
        respx.put("http://test-sovd:8080/api/v1/updates/upd-1/execute").mock(
            return_value=httpx.Response(202)
        )
        result = await client.execute_update("upd-1", {"reboot_after": True})
        assert result == {}
        await client.close()

    @respx.mock
    async def test_automate_update(self, client: SovdClient) -> None:
        # automate_update returns 202 Accepted; generated client returns None for 202
        respx.put("http://test-sovd:8080/api/v1/updates/upd-1/automated").mock(
            return_value=httpx.Response(202)
        )
        result = await client.automate_update(
            "upd-1", {"verify_checksum": True, "reboot_after": True}
        )
        assert result == {}
        await client.close()


class TestDataDiscoveryTools:
    """Tests for data discovery tools (categories and groups)."""

    @respx.mock
    async def test_list_data_categories(self, client: SovdClient) -> None:
        respx.get("http://test-sovd:8080/api/v1/components/motor/data-categories").mock(
            return_value=httpx.Response(
                200,
                json={"items": ["topics", "parameters"]},
            )
        )
        result = await client.list_data_categories("motor")
        assert result == ["topics", "parameters"]
        await client.close()

    @respx.mock
    async def test_list_data_categories_apps(self, client: SovdClient) -> None:
        respx.get("http://test-sovd:8080/api/v1/apps/my_node/data-categories").mock(
            return_value=httpx.Response(200, json={"items": ["topics"]})
        )
        result = await client.list_data_categories("my_node", "apps")
        assert result == ["topics"]
        await client.close()

    @respx.mock
    async def test_list_data_groups(self, client: SovdClient) -> None:
        respx.get("http://test-sovd:8080/api/v1/components/motor/data-groups").mock(
            return_value=httpx.Response(
                200,
                json={"items": [{"id": "sensor_data", "name": "Sensor Data"}]},
            )
        )
        result = await client.list_data_groups("motor")
        assert len(result) == 1
        assert result[0]["id"] == "sensor_data"
        await client.close()

    @respx.mock
    async def test_list_data_groups_apps(self, client: SovdClient) -> None:
        respx.get("http://test-sovd:8080/api/v1/apps/my_node/data-groups").mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        result = await client.list_data_groups("my_node", "apps")
        assert result == []
        await client.close()


class TestBulkDataUploadDeleteTools:
    """Tests for bulk data upload and delete tools."""

    @respx.mock
    async def test_delete_bulk_data_item(self, client: SovdClient) -> None:
        respx.delete("http://test-sovd:8080/api/v1/apps/motor/bulk-data/rosbags/item-123").mock(
            return_value=httpx.Response(204)
        )
        result = await client.delete_bulk_data_item("motor", "rosbags", "item-123")
        assert result == {}
        await client.close()

    @respx.mock
    async def test_delete_bulk_data_item_components(self, client: SovdClient) -> None:
        respx.delete(
            "http://test-sovd:8080/api/v1/components/motor/bulk-data/rosbags/item-456"
        ).mock(return_value=httpx.Response(204))
        result = await client.delete_bulk_data_item("motor", "rosbags", "item-456", "components")
        assert result == {}
        await client.close()

    @respx.mock
    async def test_upload_bulk_data(self, client: SovdClient) -> None:
        respx.post("http://test-sovd:8080/api/v1/apps/motor/bulk-data/rosbags").mock(
            return_value=httpx.Response(
                201,
                json={
                    "id": "uploaded-1",
                    "name": "test.mcap",
                    "mimetype": "application/x-mcap",
                    "size": 42,
                },
            )
        )
        result = await client.upload_bulk_data("motor", "rosbags", b"fake-content", "test.mcap")
        assert result["id"] == "uploaded-1"
        assert result["name"] == "test.mcap"
        await client.close()

    @respx.mock
    async def test_upload_bulk_data_components(self, client: SovdClient) -> None:
        respx.post("http://test-sovd:8080/api/v1/components/motor/bulk-data/rosbags").mock(
            return_value=httpx.Response(
                201,
                json={"id": "uploaded-2", "name": "data.bin"},
            )
        )
        result = await client.upload_bulk_data(
            "motor", "rosbags", b"binary-data", "data.bin", "components"
        )
        assert result["id"] == "uploaded-2"
        await client.close()
