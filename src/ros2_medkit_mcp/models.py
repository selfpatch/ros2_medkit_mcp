"""Pydantic models for MCP tool arguments and responses.

These models are intentionally permissive to handle varying API responses.
They validate input arguments while allowing flexible output from the API.
"""

from enum import Enum
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


# ==================== Fault Response Models ====================


class FaultStatus(str, Enum):
    """Fault status values per SOVD specification."""

    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    CLEARED = "CLEARED"
    INACTIVE = "INACTIVE"


class FaultItem(BaseModel):
    """Fault item model per SOVD specification."""

    code: str = Field(..., description="Fault code (DTC)")
    fault_name: str | None = Field(
        default=None,
        alias="faultName",
        description="Human-readable fault name",
    )
    severity: str | None = Field(
        default=None,
        description="Fault severity (e.g., 'critical', 'warning', 'info')",
    )
    status: FaultStatus | None = Field(
        default=None,
        description="Current fault status",
    )
    is_confirmed: bool | None = Field(
        default=None,
        alias="isConfirmed",
        description="Whether the fault is confirmed",
    )
    is_current: bool | None = Field(
        default=None,
        alias="isCurrent",
        description="Whether the fault is currently active",
    )
    is_test_failed: bool | None = Field(
        default=None,
        alias="isTestFailed",
        description="Whether the related test failed",
    )
    counter: int | None = Field(
        default=None,
        description="Occurrence counter",
    )
    aging_counter: int | None = Field(
        default=None,
        alias="agingCounter",
        description="Aging counter for fault maturation",
    )
    first_occurrence: str | None = Field(
        default=None,
        alias="firstOccurrence",
        description="ISO 8601 timestamp of first occurrence",
    )
    last_occurrence: str | None = Field(
        default=None,
        alias="lastOccurrence",
        description="ISO 8601 timestamp of last occurrence",
    )
    healing_cycles: int | None = Field(
        default=None,
        alias="healingCycles",
        description="Number of healing cycles",
    )
    x_medkit: dict[str, Any] | None = Field(
        default=None,
        alias="x-medkit",
        description="ROS 2 MedKit specific extensions",
    )

    model_config = {"populate_by_name": True, "extra": "allow"}


class FreezeFrameSnapshot(BaseModel):
    """Freeze frame snapshot with captured diagnostic data."""

    snapshot_id: str = Field(
        ...,
        alias="snapshotId",
        description="Unique identifier for the snapshot",
    )
    timestamp: str = Field(
        ...,
        description="ISO 8601 timestamp when snapshot was captured",
    )
    data_source: str | None = Field(
        default=None,
        alias="dataSource",
        description="Source of the snapshot data (e.g., topic name)",
    )
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Captured diagnostic data",
    )

    model_config = {"populate_by_name": True, "extra": "allow"}


class BulkDataDescriptor(BaseModel):
    """Descriptor for bulk data (rosbag) with download URI."""

    id: str = Field(..., description="Bulk data identifier")
    category: str | None = Field(
        default=None,
        description="Data category (e.g., 'rosbag', 'snapshot')",
    )
    bulk_data_uri: str = Field(
        ...,
        alias="bulkDataUri",
        description="URI to download the bulk data file",
    )
    file_size: int | None = Field(
        default=None,
        alias="fileSize",
        description="File size in bytes",
    )
    is_available: bool = Field(
        default=True,
        alias="isAvailable",
        description="Whether the file is available for download",
    )
    timestamp: str | None = Field(
        default=None,
        description="ISO 8601 timestamp when the data was captured",
    )

    model_config = {"populate_by_name": True, "extra": "allow"}


class RosbagSnapshot(BaseModel):
    """Rosbag snapshot with bulk data download URI."""

    snapshot_id: str = Field(
        ...,
        alias="snapshotId",
        description="Unique identifier for the snapshot",
    )
    timestamp: str = Field(
        ...,
        description="ISO 8601 timestamp when snapshot was captured",
    )
    bulk_data_uri: str = Field(
        ...,
        alias="bulkDataUri",
        description="URI to download the rosbag file",
    )
    file_size: int | None = Field(
        default=None,
        alias="fileSize",
        description="File size in bytes",
    )
    is_available: bool = Field(
        default=True,
        alias="isAvailable",
        description="Whether the rosbag file is available for download",
    )
    data_source: str | None = Field(
        default=None,
        alias="dataSource",
        description="Source description for the snapshot",
    )

    model_config = {"populate_by_name": True, "extra": "allow"}


