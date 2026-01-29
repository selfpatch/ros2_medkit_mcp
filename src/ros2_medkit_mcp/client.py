"""HTTP client wrapper for ros2_medkit SOVD API.

Provides async HTTP client with proper lifecycle management,
authentication, and error handling.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx

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


class SovdClient:
    """Async HTTP client for ros2_medkit SOVD API.

    Manages HTTP connection lifecycle and provides typed methods
    for each API endpoint.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize the client with settings.

        Args:
            settings: Application settings containing base URL, auth, timeout.
        """
        self._settings = settings
        self._client: httpx.AsyncClient | None = None

    def _build_headers(self) -> dict[str, str]:
        """Build HTTP headers including authentication if configured.

        Returns:
            Dictionary of HTTP headers.
        """
        headers: dict[str, str] = {
            "Accept": "application/json",
            "User-Agent": "ros2_medkit_mcp/0.1.0",
        }
        if self._settings.bearer_token:
            headers["Authorization"] = f"Bearer {self._settings.bearer_token}"
        return headers

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure HTTP client is initialized.

        Returns:
            The initialized async HTTP client.
        """
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._settings.base_url.rstrip("/"),
                headers=self._build_headers(),
                timeout=httpx.Timeout(self._settings.timeout_seconds),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _extract_request_id(self, response: httpx.Response) -> str | None:
        """Extract request ID from response headers.

        Args:
            response: HTTP response to inspect.

        Returns:
            Request ID if present, None otherwise.
        """
        for header in ("X-Request-ID", "X-Request-Id", "Request-Id", "request-id"):
            if header in response.headers:
                return response.headers[header]
        return None

    def _log_response(
        self,
        method: str,
        path: str,
        response: httpx.Response,
        request_id: str | None,
    ) -> None:
        """Log HTTP response details.

        Args:
            method: HTTP method used.
            path: Request path.
            response: HTTP response received.
            request_id: Request ID if present.
        """
        log_extra = {"status": response.status_code, "method": method, "path": path}
        if request_id:
            log_extra["request_id"] = request_id

        if response.is_success:
            logger.debug("HTTP request succeeded", extra=log_extra)
        else:
            logger.warning("HTTP request failed", extra=log_extra)

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        """Make an HTTP request and return JSON response.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: API endpoint path.
            params: Optional query parameters.
            json_body: Optional JSON body for POST/PUT requests.

        Returns:
            Parsed JSON response.

        Raises:
            SovdClientError: If request fails or returns non-2xx status.
        """
        client = await self._ensure_client()

        try:
            response = await client.request(method, path, params=params, json=json_body)
            request_id = self._extract_request_id(response)
            self._log_response(method, path, response, request_id)

            if not response.is_success:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                raise SovdClientError(
                    message=error_msg,
                    status_code=response.status_code,
                    request_id=request_id,
                )

            try:
                return response.json()
            except ValueError as e:
                error_msg = "Invalid JSON in response body"
                raise SovdClientError(
                    message=error_msg,
                    status_code=response.status_code,
                    request_id=request_id,
                ) from e

        except httpx.RequestError as e:
            logger.error("HTTP request error: %s", e)
            raise SovdClientError(message=f"Request failed: {e}") from e

    async def get_version(self) -> dict[str, Any]:
        """Get SOVD API version information.

        Returns:
            Version information as dictionary.
        """
        return await self._request("GET", "/version-info")

    async def get_health(self) -> dict[str, Any]:
        """Get health status of the gateway.

        Returns:
            Health status as dictionary.
        """
        return await self._request("GET", "/health")

    async def list_entities(self) -> list[dict[str, Any]]:
        """List all SOVD entities (areas, components, apps, and functions combined).

        Returns:
            List of entity dictionaries.
        """
        entities = []

        # Fetch areas
        try:
            areas_result = await self._request("GET", "/areas")
            if isinstance(areas_result, list):
                entities.extend(areas_result)
            elif isinstance(areas_result, dict):
                if "areas" in areas_result:
                    entities.extend(areas_result["areas"])
                elif "items" in areas_result:
                    entities.extend(areas_result["items"])
        except SovdClientError:
            pass  # Skip if areas endpoint fails

        # Fetch components
        try:
            components_result = await self._request("GET", "/components")
            if isinstance(components_result, list):
                entities.extend(components_result)
            elif isinstance(components_result, dict):
                if "components" in components_result:
                    entities.extend(components_result["components"])
                elif "items" in components_result:
                    entities.extend(components_result["items"])
        except SovdClientError:
            pass  # Skip if components endpoint fails

        # Fetch apps
        try:
            apps_result = await self._request("GET", "/apps")
            if isinstance(apps_result, list):
                entities.extend(apps_result)
            elif isinstance(apps_result, dict):
                if "apps" in apps_result:
                    entities.extend(apps_result["apps"])
                elif "items" in apps_result:
                    entities.extend(apps_result["items"])
        except SovdClientError:
            pass  # Skip if apps endpoint fails

        # Fetch functions
        try:
            functions_result = await self._request("GET", "/functions")
            if isinstance(functions_result, list):
                entities.extend(functions_result)
            elif isinstance(functions_result, dict):
                if "functions" in functions_result:
                    entities.extend(functions_result["functions"])
                elif "items" in functions_result:
                    entities.extend(functions_result["items"])
        except SovdClientError:
            pass  # Skip if functions endpoint fails

        return entities

    async def list_areas(self) -> list[dict[str, Any]]:
        """List all SOVD areas.

        Returns:
            List of area dictionaries.
        """
        result = await self._request("GET", "/areas")
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "areas" in result:
            return result["areas"]
        return [result] if result else []

    async def get_area(self, area_id: str) -> dict[str, Any]:
        """Get details of a specific area.

        Args:
            area_id: The area identifier.

        Returns:
            Area data dictionary.
        """
        result = await self._request("GET", f"/areas/{area_id}")
        return result.get("item", result) if isinstance(result, dict) else result

    async def list_components(self) -> list[dict[str, Any]]:
        """List all SOVD components.

        Returns:
            List of component dictionaries.
        """
        result = await self._request("GET", "/components")
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            if "components" in result:
                return result["components"]
            if "items" in result:
                return result["items"]
        return [result] if result else []

    async def get_component(self, component_id: str) -> dict[str, Any]:
        """Get details of a specific component.

        Args:
            component_id: The component identifier.

        Returns:
            Component data dictionary.
        """
        result = await self._request("GET", f"/components/{component_id}")
        return result.get("item", result) if isinstance(result, dict) else result

    async def list_apps(self) -> list[dict[str, Any]]:
        """List all SOVD apps (ROS 2 nodes).

        Returns:
            List of app dictionaries.
        """
        result = await self._request("GET", "/apps")
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            if "apps" in result:
                return result["apps"]
            if "items" in result:
                return result["items"]
        return [result] if result else []

    async def get_app(self, app_id: str) -> dict[str, Any]:
        """Get app capabilities and details.

        Args:
            app_id: The app identifier.

        Returns:
            App data dictionary.
        """
        result = await self._request("GET", f"/apps/{app_id}")
        return result.get("item", result) if isinstance(result, dict) else result

    async def list_app_dependencies(self, app_id: str) -> list[dict[str, Any]]:
        """List dependencies for an app.

        Args:
            app_id: The app identifier.

        Returns:
            List of dependency dictionaries.
        """
        result = await self._request("GET", f"/apps/{app_id}/depends-on")
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "items" in result:
            return result["items"]
        return [result] if result else []

    async def list_functions(self) -> list[dict[str, Any]]:
        """List all SOVD functions.

        Returns:
            List of function dictionaries.
        """
        result = await self._request("GET", "/functions")
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            if "functions" in result:
                return result["functions"]
            if "items" in result:
                return result["items"]
        return [result] if result else []

    async def get_function(self, function_id: str) -> dict[str, Any]:
        """Get function details.

        Args:
            function_id: The function identifier.

        Returns:
            Function data dictionary.
        """
        result = await self._request("GET", f"/functions/{function_id}")
        return result.get("item", result) if isinstance(result, dict) else result

    async def list_function_hosts(self, function_id: str) -> list[dict[str, Any]]:
        """List apps that host a function.

        Args:
            function_id: The function identifier.

        Returns:
            List of host app dictionaries.
        """
        result = await self._request("GET", f"/functions/{function_id}/hosts")
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "items" in result:
            return result["items"]
        return [result] if result else []

    async def get_entity(self, entity_id: str) -> dict[str, Any]:
        """Get a specific entity by ID.

        Searches through the list of all entities to find the one with matching ID.
        For components, also attempts to fetch live data.

        Args:
            entity_id: The entity identifier (component or area ID).

        Returns:
            Entity data as dictionary.

        Raises:
            SovdClientError: If entity not found.
        """
        entities = await self.list_entities()

        # Find the entity with matching ID
        found_entity = None
        for entity in entities:
            if entity.get("id") == entity_id:
                found_entity = entity
                break

        if not found_entity:
            raise SovdClientError(
                message=f"Entity '{entity_id}' not found",
                status_code=404,
            )

        # If it's a component, try to fetch its live data
        if found_entity.get("type") == "Component":
            try:
                # Use the fqn (fully qualified name) to fetch the component's namespace path
                fqn = found_entity.get("fqn", "").lstrip("/")
                if fqn:
                    # Try to get component data - might need to use area path
                    component_data = await self._request("GET", f"/components/{entity_id}/data")
                    return {**found_entity, "data": component_data}
            except SovdClientError:
                pass  # Component doesn't expose data endpoint

        return found_entity

    async def list_faults(
        self, entity_id: str, entity_type: str = "components"
    ) -> list[dict[str, Any]]:
        """List all faults for an entity.

        Args:
            entity_id: The entity identifier.
            entity_type: Entity type ('components', 'apps', 'areas', 'functions').

        Returns:
            List of fault dictionaries.
        """
        result = await self._request("GET", f"/{entity_type}/{entity_id}/faults")
        if isinstance(result, list):
            return result
        # Handle case where response is wrapped in an object
        if isinstance(result, dict):
            if "faults" in result:
                return result["faults"]
            if "items" in result:
                return result["items"]
        return [result] if result else []

    async def get_fault(
        self, entity_id: str, fault_id: str, entity_type: str = "components"
    ) -> dict[str, Any]:
        """Get a specific fault by ID.

        Args:
            entity_id: The entity identifier.
            fault_id: The fault identifier (fault code).
            entity_type: Entity type ('components', 'apps', 'areas', 'functions').

        Returns:
            Fault data dictionary.
        """
        return await self._request("GET", f"/{entity_type}/{entity_id}/faults/{fault_id}")

    async def clear_fault(
        self, entity_id: str, fault_id: str, entity_type: str = "components"
    ) -> dict[str, Any]:
        """Clear (acknowledge/dismiss) a fault.

        Args:
            entity_id: The entity identifier.
            fault_id: The fault identifier to clear.
            entity_type: Entity type ('components', 'apps', 'areas', 'functions').

        Returns:
            Response dictionary with clear status.
        """
        return await self._request("DELETE", f"/{entity_type}/{entity_id}/faults/{fault_id}")

    async def clear_all_faults(
        self, entity_id: str, entity_type: str = "components"
    ) -> dict[str, Any]:
        """Clear all faults for an entity.

        Args:
            entity_id: The entity identifier.
            entity_type: Entity type ('components', 'apps', 'areas', 'functions').

        Returns:
            Response dictionary with clear status.
        """
        return await self._request("DELETE", f"/{entity_type}/{entity_id}/faults")

    async def list_all_faults(self) -> list[dict[str, Any]]:
        """List all faults across the entire system.

        Returns:
            List of all fault dictionaries.
        """
        result = await self._request("GET", "/faults")
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            if "faults" in result:
                return result["faults"]
            if "items" in result:
                return result["items"]
        return [result] if result else []

    async def get_fault_snapshots(
        self, entity_id: str, fault_code: str, entity_type: str = "components"
    ) -> dict[str, Any]:
        """Get diagnostic snapshots for a fault.

        Args:
            entity_id: The entity identifier.
            fault_code: The fault code.
            entity_type: Entity type ('components', 'apps', 'areas', 'functions').

        Returns:
            Snapshot data dictionary.
        """
        return await self._request(
            "GET", f"/{entity_type}/{entity_id}/faults/{fault_code}/snapshots"
        )

    async def get_system_fault_snapshots(self, fault_code: str) -> dict[str, Any]:
        """Get system-wide diagnostic snapshots for a fault.

        Args:
            fault_code: The fault code.

        Returns:
            Snapshot data dictionary.
        """
        return await self._request("GET", f"/faults/{fault_code}/snapshots")

    # ==================== Area Components ====================

    async def list_area_components(self, area_id: str) -> list[dict[str, Any]]:
        """List all components within a specific area.

        Args:
            area_id: The area identifier (e.g., 'powertrain', 'chassis', 'body').

        Returns:
            List of component dictionaries.
        """
        result = await self._request("GET", f"/areas/{area_id}/components")
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "items" in result:
            return result["items"]
        return [result] if result else []

    async def list_area_subareas(self, area_id: str) -> list[dict[str, Any]]:
        """List sub-areas within an area.

        Args:
            area_id: The area identifier.

        Returns:
            List of sub-area dictionaries.
        """
        result = await self._request("GET", f"/areas/{area_id}/subareas")
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "items" in result:
            return result["items"]
        return [result] if result else []

    async def list_area_contains(self, area_id: str) -> list[dict[str, Any]]:
        """List all entities contained in an area.

        Args:
            area_id: The area identifier.

        Returns:
            List of contained entity dictionaries.
        """
        result = await self._request("GET", f"/areas/{area_id}/contains")
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "items" in result:
            return result["items"]
        return [result] if result else []

    # ==================== Component Relationships ====================

    async def list_component_subcomponents(self, component_id: str) -> list[dict[str, Any]]:
        """List subcomponents of a component.

        Args:
            component_id: The component identifier.

        Returns:
            List of subcomponent dictionaries.
        """
        result = await self._request("GET", f"/components/{component_id}/subcomponents")
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "items" in result:
            return result["items"]
        return [result] if result else []

    async def list_component_hosts(self, component_id: str) -> list[dict[str, Any]]:
        """List apps hosted by a component.

        Args:
            component_id: The component identifier.

        Returns:
            List of hosted app dictionaries.
        """
        result = await self._request("GET", f"/components/{component_id}/hosts")
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "items" in result:
            return result["items"]
        return [result] if result else []

    async def list_component_dependencies(self, component_id: str) -> list[dict[str, Any]]:
        """List dependencies of a component.

        Args:
            component_id: The component identifier.

        Returns:
            List of dependency dictionaries.
        """
        result = await self._request("GET", f"/components/{component_id}/depends-on")
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "items" in result:
            return result["items"]
        return [result] if result else []

    # ==================== Component Data ====================

    async def get_component_data(
        self, entity_id: str, entity_type: str = "components"
    ) -> list[dict[str, Any]]:
        """Read all topic data from an entity.

        Args:
            entity_id: The entity identifier.
            entity_type: Entity type ('components', 'apps', 'areas', 'functions').

        Returns:
            List of topic data dictionaries.
        """
        result = await self._request("GET", f"/{entity_type}/{entity_id}/data")
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "items" in result:
            return result["items"]
        return [result] if result else []

    async def get_component_topic_data(
        self, entity_id: str, topic_name: str, entity_type: str = "components"
    ) -> dict[str, Any]:
        """Read data from a specific topic within an entity.

        Args:
            entity_id: The entity identifier.
            topic_name: The topic name (e.g., 'temperature', 'rpm').
            entity_type: Entity type ('components', 'apps', 'areas', 'functions').

        Returns:
            Topic data dictionary.
        """
        return await self._request("GET", f"/{entity_type}/{entity_id}/data/{topic_name}")

    async def publish_to_topic(
        self,
        entity_id: str,
        topic_name: str,
        data: dict[str, Any],
        entity_type: str = "components",
    ) -> dict[str, Any]:
        """Publish data to an entity's topic.

        Args:
            entity_id: The entity identifier.
            topic_name: The topic name to publish to.
            data: The message data to publish.
            entity_type: Entity type ('components', 'apps', 'areas', 'functions').

        Returns:
            Response dictionary with publish status.
        """
        return await self._request(
            "PUT", f"/{entity_type}/{entity_id}/data/{topic_name}", json_body=data
        )

    # ==================== Operations (Services & Actions) ====================

    async def list_operations(
        self, entity_id: str, entity_type: str = "components"
    ) -> list[dict[str, Any]]:
        """List all operations (services and actions) for an entity.

        Args:
            entity_id: The entity identifier.
            entity_type: Entity type ('components', 'apps', 'areas', 'functions').

        Returns:
            List of operation dictionaries.
        """
        result = await self._request("GET", f"/{entity_type}/{entity_id}/operations")
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "items" in result:
            return result["items"]
        return [result] if result else []

    async def get_operation(
        self, entity_id: str, operation_name: str, entity_type: str = "components"
    ) -> dict[str, Any]:
        """Get details of a specific operation.

        Args:
            entity_id: The entity identifier.
            operation_name: The operation name.
            entity_type: Entity type ('components', 'apps', 'areas', 'functions').

        Returns:
            Operation details dictionary.
        """
        return await self._request("GET", f"/{entity_type}/{entity_id}/operations/{operation_name}")

    async def create_execution(
        self,
        entity_id: str,
        operation_name: str,
        request_data: dict[str, Any] | None = None,
        entity_type: str = "components",
    ) -> dict[str, Any]:
        """Start an execution for an operation (service call or action goal).

        Args:
            entity_id: The entity identifier.
            operation_name: The operation name (service or action).
            request_data: Optional request data (goal for actions, request for services).
            entity_type: Entity type ('components', 'apps', 'areas', 'functions').

        Returns:
            Response dictionary with execution_id for actions, or result for services.
        """
        body: dict[str, Any] = {}
        if request_data:
            body["parameters"] = request_data  # SOVD uses 'parameters' field
        return await self._request(
            "POST",
            f"/{entity_type}/{entity_id}/operations/{operation_name}/executions",
            json_body=body if body else None,
        )

    async def list_executions(
        self, entity_id: str, operation_name: str, entity_type: str = "components"
    ) -> list[dict[str, Any]]:
        """List all executions for an operation.

        Args:
            entity_id: The entity identifier.
            operation_name: The operation name.
            entity_type: Entity type ('components', 'apps', 'areas', 'functions').

        Returns:
            List of execution dictionaries.
        """
        result = await self._request(
            "GET", f"/{entity_type}/{entity_id}/operations/{operation_name}/executions"
        )
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "items" in result:
            return result["items"]
        return [result] if result else []

    async def get_execution(
        self,
        entity_id: str,
        operation_name: str,
        execution_id: str,
        entity_type: str = "components",
    ) -> dict[str, Any]:
        """Get execution status and feedback.

        Args:
            entity_id: The entity identifier.
            operation_name: The operation name.
            execution_id: The execution identifier.
            entity_type: Entity type ('components', 'apps', 'areas', 'functions').

        Returns:
            Execution status dictionary.
        """
        return await self._request(
            "GET",
            f"/{entity_type}/{entity_id}/operations/{operation_name}/executions/{execution_id}",
        )

    async def update_execution(
        self,
        entity_id: str,
        operation_name: str,
        execution_id: str,
        update_data: dict[str, Any],
        entity_type: str = "components",
    ) -> dict[str, Any]:
        """Update an execution (e.g., stop capability).

        Args:
            entity_id: The entity identifier.
            operation_name: The operation name.
            execution_id: The execution identifier.
            update_data: Update data (e.g., {"stop": True}).
            entity_type: Entity type ('components', 'apps', 'areas', 'functions').

        Returns:
            Updated execution dictionary.
        """
        return await self._request(
            "PUT",
            f"/{entity_type}/{entity_id}/operations/{operation_name}/executions/{execution_id}",
            json_body=update_data,
        )

    async def cancel_execution(
        self,
        entity_id: str,
        operation_name: str,
        execution_id: str,
        entity_type: str = "components",
    ) -> dict[str, Any]:
        """Cancel a specific execution.

        Args:
            entity_id: The entity identifier.
            operation_name: The operation name.
            execution_id: The execution identifier.
            entity_type: Entity type ('components', 'apps', 'areas', 'functions').

        Returns:
            Cancellation response dictionary.
        """
        return await self._request(
            "DELETE",
            f"/{entity_type}/{entity_id}/operations/{operation_name}/executions/{execution_id}",
        )

    # ==================== Configurations (ROS 2 Parameters) ====================

    async def list_configurations(
        self, entity_id: str, entity_type: str = "components"
    ) -> list[dict[str, Any]]:
        """List all configurations (parameters) for an entity.

        Args:
            entity_id: The entity identifier.
            entity_type: Entity type ('components', 'apps', 'areas', 'functions').

        Returns:
            List of configuration dictionaries.
        """
        result = await self._request("GET", f"/{entity_type}/{entity_id}/configurations")
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            if "configurations" in result:
                return result["configurations"]
            if "items" in result:
                return result["items"]
        return [result] if result else []

    async def get_configuration(
        self, entity_id: str, param_name: str, entity_type: str = "components"
    ) -> dict[str, Any]:
        """Get a specific configuration (parameter) value.

        Args:
            entity_id: The entity identifier.
            param_name: The parameter name.
            entity_type: Entity type ('components', 'apps', 'areas', 'functions').

        Returns:
            Configuration value dictionary.
        """
        return await self._request("GET", f"/{entity_type}/{entity_id}/configurations/{param_name}")

    async def set_configuration(
        self, entity_id: str, param_name: str, value: Any, entity_type: str = "components"
    ) -> dict[str, Any]:
        """Set a configuration (parameter) value.

        Args:
            entity_id: The entity identifier.
            param_name: The parameter name.
            value: The new parameter value.
            entity_type: Entity type ('components', 'apps', 'areas', 'functions').

        Returns:
            Response dictionary with set status.
        """
        return await self._request(
            "PUT",
            f"/{entity_type}/{entity_id}/configurations/{param_name}",
            json_body={"value": value},
        )

    async def delete_configuration(
        self, entity_id: str, param_name: str, entity_type: str = "components"
    ) -> dict[str, Any]:
        """Reset a configuration (parameter) to its default value.

        Args:
            entity_id: The entity identifier.
            param_name: The parameter name.
            entity_type: Entity type ('components', 'apps', 'areas', 'functions').

        Returns:
            Response dictionary.
        """
        return await self._request(
            "DELETE", f"/{entity_type}/{entity_id}/configurations/{param_name}"
        )

    async def delete_all_configurations(
        self, entity_id: str, entity_type: str = "components"
    ) -> dict[str, Any]:
        """Reset all configurations (parameters) to their default values.

        Args:
            entity_id: The entity identifier.
            entity_type: Entity type ('components', 'apps', 'areas', 'functions').

        Returns:
            Response dictionary.
        """
        return await self._request("DELETE", f"/{entity_type}/{entity_id}/configurations")


@asynccontextmanager
async def create_client(settings: Settings) -> AsyncIterator[SovdClient]:
    """Create and manage SOVD client lifecycle.

    Args:
        settings: Application settings.

    Yields:
        Initialized SOVD client.
    """
    client = SovdClient(settings)
    try:
        yield client
    finally:
        await client.close()
