"""Pydantic models for MCP tool arguments and responses.

These models are intentionally permissive to handle varying API responses.
They validate input arguments while allowing flexible output from the API.
"""

from typing import Any

from pydantic import BaseModel, Field


class EntitiesListArgs(BaseModel):
    """Arguments for sovd.entities.list tool."""

    filter: str | None = Field(
        default=None,
        description="Optional substring filter to match against entity id and name",
    )


class EntityGetArgs(BaseModel):
    """Arguments for sovd.entities.get tool."""

    entity_id: str = Field(
        ...,
        description="The entity identifier to retrieve",
    )


class FaultsListArgs(BaseModel):
    """Arguments for listing entity faults."""

    entity_id: str = Field(
        ...,
        description="The entity identifier",
    )
    entity_type: str = Field(
        default="components",
        description="Entity type: 'components', 'apps', 'areas', or 'functions'",
    )


class FaultGetArgs(BaseModel):
    """Arguments for getting or clearing a specific fault."""

    entity_id: str = Field(
        ...,
        description="The entity identifier",
    )
    fault_id: str = Field(
        ...,
        description="The fault identifier (fault code)",
    )
    entity_type: str = Field(
        default="components",
        description="Entity type: 'components', 'apps', 'areas', or 'functions'",
    )


class AreaComponentsArgs(BaseModel):
    """Arguments for listing components in an area."""

    area_id: str = Field(
        ...,
        description="The area identifier (e.g., 'powertrain', 'chassis', 'body')",
    )


class AreaIdArgs(BaseModel):
    """Arguments for area-specific operations."""

    area_id: str = Field(
        ...,
        description="The area identifier",
    )


class ComponentIdArgs(BaseModel):
    """Arguments for component-specific operations."""

    component_id: str = Field(
        ...,
        description="The component identifier",
    )


class EntityDataArgs(BaseModel):
    """Arguments for getting entity data."""

    entity_id: str = Field(
        ...,
        description="The entity identifier",
    )
    entity_type: str = Field(
        default="components",
        description="Entity type: 'components', 'apps', 'areas', or 'functions'",
    )


class EntityTopicDataArgs(BaseModel):
    """Arguments for getting specific topic data from an entity."""

    entity_id: str = Field(
        ...,
        description="The entity identifier",
    )
    topic_name: str = Field(
        ...,
        description="The topic name (e.g., 'temperature', 'rpm')",
    )
    entity_type: str = Field(
        default="components",
        description="Entity type: 'components', 'apps', 'areas', or 'functions'",
    )


class PublishTopicArgs(BaseModel):
    """Arguments for publishing data to a topic."""

    entity_id: str = Field(
        ...,
        description="The entity identifier",
    )
    topic_name: str = Field(
        ...,
        description="The topic name to publish to",
    )
    data: dict[str, Any] = Field(
        ...,
        description="The message data to publish as JSON object",
    )
    entity_type: str = Field(
        default="components",
        description="Entity type: 'components', 'apps', 'areas', or 'functions'",
    )


class ListOperationsArgs(BaseModel):
    """Arguments for listing entity operations."""

    entity_id: str = Field(
        ...,
        description="The entity identifier",
    )
    entity_type: str = Field(
        default="components",
        description="Entity type: 'components', 'apps', 'areas', or 'functions'",
    )


# ==================== Execution Model Args ====================


class CreateExecutionArgs(BaseModel):
    """Arguments for creating an execution."""

    entity_id: str = Field(
        ...,
        description="The entity identifier (component, app, etc.)",
    )
    operation_name: str = Field(
        ...,
        description="The operation name (service or action)",
    )
    request_data: dict[str, Any] | None = Field(
        default=None,
        description="Optional request data (goal for actions, request for services)",
    )
    entity_type: str = Field(
        default="components",
        description="Entity type: 'components', 'apps', 'areas', or 'functions'",
    )


class ListExecutionsArgs(BaseModel):
    """Arguments for listing executions."""

    entity_id: str = Field(
        ...,
        description="The entity identifier",
    )
    operation_name: str = Field(
        ...,
        description="The operation name",
    )
    entity_type: str = Field(
        default="components",
        description="Entity type: 'components', 'apps', 'areas', or 'functions'",
    )


class ExecutionArgs(BaseModel):
    """Arguments for get/cancel/update execution."""

    entity_id: str = Field(
        ...,
        description="The entity identifier",
    )
    operation_name: str = Field(
        ...,
        description="The operation name",
    )
    execution_id: str = Field(
        ...,
        description="The execution identifier",
    )
    entity_type: str = Field(
        default="components",
        description="Entity type: 'components', 'apps', 'areas', or 'functions'",
    )


class UpdateExecutionArgs(BaseModel):
    """Arguments for updating an execution."""

    entity_id: str = Field(
        ...,
        description="The entity identifier",
    )
    operation_name: str = Field(
        ...,
        description="The operation name",
    )
    execution_id: str = Field(
        ...,
        description="The execution identifier",
    )
    update_data: dict[str, Any] = Field(
        ...,
        description="Update data (e.g., {'stop': true} to stop execution)",
    )
    entity_type: str = Field(
        default="components",
        description="Entity type: 'components', 'apps', 'areas', or 'functions'",
    )