class ExtendedDataRecords(BaseModel):
    """Extended data records containing diagnostic snapshots."""

    freeze_frame_snapshots: list[FreezeFrameSnapshot] = Field(
        default_factory=list,
        alias="freezeFrameSnapshots",
        description="List of freeze frame snapshots with captured data",
    )
    rosbag_snapshots: list[RosbagSnapshot] = Field(
        default_factory=list,
        alias="rosbagSnapshots",
        description="List of rosbag snapshots with download URIs",
    )

    model_config = {"populate_by_name": True, "extra": "allow"}


class EnvironmentData(BaseModel):
    """Environment data captured at fault occurrence."""

    extended_data_records: ExtendedDataRecords | None = Field(
        default=None,
        alias="extendedDataRecords",
        description="Snapshot data including freeze frames and rosbags",
    )

    model_config = {"populate_by_name": True, "extra": "allow"}


class FaultResponse(BaseModel):
    """Complete fault response with item and environment data."""

    item: FaultItem = Field(..., description="The fault item details")
    environment_data: EnvironmentData | None = Field(
        default=None,
        alias="environmentData",
        description="Environment data captured at fault occurrence",
    )

    model_config = {"populate_by_name": True, "extra": "allow"}


class FaultListResponse(BaseModel):
    """Response containing a list of fault items."""

    items: list[FaultItem] = Field(
        default_factory=list,
        description="List of fault items",
    )

    model_config = {"populate_by_name": True, "extra": "allow"}


# ==================== Bulk Data Response Models ====================


class BulkDataItem(BaseModel):
    """Item in a bulk-data category listing."""

    id: str = Field(..., description="Unique identifier for the bulk data item")
    name: str | None = Field(
        default=None,
        description="Human-readable name for the item",
    )
    mimetype: str = Field(
        default="application/octet-stream",
        description="MIME type of the data (e.g., 'application/x-mcap')",
    )
    size: int | None = Field(
        default=None,
        description="File size in bytes",
    )
    creation_date: str | None = Field(
        default=None,
        alias="creationDate",
        description="ISO 8601 timestamp when the data was created",
    )

    model_config = {"populate_by_name": True, "extra": "allow"}


class BulkDataCategoryResponse(BaseModel):
    """Response listing available bulk-data categories."""

    items: list[str] = Field(
        default_factory=list,
        description="List of available category names (e.g., 'rosbags', 'logs')",
    )

    model_config = {"populate_by_name": True, "extra": "allow"}


class BulkDataListResponse(BaseModel):
    """Response listing items in a bulk-data category."""

    items: list[BulkDataItem] = Field(
        default_factory=list,
        description="List of bulk data items in the category",
    )

    model_config = {"populate_by_name": True, "extra": "allow"}


# ==================== Bulk Data Argument Models ====================


class BulkDataCategoriesArgs(BaseModel):
    """Arguments for listing bulk-data categories."""

    entity_id: str = Field(
        ...,
        description="The entity identifier",
    )
    entity_type: str = Field(
        default="apps",
        description="Entity type: 'components', 'apps', 'areas', or 'functions'",
    )


class BulkDataListArgs(BaseModel):
    """Arguments for listing bulk-data items in a category."""

    entity_id: str = Field(
        ...,
        description="The entity identifier",
    )
    category: str = Field(
        ...,
        description="Category name (e.g., 'rosbags')",
    )
    entity_type: str = Field(
        default="apps",
        description="Entity type: 'components', 'apps', 'areas', or 'functions'",
    )


class BulkDataInfoArgs(BaseModel):
    """Arguments for getting bulk-data item info."""

    bulk_data_uri: str = Field(
        ...,
        description="Full bulk-data URI path (e.g., '/apps/motor/bulk-data/rosbags/uuid')",
    )


class BulkDataDownloadArgs(BaseModel):
    """Arguments for downloading a bulk-data item."""

    bulk_data_uri: str = Field(
        ...,
        description="Full bulk-data URI path (e.g., '/apps/motor/bulk-data/rosbags/uuid')",
    )
    output_dir: str = Field(
        default="/tmp",
        description="Directory to save the downloaded file",
    )


class BulkDataDownloadForFaultArgs(BaseModel):
    """Arguments for downloading all rosbags for a fault."""

    entity_id: str = Field(
        ...,
        description="The entity identifier",
    )
    fault_code: str = Field(
        ...,
        description="The fault code",
    )
    entity_type: str = Field(
        default="apps",
        description="Entity type: 'components', 'apps', 'areas', or 'functions'",
    )
    output_dir: str = Field(
        default="/tmp",
        description="Directory to save the downloaded files",
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
