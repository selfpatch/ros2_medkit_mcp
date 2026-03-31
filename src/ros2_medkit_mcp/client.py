"""HTTP client wrapper for ros2_medkit SOVD API.

Delegates to the generated ros2-medkit-client package (MedkitClient)
while preserving the SovdClient interface used by mcp_app.py.

Note: response dicts use snake_case field names from the generated
client's to_dict() method (e.g. fault_code, environment_data),
not the gateway's camelCase JSON.
"""

import asyncio
import logging
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from typing import Any
from urllib.parse import quote

import httpx
from ros2_medkit_client import MedkitClient, MedkitError
from ros2_medkit_client.api import (
    bulk_data,
    configuration,
    data,
    discovery,
    faults,
    locking,
    logs,
    operations,
    scripts,
    server,
    subscriptions,
    triggers,
    updates,
)

from ros2_medkit_mcp.config import Settings

logger = logging.getLogger(__name__)


class SovdClientError(Exception):
    """Base exception for SOVD client errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.request_id = request_id


def _to_dict(obj: Any) -> Any:
    """Convert a generated model object to a dict, or pass through if already a dict/list."""
    if obj is None:
        return {}
    if isinstance(obj, dict | str | int | float | bool):
        return obj
    if isinstance(obj, list):
        return [_to_dict(item) for item in obj]
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    return obj


def _extract_items(result: Any) -> list[dict[str, Any]]:
    """Extract items list from a collection response."""
    d = _to_dict(result)
    if isinstance(d, list):
        return d
    if isinstance(d, dict):
        for key in (
            "items",
            "areas",
            "components",
            "apps",
            "functions",
            "faults",
            "configurations",
        ):
            if key in d:
                return d[key]
    return [d] if d else []


def _extract_filename(content_disposition: str) -> str | None:
    """Extract filename from Content-Disposition header."""
    if "filename=" not in content_disposition:
        return None
    match = re.search(r'filename="?([^"]+)"?', content_disposition)
    return match.group(1) if match else None


def _wrap_body_dict(api_func: Any, body_dict: dict[str, Any]) -> Any:
    """Wrap a raw dict as the body model expected by a generated API function.

    Generated functions require attrs model instances (with to_dict()), not raw dicts.
    Extracts the body type from the function's signature and creates it via from_dict().
    """
    import inspect

    sig = inspect.signature(api_func)
    body_param = sig.parameters.get("body")
    if body_param is not None and body_param.annotation is not inspect.Parameter.empty:
        body_cls = body_param.annotation
        if hasattr(body_cls, "from_dict"):
            return body_cls.from_dict(body_dict)
    return body_dict


def _validate_relative_uri(uri: str) -> None:
    """Reject absolute URLs to prevent SSRF."""
    if uri.startswith(("http://", "https://", "//")):
        raise SovdClientError(f"Absolute URLs not allowed: {uri}")


# Mapping of (entity_type, resource, method) -> generated function name
# entity_type is plural ("components"), singular is derived by stripping trailing "s"
_ENTITY_FUNC_MAP: dict[str, dict[str, dict[str, Any]]] = {
    "faults": {
        "list": {
            "components": faults.list_component_faults,
            "apps": faults.list_app_faults,
            "areas": faults.list_area_faults,
            "functions": faults.list_function_faults,
        },
        "get": {
            "components": faults.get_component_fault,
            "apps": faults.get_app_fault,
            "areas": faults.get_area_fault,
            "functions": faults.get_function_fault,
        },
        "clear": {
            "components": faults.clear_component_fault,
            "apps": faults.clear_app_fault,
            "areas": faults.clear_area_fault,
            "functions": faults.clear_function_fault,
        },
        "clear_all": {
            "components": faults.clear_all_component_faults,
            "apps": faults.clear_all_app_faults,
            "areas": faults.clear_all_area_faults,
            "functions": faults.clear_all_function_faults,
        },
    },
    "data": {
        "list": {
            "components": data.list_component_data,
            "apps": data.list_app_data,
            "areas": data.list_area_data,
            "functions": data.list_function_data,
        },
        "get": {
            "components": data.get_component_data_item,
            "apps": data.get_app_data_item,
            "areas": data.get_area_data_item,
            "functions": data.get_function_data_item,
        },
        "put": {
            "components": data.put_component_data_item,
            "apps": data.put_app_data_item,
            "areas": data.put_area_data_item,
            "functions": data.put_function_data_item,
        },
    },
    "operations": {
        "list": {
            "components": operations.list_component_operations,
            "apps": operations.list_app_operations,
            "areas": operations.list_area_operations,
            "functions": operations.list_function_operations,
        },
        "get": {
            "components": operations.get_component_operation,
            "apps": operations.get_app_operation,
            "areas": operations.get_area_operation,
            "functions": operations.get_function_operation,
        },
        "execute": {
            "components": operations.execute_component_operation,
            "apps": operations.execute_app_operation,
            "areas": operations.execute_area_operation,
            "functions": operations.execute_function_operation,
        },
        "list_executions": {
            "components": operations.list_component_executions,
            "apps": operations.list_app_executions,
            "areas": operations.list_area_executions,
            "functions": operations.list_function_executions,
        },
        "get_execution": {
            "components": operations.get_component_execution,
            "apps": operations.get_app_execution,
            "areas": operations.get_area_execution,
            "functions": operations.get_function_execution,
        },
        "update_execution": {
            "components": operations.update_component_execution,
            "apps": operations.update_app_execution,
            "areas": operations.update_area_execution,
            "functions": operations.update_function_execution,
        },
        "cancel_execution": {
            "components": operations.cancel_component_execution,
            "apps": operations.cancel_app_execution,
            "areas": operations.cancel_area_execution,
            "functions": operations.cancel_function_execution,
        },
    },
    "configurations": {
        "list": {
            "components": configuration.list_component_configurations,
            "apps": configuration.list_app_configurations,
            "areas": configuration.list_area_configurations,
            "functions": configuration.list_function_configurations,
        },
        "get": {
            "components": configuration.get_component_configuration,
            "apps": configuration.get_app_configuration,
            "areas": configuration.get_area_configuration,
            "functions": configuration.get_function_configuration,
        },
        "set": {
            "components": configuration.set_component_configuration,
            "apps": configuration.set_app_configuration,
            "areas": configuration.set_area_configuration,
            "functions": configuration.set_function_configuration,
        },
        "delete": {
            "components": configuration.delete_component_configuration,
            "apps": configuration.delete_app_configuration,
            "areas": configuration.delete_area_configuration,
            "functions": configuration.delete_function_configuration,
        },
        "delete_all": {
            "components": configuration.delete_all_component_configurations,
            "apps": configuration.delete_all_app_configurations,
            "areas": configuration.delete_all_area_configurations,
            "functions": configuration.delete_all_function_configurations,
        },
    },
    "data_categories": {
        "list": {
            "components": data.list_component_data_categories,
            "apps": data.list_app_data_categories,
            "areas": data.list_area_data_categories,
            "functions": data.list_function_data_categories,
        },
    },
    "data_groups": {
        "list": {
            "components": data.list_component_data_groups,
            "apps": data.list_app_data_groups,
            "areas": data.list_area_data_groups,
            "functions": data.list_function_data_groups,
        },
    },
    "bulk_data": {
        "list_categories": {
            "components": bulk_data.list_component_bulk_data_categories,
            "apps": bulk_data.list_app_bulk_data_categories,
            "areas": bulk_data.list_area_bulk_data_categories,
            "functions": bulk_data.list_function_bulk_data_categories,
        },
        "list": {
            "components": bulk_data.list_component_bulk_data_descriptors,
            "apps": bulk_data.list_app_bulk_data_descriptors,
            "areas": bulk_data.list_area_bulk_data_descriptors,
            "functions": bulk_data.list_function_bulk_data_descriptors,
        },
        "delete": {
            "components": bulk_data.delete_component_bulk_data,
            "apps": bulk_data.delete_app_bulk_data,
        },
        "upload": {
            "components": bulk_data.upload_component_bulk_data,
            "apps": bulk_data.upload_app_bulk_data,
        },
    },
    "logs": {
        "list": {
            "components": logs.list_component_logs,
            "apps": logs.list_app_logs,
            "areas": logs.list_area_logs,
            "functions": logs.list_function_logs,
        },
        "get_config": {
            "components": logs.get_component_log_configuration,
            "apps": logs.get_app_log_configuration,
            "areas": logs.get_area_log_configuration,
            "functions": logs.get_function_log_configuration,
        },
        "set_config": {
            "components": logs.set_component_log_configuration,
            "apps": logs.set_app_log_configuration,
            "areas": logs.set_area_log_configuration,
            "functions": logs.set_function_log_configuration,
        },
    },
    "triggers": {
        "list": {
            "components": triggers.list_component_triggers,
            "apps": triggers.list_app_triggers,
            "areas": triggers.list_area_triggers,
            "functions": triggers.list_function_triggers,
        },
        "get": {
            "components": triggers.get_component_trigger,
            "apps": triggers.get_app_trigger,
            "areas": triggers.get_area_trigger,
            "functions": triggers.get_function_trigger,
        },
        "create": {
            "components": triggers.create_component_trigger,
            "apps": triggers.create_app_trigger,
            "areas": triggers.create_area_trigger,
            "functions": triggers.create_function_trigger,
        },
        "update": {
            "components": triggers.update_component_trigger,
            "apps": triggers.update_app_trigger,
            "areas": triggers.update_area_trigger,
            "functions": triggers.update_function_trigger,
        },
        "delete": {
            "components": triggers.delete_component_trigger,
            "apps": triggers.delete_app_trigger,
            "areas": triggers.delete_area_trigger,
            "functions": triggers.delete_function_trigger,
        },
    },
    "scripts": {
        "list": {
            "components": scripts.list_component_scripts,
            "apps": scripts.list_app_scripts,
        },
        "get": {
            "components": scripts.get_component_script,
            "apps": scripts.get_app_script,
        },
        "upload": {
            "components": scripts.upload_component_script,
            "apps": scripts.upload_app_script,
        },
        "execute": {
            "components": scripts.start_component_script_execution,
            "apps": scripts.start_app_script_execution,
        },
        "get_execution": {
            "components": scripts.get_component_script_execution,
            "apps": scripts.get_app_script_execution,
        },
        "control_execution": {
            "components": scripts.control_component_script_execution,
            "apps": scripts.control_app_script_execution,
        },
        "delete": {
            "components": scripts.delete_component_script,
            "apps": scripts.delete_app_script,
        },
    },
    "locking": {
        "acquire": {
            "components": locking.acquire_component_lock,
            "apps": locking.acquire_app_lock,
        },
        "list": {
            "components": locking.list_component_locks,
            "apps": locking.list_app_locks,
        },
        "get": {
            "components": locking.get_component_lock,
            "apps": locking.get_app_lock,
        },
        "extend": {
            "components": locking.extend_component_lock,
            "apps": locking.extend_app_lock,
        },
        "release": {
            "components": locking.release_component_lock,
            "apps": locking.release_app_lock,
        },
    },
    "subscriptions": {
        "create": {
            "components": subscriptions.create_component_subscription,
            "apps": subscriptions.create_app_subscription,
            "functions": subscriptions.create_function_subscription,
        },
        "list": {
            "components": subscriptions.list_component_subscriptions,
            "apps": subscriptions.list_app_subscriptions,
            "functions": subscriptions.list_function_subscriptions,
        },
        "get": {
            "components": subscriptions.get_component_subscription,
            "apps": subscriptions.get_app_subscription,
            "functions": subscriptions.get_function_subscription,
        },
        "update": {
            "components": subscriptions.update_component_subscription,
            "apps": subscriptions.update_app_subscription,
            "functions": subscriptions.update_function_subscription,
        },
        "delete": {
            "components": subscriptions.delete_component_subscription,
            "apps": subscriptions.delete_app_subscription,
            "functions": subscriptions.delete_function_subscription,
        },
    },
}


# Validate all function references at import time
for _resource, _methods in _ENTITY_FUNC_MAP.items():
    for _method, _types in _methods.items():
        for _etype, _func in _types.items():
            if not hasattr(_func, "asyncio"):
                raise ImportError(
                    f"Generated API function {_resource}/{_method}/{_etype} "
                    f"({_func}) missing .asyncio attribute"
                )


def _entity_func(resource: str, method: str, entity_type: str) -> Any:
    """Look up the generated API function for a resource/method/entity_type combo."""
    resource_map = _ENTITY_FUNC_MAP.get(resource)
    if not resource_map:
        raise SovdClientError(f"Unknown resource: {resource}")
    method_map = resource_map.get(method)
    if not method_map:
        raise SovdClientError(f"Unknown method {method} for {resource}")
    func = method_map.get(entity_type)
    if not func:
        raise SovdClientError(f"No API function for {entity_type}/{resource}/{method}")
    return func.asyncio


def _entity_id_kwarg(entity_type: str) -> str:
    """Get the keyword argument name for entity ID based on type."""
    return f"{entity_type.removesuffix('s')}_id"


class SovdClient:
    """Async HTTP client for ros2_medkit SOVD API.

    Wraps the generated MedkitClient while preserving the interface
    expected by mcp_app.py.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._medkit: MedkitClient | None = None
        self._entered = False
        self._init_lock = asyncio.Lock()

    async def _ensure_client(self) -> MedkitClient:
        if self._medkit is not None:
            return self._medkit
        async with self._init_lock:
            if self._medkit is None:
                self._medkit = MedkitClient(
                    base_url=self._settings.base_url,
                    auth_token=self._settings.bearer_token,
                    timeout=self._settings.timeout_seconds,
                )
                await self._medkit.__aenter__()
                self._entered = True
        return self._medkit

    async def _httpx_client(self) -> httpx.AsyncClient:
        """Get the underlying httpx client for raw requests.

        Used for endpoints not covered by the generated client
        (fault snapshots, bulk-data HEAD/download).
        """
        client = await self._ensure_client()
        return client.http.get_async_httpx_client()

    async def close(self) -> None:
        if self._medkit is not None and self._entered:
            await self._medkit.__aexit__(None, None, None)
            self._medkit = None
            self._entered = False

    async def _call(self, api_func: Any, **kwargs: Any) -> Any:
        """Call a generated API function, converting errors to SovdClientError.

        Body dicts are auto-wrapped into the generated model expected by the
        API function (generated functions require attrs models with to_dict()).
        """
        if "body" in kwargs and isinstance(kwargs["body"], dict):
            kwargs["body"] = _wrap_body_dict(api_func, kwargs["body"])
        client = await self._ensure_client()
        try:
            result = await client.call(api_func, **kwargs)
            return _to_dict(result)
        except MedkitError as e:
            msg = f"[{e.code}] {e.message}" if e.code else str(e)
            raise SovdClientError(message=msg, status_code=e.status) from e
        except httpx.TimeoutException as e:
            raise SovdClientError(message=f"Request timed out: {e}") from e
        except httpx.RequestError as e:
            raise SovdClientError(message=f"Request failed: {e}") from e
        except (ValueError, KeyError) as e:
            raise SovdClientError(message=f"Failed to parse response: {e}") from e

    async def _call_void(self, api_func: Any, **kwargs: Any) -> dict[str, Any]:
        """Call a generated API function that may return 204/202 (None).

        Unlike _call(), this handles endpoints that return no body on success.
        The generated client returns None for 204/202, which MedkitClient.call()
        treats as an error. This method calls the function directly, treating
        None as success and checking for GenericError responses.
        """
        if "body" in kwargs and isinstance(kwargs["body"], dict):
            kwargs["body"] = _wrap_body_dict(api_func, kwargs["body"])
        client = await self._ensure_client()
        try:
            result = await api_func(client=client.http, **kwargs)
            if result is None:
                return {}
            # Check for GenericError (gateway returned 4xx/5xx)
            if hasattr(result, "error_code") and hasattr(result, "message"):
                error_code = getattr(result, "error_code", "unknown")
                message = getattr(result, "message", "Unknown error")
                raise SovdClientError(message=f"[{error_code}] {message}")
            return _to_dict(result)
        except httpx.TimeoutException as e:
            raise SovdClientError(message=f"Request timed out: {e}") from e
        except httpx.RequestError as e:
            raise SovdClientError(message=f"Request failed: {e}") from e
        except (ValueError, KeyError) as e:
            raise SovdClientError(message=f"Failed to parse response: {e}") from e

    async def _raw_request(self, method: str, path: str) -> Any:
        """Make a raw HTTP request for endpoints not in the generated client
        (fault snapshots). Path segments must be pre-encoded by the caller."""
        try:
            hc = await self._httpx_client()
            response = await hc.request(method, path)
            if not response.is_success:
                raise SovdClientError(
                    message=f"Gateway returned HTTP {response.status_code}",
                    status_code=response.status_code,
                )
            try:
                return response.json()
            except ValueError as e:
                raise SovdClientError(
                    message="Failed to decode JSON response from gateway",
                    status_code=response.status_code,
                ) from e
        except httpx.RequestError as e:
            raise SovdClientError(message=f"Request failed: {e}") from e

    # ==================== Server ====================

    async def get_version(self) -> dict[str, Any]:
        return await self._call(server.get_version_info.asyncio)

    async def get_health(self) -> dict[str, Any]:
        return await self._call(server.get_health.asyncio)

    # ==================== Discovery ====================

    async def list_entities(self) -> list[dict[str, Any]]:
        entities: list[dict[str, Any]] = []
        for list_fn in (self.list_areas, self.list_components, self.list_apps, self.list_functions):
            with suppress(SovdClientError):
                entities.extend(await list_fn())
        return entities

    async def list_areas(self) -> list[dict[str, Any]]:
        return _extract_items(await self._call(discovery.list_areas.asyncio))

    async def get_area(self, area_id: str) -> dict[str, Any]:
        return await self._call(discovery.get_area.asyncio, area_id=area_id)

    async def list_components(self) -> list[dict[str, Any]]:
        return _extract_items(await self._call(discovery.list_components.asyncio))

    async def get_component(self, component_id: str) -> dict[str, Any]:
        return await self._call(discovery.get_component.asyncio, component_id=component_id)

    async def list_apps(self) -> list[dict[str, Any]]:
        return _extract_items(await self._call(discovery.list_apps.asyncio))

    async def get_app(self, app_id: str) -> dict[str, Any]:
        return await self._call(discovery.get_app.asyncio, app_id=app_id)

    async def list_app_dependencies(self, app_id: str) -> list[dict[str, Any]]:
        return _extract_items(
            await self._call(discovery.list_app_dependencies.asyncio, app_id=app_id)
        )

    async def list_functions(self) -> list[dict[str, Any]]:
        return _extract_items(await self._call(discovery.list_functions.asyncio))

    async def get_function(self, function_id: str) -> dict[str, Any]:
        return await self._call(discovery.get_function.asyncio, function_id=function_id)

    async def list_function_hosts(self, function_id: str) -> list[dict[str, Any]]:
        return _extract_items(
            await self._call(discovery.list_function_hosts.asyncio, function_id=function_id)
        )

    async def get_entity(self, entity_id: str) -> dict[str, Any]:
        entities = await self.list_entities()
        for entity in entities:
            if entity.get("id") == entity_id:
                if entity.get("type") == "Component":
                    try:
                        component_data = await self.get_component_data(entity_id)
                        return {**entity, "data": component_data}
                    except SovdClientError:
                        pass
                return entity
        raise SovdClientError(message=f"Entity '{entity_id}' not found", status_code=404)

    # ==================== Area Relationships ====================

    async def list_area_components(self, area_id: str) -> list[dict[str, Any]]:
        return _extract_items(
            await self._call(discovery.list_area_components.asyncio, area_id=area_id)
        )

    async def list_area_subareas(self, area_id: str) -> list[dict[str, Any]]:
        return _extract_items(await self._call(discovery.list_subareas.asyncio, area_id=area_id))

    async def list_area_contains(self, area_id: str) -> list[dict[str, Any]]:
        return _extract_items(
            await self._call(discovery.list_area_contains.asyncio, area_id=area_id)
        )

    # ==================== Component Relationships ====================

    async def list_component_subcomponents(self, component_id: str) -> list[dict[str, Any]]:
        return _extract_items(
            await self._call(discovery.list_subcomponents.asyncio, component_id=component_id)
        )

    async def list_component_hosts(self, component_id: str) -> list[dict[str, Any]]:
        return _extract_items(
            await self._call(discovery.list_component_hosts.asyncio, component_id=component_id)
        )

    async def list_component_dependencies(self, component_id: str) -> list[dict[str, Any]]:
        return _extract_items(
            await self._call(
                discovery.list_component_dependencies.asyncio, component_id=component_id
            )
        )

    # ==================== Faults ====================

    async def list_faults(
        self, entity_id: str, entity_type: str = "components"
    ) -> list[dict[str, Any]]:
        fn = _entity_func("faults", "list", entity_type)
        return _extract_items(await self._call(fn, **{_entity_id_kwarg(entity_type): entity_id}))

    async def get_fault(
        self, entity_id: str, fault_id: str, entity_type: str = "components"
    ) -> dict[str, Any]:
        fn = _entity_func("faults", "get", entity_type)
        return await self._call(
            fn, **{_entity_id_kwarg(entity_type): entity_id, "fault_code": fault_id}
        )

    async def clear_fault(
        self, entity_id: str, fault_id: str, entity_type: str = "components"
    ) -> dict[str, Any]:
        fn = _entity_func("faults", "clear", entity_type)
        return await self._call(
            fn, **{_entity_id_kwarg(entity_type): entity_id, "fault_code": fault_id}
        )

    async def clear_all_faults(
        self, entity_id: str, entity_type: str = "components"
    ) -> dict[str, Any]:
        fn = _entity_func("faults", "clear_all", entity_type)
        return await self._call(fn, **{_entity_id_kwarg(entity_type): entity_id})

    async def list_all_faults(self) -> list[dict[str, Any]]:
        return _extract_items(await self._call(faults.list_all_faults.asyncio))

    async def get_fault_snapshots(
        self, entity_id: str, fault_code: str, entity_type: str = "components"
    ) -> dict[str, Any]:
        return await self._raw_request(
            "GET",
            f"/{quote(entity_type, safe='')}/{quote(entity_id, safe='')}"
            f"/faults/{quote(fault_code, safe='')}/snapshots",
        )

    async def get_system_fault_snapshots(self, fault_code: str) -> dict[str, Any]:
        return await self._raw_request("GET", f"/faults/{quote(fault_code, safe='')}/snapshots")

    # ==================== Data ====================

    async def get_component_data(
        self, entity_id: str, entity_type: str = "components"
    ) -> list[dict[str, Any]]:
        fn = _entity_func("data", "list", entity_type)
        return _extract_items(await self._call(fn, **{_entity_id_kwarg(entity_type): entity_id}))

    async def get_component_topic_data(
        self, entity_id: str, topic_name: str, entity_type: str = "components"
    ) -> dict[str, Any]:
        fn = _entity_func("data", "get", entity_type)
        return await self._call(
            fn, **{_entity_id_kwarg(entity_type): entity_id, "data_id": topic_name}
        )

    async def publish_to_topic(
        self,
        entity_id: str,
        topic_name: str,
        data: dict[str, Any],
        entity_type: str = "components",
    ) -> dict[str, Any]:
        fn = _entity_func("data", "put", entity_type)
        return await self._call(
            fn,
            **{_entity_id_kwarg(entity_type): entity_id, "data_id": topic_name, "body": data},
        )

    # ==================== Operations ====================

    async def list_operations(
        self, entity_id: str, entity_type: str = "components"
    ) -> list[dict[str, Any]]:
        fn = _entity_func("operations", "list", entity_type)
        return _extract_items(await self._call(fn, **{_entity_id_kwarg(entity_type): entity_id}))

    async def get_operation(
        self, entity_id: str, operation_name: str, entity_type: str = "components"
    ) -> dict[str, Any]:
        fn = _entity_func("operations", "get", entity_type)
        return await self._call(
            fn,
            **{_entity_id_kwarg(entity_type): entity_id, "operation_id": operation_name},
        )

    async def create_execution(
        self,
        entity_id: str,
        operation_name: str,
        request_data: dict[str, Any] | None = None,
        entity_type: str = "components",
    ) -> dict[str, Any]:
        fn = _entity_func("operations", "execute", entity_type)
        kwargs: dict[str, Any] = {
            _entity_id_kwarg(entity_type): entity_id,
            "operation_id": operation_name,
        }
        if request_data:
            kwargs["body"] = {"parameters": request_data}
        return await self._call(fn, **kwargs)

    async def list_executions(
        self, entity_id: str, operation_name: str, entity_type: str = "components"
    ) -> list[dict[str, Any]]:
        fn = _entity_func("operations", "list_executions", entity_type)
        return _extract_items(
            await self._call(
                fn,
                **{_entity_id_kwarg(entity_type): entity_id, "operation_id": operation_name},
            )
        )

    async def get_execution(
        self,
        entity_id: str,
        operation_name: str,
        execution_id: str,
        entity_type: str = "components",
    ) -> dict[str, Any]:
        fn = _entity_func("operations", "get_execution", entity_type)
        return await self._call(
            fn,
            **{
                _entity_id_kwarg(entity_type): entity_id,
                "operation_id": operation_name,
                "execution_id": execution_id,
            },
        )

    async def update_execution(
        self,
        entity_id: str,
        operation_name: str,
        execution_id: str,
        update_data: dict[str, Any],
        entity_type: str = "components",
    ) -> dict[str, Any]:
        fn = _entity_func("operations", "update_execution", entity_type)
        return await self._call(
            fn,
            **{
                _entity_id_kwarg(entity_type): entity_id,
                "operation_id": operation_name,
                "execution_id": execution_id,
                "body": update_data,
            },
        )

    async def cancel_execution(
        self,
        entity_id: str,
        operation_name: str,
        execution_id: str,
        entity_type: str = "components",
    ) -> dict[str, Any]:
        fn = _entity_func("operations", "cancel_execution", entity_type)
        return await self._call(
            fn,
            **{
                _entity_id_kwarg(entity_type): entity_id,
                "operation_id": operation_name,
                "execution_id": execution_id,
            },
        )

    # ==================== Configurations ====================

    async def list_configurations(
        self, entity_id: str, entity_type: str = "components"
    ) -> list[dict[str, Any]]:
        fn = _entity_func("configurations", "list", entity_type)
        return _extract_items(await self._call(fn, **{_entity_id_kwarg(entity_type): entity_id}))

    async def get_configuration(
        self, entity_id: str, param_name: str, entity_type: str = "components"
    ) -> dict[str, Any]:
        fn = _entity_func("configurations", "get", entity_type)
        return await self._call(
            fn,
            **{_entity_id_kwarg(entity_type): entity_id, "config_id": param_name},
        )

    async def set_configuration(
        self, entity_id: str, param_name: str, value: Any, entity_type: str = "components"
    ) -> dict[str, Any]:
        fn = _entity_func("configurations", "set", entity_type)
        return await self._call(
            fn,
            **{
                _entity_id_kwarg(entity_type): entity_id,
                "config_id": param_name,
                "body": {"data": value},
            },
        )

    async def delete_configuration(
        self, entity_id: str, param_name: str, entity_type: str = "components"
    ) -> dict[str, Any]:
        fn = _entity_func("configurations", "delete", entity_type)
        return await self._call(
            fn,
            **{_entity_id_kwarg(entity_type): entity_id, "config_id": param_name},
        )

    async def delete_all_configurations(
        self, entity_id: str, entity_type: str = "components"
    ) -> dict[str, Any]:
        fn = _entity_func("configurations", "delete_all", entity_type)
        return await self._call(fn, **{_entity_id_kwarg(entity_type): entity_id})

    # ==================== Data Discovery ====================

    async def list_data_categories(
        self, entity_id: str, entity_type: str = "components"
    ) -> list[dict[str, Any]]:
        fn = _entity_func("data_categories", "list", entity_type)
        return _extract_items(await self._call(fn, **{_entity_id_kwarg(entity_type): entity_id}))

    async def list_data_groups(
        self, entity_id: str, entity_type: str = "components"
    ) -> list[dict[str, Any]]:
        fn = _entity_func("data_groups", "list", entity_type)
        return _extract_items(await self._call(fn, **{_entity_id_kwarg(entity_type): entity_id}))

    # ==================== Bulk Data ====================

    async def list_bulk_data_categories(
        self, entity_id: str, entity_type: str = "apps"
    ) -> list[str]:
        fn = _entity_func("bulk_data", "list_categories", entity_type)
        result = await self._call(fn, **{_entity_id_kwarg(entity_type): entity_id})
        if isinstance(result, dict) and "items" in result:
            return result["items"]
        if isinstance(result, list):
            return result
        return []

    async def list_bulk_data(
        self, entity_id: str, category: str, entity_type: str = "apps"
    ) -> list[dict[str, Any]]:
        fn = _entity_func("bulk_data", "list", entity_type)
        return _extract_items(
            await self._call(
                fn,
                **{_entity_id_kwarg(entity_type): entity_id, "category_id": category},
            )
        )

    async def get_bulk_data_info(self, bulk_data_uri: str) -> dict[str, Any]:
        """Get metadata about a bulk-data item via HEAD request."""
        _validate_relative_uri(bulk_data_uri)
        hc = await self._httpx_client()
        try:
            response = await hc.head(bulk_data_uri)
        except httpx.RequestError as e:
            raise SovdClientError(message=f"Request failed: {e}") from e

        if not response.is_success:
            raise SovdClientError(
                message=f"Bulk data not found: {bulk_data_uri} (HTTP {response.status_code})",
                status_code=response.status_code,
            )

        return {
            "content_type": response.headers.get("Content-Type", "application/octet-stream"),
            "content_length": response.headers.get("Content-Length"),
            "filename": _extract_filename(response.headers.get("Content-Disposition", "")),
            "uri": bulk_data_uri,
        }

    async def download_bulk_data(self, bulk_data_uri: str) -> tuple[bytes, str | None]:
        """Download a bulk-data file."""
        _validate_relative_uri(bulk_data_uri)
        hc = await self._httpx_client()
        try:
            response = await hc.get(bulk_data_uri, timeout=httpx.Timeout(300.0))
        except httpx.RequestError as e:
            raise SovdClientError(message=f"Request failed: {e}") from e

        if not response.is_success:
            raise SovdClientError(
                message=f"Download failed: {response.status_code}",
                status_code=response.status_code,
            )

        return response.content, _extract_filename(response.headers.get("Content-Disposition", ""))

    async def delete_bulk_data_item(
        self,
        entity_id: str,
        category: str,
        item_id: str,
        entity_type: str = "apps",
    ) -> dict[str, Any]:
        fn = _entity_func("bulk_data", "delete", entity_type)
        return await self._call_void(
            fn,
            **{
                _entity_id_kwarg(entity_type): entity_id,
                "category_id": category,
                "file_id": item_id,
            },
        )

    async def upload_bulk_data(
        self,
        entity_id: str,
        category: str,
        file_content: bytes,
        filename: str,
        entity_type: str = "apps",
    ) -> dict[str, Any]:
        fn = _entity_func("bulk_data", "upload", entity_type)
        # upload expects a File object (binary upload), not a dict body.
        import io

        from ros2_medkit_client._generated.types import File

        file_obj = File(
            payload=io.BytesIO(file_content),
            file_name=filename,
            mime_type="application/octet-stream",
        )
        return await self._call_void(
            fn,
            **{
                _entity_id_kwarg(entity_type): entity_id,
                "category_id": category,
                "body": file_obj,
            },
        )

    # ==================== Logs ====================

    async def list_logs(
        self, entity_id: str, entity_type: str = "components"
    ) -> list[dict[str, Any]]:
        fn = _entity_func("logs", "list", entity_type)
        return _extract_items(await self._call(fn, **{_entity_id_kwarg(entity_type): entity_id}))

    async def get_log_configuration(
        self, entity_id: str, entity_type: str = "components"
    ) -> dict[str, Any]:
        fn = _entity_func("logs", "get_config", entity_type)
        return await self._call(fn, **{_entity_id_kwarg(entity_type): entity_id})

    async def set_log_configuration(
        self, entity_id: str, config: dict[str, Any], entity_type: str = "components"
    ) -> dict[str, Any]:
        fn = _entity_func("logs", "set_config", entity_type)
        return await self._call_void(
            fn, **{_entity_id_kwarg(entity_type): entity_id, "body": config}
        )

    # ==================== Triggers ====================

    async def list_triggers(
        self, entity_id: str, entity_type: str = "components"
    ) -> list[dict[str, Any]]:
        fn = _entity_func("triggers", "list", entity_type)
        return _extract_items(await self._call(fn, **{_entity_id_kwarg(entity_type): entity_id}))

    async def get_trigger(
        self, entity_id: str, trigger_id: str, entity_type: str = "components"
    ) -> dict[str, Any]:
        fn = _entity_func("triggers", "get", entity_type)
        return await self._call(
            fn, **{_entity_id_kwarg(entity_type): entity_id, "trigger_id": trigger_id}
        )

    async def create_trigger(
        self, entity_id: str, trigger_config: dict[str, Any], entity_type: str = "components"
    ) -> dict[str, Any]:
        fn = _entity_func("triggers", "create", entity_type)
        return await self._call(
            fn, **{_entity_id_kwarg(entity_type): entity_id, "body": trigger_config}
        )

    async def update_trigger(
        self,
        entity_id: str,
        trigger_id: str,
        trigger_config: dict[str, Any],
        entity_type: str = "components",
    ) -> dict[str, Any]:
        fn = _entity_func("triggers", "update", entity_type)
        return await self._call(
            fn,
            **{
                _entity_id_kwarg(entity_type): entity_id,
                "trigger_id": trigger_id,
                "body": trigger_config,
            },
        )

    async def delete_trigger(
        self, entity_id: str, trigger_id: str, entity_type: str = "components"
    ) -> dict[str, Any]:
        fn = _entity_func("triggers", "delete", entity_type)
        return await self._call_void(
            fn, **{_entity_id_kwarg(entity_type): entity_id, "trigger_id": trigger_id}
        )

    # ==================== Scripts ====================

    async def list_scripts(
        self, entity_id: str, entity_type: str = "components"
    ) -> list[dict[str, Any]]:
        fn = _entity_func("scripts", "list", entity_type)
        return _extract_items(await self._call(fn, **{_entity_id_kwarg(entity_type): entity_id}))

    async def get_script(
        self, entity_id: str, script_id: str, entity_type: str = "components"
    ) -> dict[str, Any]:
        fn = _entity_func("scripts", "get", entity_type)
        return await self._call(
            fn, **{_entity_id_kwarg(entity_type): entity_id, "script_id": script_id}
        )

    async def upload_script(
        self, entity_id: str, script_content: str, entity_type: str = "components"
    ) -> dict[str, Any]:
        fn = _entity_func("scripts", "upload", entity_type)
        # upload_script expects a File object (binary upload), not a dict body.
        # Build the File object from the script content string.
        import io

        from ros2_medkit_client._generated.types import File

        file_obj = File(
            payload=io.BytesIO(script_content.encode("utf-8")),
            file_name="script.py",
            mime_type="application/octet-stream",
        )
        return await self._call_void(
            fn, **{_entity_id_kwarg(entity_type): entity_id, "body": file_obj}
        )

    async def execute_script(
        self,
        entity_id: str,
        script_id: str,
        params: dict[str, Any] | None = None,
        entity_type: str = "components",
    ) -> dict[str, Any]:
        fn = _entity_func("scripts", "execute", entity_type)
        kwargs: dict[str, Any] = {
            _entity_id_kwarg(entity_type): entity_id,
            "script_id": script_id,
            "body": params if params else {},
        }
        return await self._call(fn, **kwargs)

    async def get_script_execution(
        self,
        entity_id: str,
        script_id: str,
        execution_id: str,
        entity_type: str = "components",
    ) -> dict[str, Any]:
        fn = _entity_func("scripts", "get_execution", entity_type)
        return await self._call(
            fn,
            **{
                _entity_id_kwarg(entity_type): entity_id,
                "script_id": script_id,
                "execution_id": execution_id,
            },
        )

    async def control_script_execution(
        self,
        entity_id: str,
        script_id: str,
        execution_id: str,
        action: dict[str, Any],
        entity_type: str = "components",
    ) -> dict[str, Any]:
        fn = _entity_func("scripts", "control_execution", entity_type)
        return await self._call(
            fn,
            **{
                _entity_id_kwarg(entity_type): entity_id,
                "script_id": script_id,
                "execution_id": execution_id,
                "body": action,
            },
        )

    async def delete_script(
        self, entity_id: str, script_id: str, entity_type: str = "components"
    ) -> dict[str, Any]:
        fn = _entity_func("scripts", "delete", entity_type)
        return await self._call_void(
            fn, **{_entity_id_kwarg(entity_type): entity_id, "script_id": script_id}
        )

    # ==================== Locking ====================

    async def acquire_lock(
        self, entity_id: str, lock_config: dict[str, Any], entity_type: str = "components"
    ) -> dict[str, Any]:
        fn = _entity_func("locking", "acquire", entity_type)
        return await self._call(
            fn, **{_entity_id_kwarg(entity_type): entity_id, "body": lock_config}
        )

    async def list_locks(
        self, entity_id: str, entity_type: str = "components"
    ) -> list[dict[str, Any]]:
        fn = _entity_func("locking", "list", entity_type)
        return _extract_items(await self._call(fn, **{_entity_id_kwarg(entity_type): entity_id}))

    async def get_lock(
        self, entity_id: str, lock_id: str, entity_type: str = "components"
    ) -> dict[str, Any]:
        fn = _entity_func("locking", "get", entity_type)
        return await self._call(
            fn, **{_entity_id_kwarg(entity_type): entity_id, "lock_id": lock_id}
        )

    async def extend_lock(
        self,
        entity_id: str,
        lock_id: str,
        lock_config: dict[str, Any],
        entity_type: str = "components",
    ) -> dict[str, Any]:
        fn = _entity_func("locking", "extend", entity_type)
        return await self._call(
            fn,
            **{
                _entity_id_kwarg(entity_type): entity_id,
                "lock_id": lock_id,
                "body": lock_config,
            },
        )

    async def release_lock(
        self, entity_id: str, lock_id: str, entity_type: str = "components"
    ) -> dict[str, Any]:
        fn = _entity_func("locking", "release", entity_type)
        return await self._call_void(
            fn, **{_entity_id_kwarg(entity_type): entity_id, "lock_id": lock_id}
        )

    # ==================== Cyclic Subscriptions ====================

    async def create_cyclic_subscription(
        self,
        entity_id: str,
        sub_config: dict[str, Any],
        entity_type: str = "components",
    ) -> dict[str, Any]:
        fn = _entity_func("subscriptions", "create", entity_type)
        return await self._call(
            fn, **{_entity_id_kwarg(entity_type): entity_id, "body": sub_config}
        )

    async def list_cyclic_subscriptions(
        self, entity_id: str, entity_type: str = "components"
    ) -> list[dict[str, Any]]:
        fn = _entity_func("subscriptions", "list", entity_type)
        return _extract_items(await self._call(fn, **{_entity_id_kwarg(entity_type): entity_id}))

    async def get_cyclic_subscription(
        self, entity_id: str, subscription_id: str, entity_type: str = "components"
    ) -> dict[str, Any]:
        fn = _entity_func("subscriptions", "get", entity_type)
        return await self._call(
            fn,
            **{_entity_id_kwarg(entity_type): entity_id, "subscription_id": subscription_id},
        )

    async def update_cyclic_subscription(
        self,
        entity_id: str,
        subscription_id: str,
        sub_config: dict[str, Any],
        entity_type: str = "components",
    ) -> dict[str, Any]:
        fn = _entity_func("subscriptions", "update", entity_type)
        return await self._call(
            fn,
            **{
                _entity_id_kwarg(entity_type): entity_id,
                "subscription_id": subscription_id,
                "body": sub_config,
            },
        )

    async def delete_cyclic_subscription(
        self, entity_id: str, subscription_id: str, entity_type: str = "components"
    ) -> dict[str, Any]:
        fn = _entity_func("subscriptions", "delete", entity_type)
        return await self._call_void(
            fn,
            **{
                _entity_id_kwarg(entity_type): entity_id,
                "subscription_id": subscription_id,
            },
        )

    # ==================== Software Updates ====================

    async def list_updates(self) -> list[dict[str, Any]]:
        return _extract_items(await self._call(updates.list_updates.asyncio))

    async def register_update(self, update_config: dict[str, Any]) -> dict[str, Any]:
        return await self._call(updates.register_update.asyncio, body=update_config)

    async def get_update(self, update_id: str) -> dict[str, Any]:
        return await self._call(updates.get_update.asyncio, update_id=update_id)

    async def get_update_status(self, update_id: str) -> dict[str, Any]:
        return await self._call(updates.get_update_status.asyncio, update_id=update_id)

    async def prepare_update(self, update_id: str, config: dict[str, Any]) -> dict[str, Any]:
        # prepare_update returns 202 Accepted on success.
        # The generated client returns None for 202, which MedkitClient.call()
        # treats as an error. Call the function directly and treat None as success.
        return await self._call_update_action(
            updates.prepare_update.asyncio, update_id=update_id, body=config
        )

    async def execute_update(self, update_id: str, config: dict[str, Any]) -> dict[str, Any]:
        # execute_update returns 202 Accepted on success.
        return await self._call_update_action(
            updates.execute_update.asyncio, update_id=update_id, body=config
        )

    async def automate_update(self, update_id: str, config: dict[str, Any]) -> dict[str, Any]:
        # automate_update returns 202 Accepted on success.
        return await self._call_update_action(
            updates.automate_update.asyncio, update_id=update_id, body=config
        )

    async def _call_update_action(self, api_func: Any, **kwargs: Any) -> dict[str, Any]:
        """Call a generated update action function that returns 202 with None body."""
        return await self._call_void(api_func, **kwargs)

    async def delete_update(self, update_id: str) -> dict[str, Any]:
        return await self._call_void(updates.delete_update.asyncio, update_id=update_id)


@asynccontextmanager
async def create_client(settings: Settings) -> AsyncIterator[SovdClient]:
    """Create and manage SOVD client lifecycle."""
    client = SovdClient(settings)
    try:
        yield client
    finally:
        await client.close()