class GetOperationArgs(BaseModel):
    """Arguments for getting operation details."""

    entity_id: str = Field(
        ...,
        description="The entity identifier",
    )
    operation_name: str = Field(
        ...,
        description="The operation name",
    )
    entity_type: str = Field(
        default="components",
        description="Entity type: 'components', 'apps', 'areas', or 'functions'",
    )


# ==================== Apps & Functions Args ====================


class AppIdArgs(BaseModel):
    """Arguments for app-specific operations."""

    app_id: str = Field(
        ...,
        description="The app identifier",
    )


class FunctionIdArgs(BaseModel):
    """Arguments for function-specific operations."""

    function_id: str = Field(
        ...,
        description="The function identifier",
    )


# ==================== Fault Args ====================


class ClearAllFaultsArgs(BaseModel):
    """Arguments for clearing all faults."""

    entity_id: str = Field(
        ...,
        description="The entity identifier",
    )
    entity_type: str = Field(
        default="components",
        description="Entity type: 'components', 'apps', 'areas', or 'functions'",
    )


class FaultSnapshotsArgs(BaseModel):
    """Arguments for getting fault snapshots."""

    entity_id: str = Field(
        ...,
        description="The entity identifier",
    )
    fault_code: str = Field(
        ...,
        description="The fault code",
    )
    entity_type: str = Field(
        default="components",
        description="Entity type: 'components', 'apps', 'areas', or 'functions'",
    )


class SystemFaultSnapshotsArgs(BaseModel):
    """Arguments for getting system-wide fault snapshots."""

    fault_code: str = Field(
        ...,
        description="The fault code",
    )


# ==================== Relationship Args ====================


class SubareasArgs(BaseModel):
    """Arguments for listing sub-areas."""

    area_id: str = Field(
        ...,
        description="The area identifier",
    )


class AreaContainsArgs(BaseModel):
    """Arguments for listing area contents."""

    area_id: str = Field(
        ...,
        description="The area identifier",
    )


class SubcomponentsArgs(BaseModel):
    """Arguments for listing subcomponents."""

    component_id: str = Field(
        ...,
        description="The component identifier",
    )


class ComponentHostsArgs(BaseModel):
    """Arguments for listing component hosts."""

    component_id: str = Field(
        ...,
        description="The component identifier",
    )


class DependenciesArgs(BaseModel):
    """Arguments for listing dependencies."""

    entity_id: str = Field(
        ...,
        description="The entity identifier (component or app)",
    )
    entity_type: str = Field(
        default="components",
        description="Entity type: 'components' or 'apps'",
    )


class ListConfigurationsArgs(BaseModel):
    """Arguments for listing entity configurations."""

    entity_id: str = Field(
        ...,
        description="The entity identifier",
    )
    entity_type: str = Field(
        default="components",
        description="Entity type: 'components', 'apps', 'areas', or 'functions'",
    )


class GetConfigurationArgs(BaseModel):
    """Arguments for getting a specific configuration."""

    entity_id: str = Field(
        ...,
        description="The entity identifier",
    )
    param_name: str = Field(
        ...,
        description="The parameter name",
    )
    entity_type: str = Field(
        default="components",
        description="Entity type: 'components', 'apps', 'areas', or 'functions'",
    )


class SetConfigurationArgs(BaseModel):
    """Arguments for setting a configuration value."""

    entity_id: str = Field(
        ...,
        description="The entity identifier",
    )
    param_name: str = Field(
        ...,
        description="The parameter name",
    )
    value: Any = Field(
        ...,
        description="The new parameter value",
    )
    entity_type: str = Field(
        default="components",
        description="Entity type: 'components', 'apps', 'areas', or 'functions'",
    )


class ToolResult(BaseModel):
    """Standard result wrapper for tool responses."""

    success: bool = Field(
        default=True,
        description="Whether the tool execution succeeded",
    )
    data: Any = Field(
        default=None,
        description="The result data from the tool",
    )
    error: str | None = Field(
        default=None,
        description="Error message if success is False",
    )

    @classmethod
    def ok(cls, data: Any) -> "ToolResult":
        """Create a successful result.

        Args:
            data: The result data.

        Returns:
            ToolResult with success=True.
        """
        return cls(success=True, data=data)

    @classmethod
    def fail(cls, error: str) -> "ToolResult":
        """Create a failed result.

        Args:
            error: Error message.

        Returns:
            ToolResult with success=False.
        """
        return cls(success=False, error=error)


def filter_entities(
    entities: list[dict[str, Any]], filter_text: str | None
) -> list[dict[str, Any]]:
    """Filter entities by substring match on id and name fields.

    Args:
        entities: List of entity dictionaries.
        filter_text: Optional substring to filter by.

    Returns:
        Filtered list of entities.
    """
    if not filter_text:
        return entities

    filter_lower = filter_text.lower()
    filtered = []

    for entity in entities:
        # Match against id field
        entity_id = entity.get("id", "")
        if isinstance(entity_id, str) and filter_lower in entity_id.lower():
            filtered.append(entity)
            continue

        # Match against name field
        entity_name = entity.get("name", "")
        if isinstance(entity_name, str) and filter_lower in entity_name.lower():
            filtered.append(entity)

    return filtered
