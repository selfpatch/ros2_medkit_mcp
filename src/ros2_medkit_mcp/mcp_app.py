"""MCP application with tools and resources for ros2_medkit SOVD API.

This module defines the MCP server with all tools and resources,
intended to be reused by both stdio and HTTP transport entrypoints.
"""

import json
import logging
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.types import Resource, TextContent, Tool

from ros2_medkit_mcp.client import SovdClient, SovdClientError
from ros2_medkit_mcp.config import Settings
from ros2_medkit_mcp.models import (
    AppIdArgs,
    AreaComponentsArgs,
    AreaContainsArgs,
    AreaIdArgs,
    BulkDataCategoriesArgs,
    BulkDataDownloadArgs,
    BulkDataDownloadForFaultArgs,
    BulkDataInfoArgs,
    BulkDataItem,
    BulkDataListArgs,
    ClearAllFaultsArgs,
    ComponentHostsArgs,
    ComponentIdArgs,
    CreateExecutionArgs,
    DependenciesArgs,
    EntitiesListArgs,
    EntityDataArgs,
    EntityGetArgs,
    EntityTopicDataArgs,
    EnvironmentData,
    ExecutionArgs,
    ExtendedDataRecords,
    FaultGetArgs,
    FaultItem,
    FaultsListArgs,
    FaultSnapshotsArgs,
    FreezeFrameSnapshot,
    FunctionIdArgs,
    GetConfigurationArgs,
    GetOperationArgs,
    ListConfigurationsArgs,
    ListExecutionsArgs,
    ListOperationsArgs,
    PublishTopicArgs,
    RosbagSnapshot,
    SetConfigurationArgs,
    SubareasArgs,
    SubcomponentsArgs,
    SystemFaultSnapshotsArgs,
    ToolResult,
    UpdateExecutionArgs,
    filter_entities,
)
from ros2_medkit_mcp.plugin import McpPlugin

logger = logging.getLogger(__name__)


def create_mcp_server(name: str = "ros2_medkit_mcp") -> Server:
    """Create and configure the MCP server.

    Args:
        name: Server name for identification.

    Returns:
        Configured MCP Server instance.
    """
    return Server(name)


def format_result(result: ToolResult) -> list[TextContent]:
    """Format a ToolResult as MCP TextContent.

    Args:
        result: The tool result to format.

    Returns:
        List containing a single TextContent with JSON data.
    """
    return [
        TextContent(
            type="text",
            text=json.dumps(result.model_dump(), indent=2, default=str),
        )
    ]


def format_json_response(data: Any) -> list[TextContent]:
    """Format raw data as MCP TextContent.

    Args:
        data: The data to format as JSON.

    Returns:
        List containing a single TextContent with JSON data.
    """
    return [
        TextContent(
            type="text",
            text=json.dumps(data, indent=2, default=str),
        )
    ]


def format_error(error: str) -> list[TextContent]:
    """Format an error message as MCP TextContent.

    Args:
        error: The error message.

    Returns:
        List containing a single TextContent with error JSON.
    """
    return format_result(ToolResult.fail(error))


# ==================== Fault Formatting Helpers ====================


def format_fault_item(item: FaultItem) -> str:
    """Format a single fault item for LLM readability.

    Args:
        item: The fault item to format.

    Returns:
        Formatted string with fault details.
    """
    lines = [f"Fault: {item.code}"]
    if item.fault_name:
        lines[0] += f" - {item.fault_name}"
    if item.severity:
        lines.append(f"  Severity: {item.severity}")
    if item.status:
        lines.append(
            f"  Status: {item.status.value if hasattr(item.status, 'value') else item.status}"
        )
    if item.is_confirmed is not None:
        lines.append(f"  Confirmed: {item.is_confirmed}")
    if item.is_current is not None:
        lines.append(f"  Current: {item.is_current}")
    if item.counter is not None:
        lines.append(f"  Occurrences: {item.counter}")
    if item.first_occurrence:
        lines.append(f"  First Seen: {item.first_occurrence}")
    if item.last_occurrence:
        lines.append(f"  Last Seen: {item.last_occurrence}")
    return "\n".join(lines)


def format_fault_list(faults: list[dict[str, Any]]) -> list[TextContent]:
    """Format a list of faults for LLM readability.

    Args:
        faults: List of fault dictionaries from the API.

    Returns:
        Formatted TextContent list.
    """
    if not faults:
        return [TextContent(type="text", text="No faults found.")]

    lines = [f"Found {len(faults)} fault(s):\n"]
    for fault_dict in faults:
        try:
            item = FaultItem.model_validate(fault_dict)
            lines.append(format_fault_item(item))
            lines.append("")
        except Exception:
            # Fallback to basic formatting if model validation fails
            code = fault_dict.get("code", "unknown")
            name = fault_dict.get("faultName", "")
            severity = fault_dict.get("severity", "")
            status = fault_dict.get("status", "")
            lines.append(f"Fault: {code}" + (f" - {name}" if name else ""))
            if severity:
                lines.append(f"  Severity: {severity}")
            if status:
                lines.append(f"  Status: {status}")
            lines.append("")

    return [TextContent(type="text", text="\n".join(lines))]


def format_snapshot(snapshot: FreezeFrameSnapshot | RosbagSnapshot) -> str:
    """Format a snapshot for display.

    Args:
        snapshot: A freeze frame or rosbag snapshot.

    Returns:
        Formatted string describing the snapshot.
    """
    lines = [f"  Snapshot: {snapshot.snapshot_id}"]
    lines.append(f"    Timestamp: {snapshot.timestamp}")
    if snapshot.data_source:
        lines.append(f"    Source: {snapshot.data_source}")

    if isinstance(snapshot, RosbagSnapshot):
        lines.append(f"    Download URI: {snapshot.bulk_data_uri}")
        if snapshot.file_size:
            size_mb = snapshot.file_size / (1024 * 1024)
            lines.append(f"    File Size: {size_mb:.2f} MB")
        lines.append(f"    Available: {snapshot.is_available}")
    elif isinstance(snapshot, FreezeFrameSnapshot) and snapshot.data:
        lines.append(f"    Data: {json.dumps(snapshot.data, indent=6, default=str)}")

    return "\n".join(lines)


def format_environment_data(env_data: EnvironmentData) -> str:
    """Format environment data for LLM readability.

    Args:
        env_data: Environment data with snapshots.

    Returns:
        Formatted string describing the environment data.
    """
    lines = ["\nEnvironment Data:"]

    if env_data.extended_data_records:
        records = env_data.extended_data_records

        if records.freeze_frame_snapshots:
            lines.append(f"  Freeze Frame Snapshots ({len(records.freeze_frame_snapshots)}):")
            for snap in records.freeze_frame_snapshots:
                lines.append(format_snapshot(snap))

        if records.rosbag_snapshots:
            lines.append(f"  Rosbag Snapshots ({len(records.rosbag_snapshots)}):")
            for snap in records.rosbag_snapshots:
                lines.append(format_snapshot(snap))

    return "\n".join(lines)


def format_fault_response(fault_data: dict[str, Any]) -> list[TextContent]:
    """Format a fault response with environment data for LLM readability.

    Args:
        fault_data: Fault response dictionary from the API.

    Returns:
        Formatted TextContent list.
    """
    lines = []

    # Parse the fault item
    item_data = fault_data.get("item", fault_data)
    try:
        item = FaultItem.model_validate(item_data)
        lines.append(format_fault_item(item))
    except Exception:
        # Fallback to basic formatting
        code = item_data.get("code", "unknown")
        lines.append(f"Fault: {code}")

    # Parse environment data if present
    env_data_dict = fault_data.get("environmentData") or fault_data.get("environment_data")
    if env_data_dict:
        try:
            env_data = EnvironmentData.model_validate(env_data_dict)
            lines.append(format_environment_data(env_data))
        except Exception:
            # Fallback: just show raw JSON for environment data
            lines.append(f"\nEnvironment Data: {json.dumps(env_data_dict, indent=2, default=str)}")

    # Include x-medkit extensions if present
    x_medkit = fault_data.get("x-medkit") or item_data.get("x-medkit")
    if x_medkit:
        lines.append(f"\nROS 2 MedKit Extensions: {json.dumps(x_medkit, indent=2, default=str)}")

    return [TextContent(type="text", text="\n".join(lines))]


def format_snapshots_response(snapshots_data: dict[str, Any]) -> list[TextContent]:
    """Format a snapshots response for LLM readability.

    Args:
        snapshots_data: Snapshots response dictionary from the API.

    Returns:
        Formatted TextContent list.
    """
    lines = ["Diagnostic Snapshots:"]

    # Try to validate as ExtendedDataRecords
    try:
        records = ExtendedDataRecords.model_validate(snapshots_data)

        if records.freeze_frame_snapshots:
            lines.append(f"\nFreeze Frame Snapshots ({len(records.freeze_frame_snapshots)}):")
            for snap in records.freeze_frame_snapshots:
                lines.append(format_snapshot(snap))

        if records.rosbag_snapshots:
            lines.append(f"\nRosbag Snapshots ({len(records.rosbag_snapshots)}):")
            for snap in records.rosbag_snapshots:
                lines.append(format_snapshot(snap))

        if not records.freeze_frame_snapshots and not records.rosbag_snapshots:
            lines.append("  No snapshots available.")

    except Exception:
        # Fallback to raw JSON
        lines.append(json.dumps(snapshots_data, indent=2, default=str))

    return [TextContent(type="text", text="\n".join(lines))]


# ==================== Bulk Data Formatting ====================


def format_bulkdata_categories(categories: list[str], entity_id: str) -> list[TextContent]:
    """Format bulk-data categories for LLM readability.

    Args:
        categories: List of category names.
        entity_id: Entity identifier for context.

    Returns:
        Formatted TextContent list.
    """
    if not categories:
        return [TextContent(type="text", text=f"No bulk-data categories available for {entity_id}")]

    lines = [f"Bulk-data categories for {entity_id}:"]
    for cat in categories:
        lines.append(f"  - {cat}")

    return [TextContent(type="text", text="\n".join(lines))]


def format_bulkdata_list(
    items: list[dict[str, Any]], entity_id: str, category: str
) -> list[TextContent]:
    """Format bulk-data items list for LLM readability.

    Args:
        items: List of bulk-data item dictionaries.
        entity_id: Entity identifier for context.
        category: Category name.

    Returns:
        Formatted TextContent list.
    """
    if not items:
        return [TextContent(type="text", text=f"No {category} available for {entity_id}")]

    lines = [f"Bulk-data items in {entity_id}/{category} ({len(items)} total):"]

    for item_dict in items:
        try:
            item = BulkDataItem.model_validate(item_dict)
            name = item.name or item.id

            size_str = ""
            if item.size:
                size_mb = item.size / (1024 * 1024)
                size_str = f", {size_mb:.2f} MB"

            date_str = ""
            if item.creation_date:
                # Just show the date portion
                date_str = f", created {item.creation_date[:10]}"

            lines.append(f"  [{item.id}] {name} ({item.mimetype}{size_str}{date_str})")
        except Exception:
            # Fallback formatting
            item_id = item_dict.get("id", "unknown")
            name = item_dict.get("name", item_id)
            lines.append(f"  [{item_id}] {name}")

    return [TextContent(type="text", text="\n".join(lines))]


def format_bulkdata_info(info: dict[str, Any]) -> list[TextContent]:
    """Format bulk-data info for LLM readability.

    Args:
        info: Dictionary with content_type, content_length, filename, uri.

    Returns:
        Formatted TextContent list.
    """
    lines = [f"Bulk-data info for: {info.get('uri', 'unknown')}"]

    if info.get("filename"):
        lines.append(f"  Filename: {info['filename']}")

    lines.append(f"  Content-Type: {info.get('content_type', 'unknown')}")

    if info.get("content_length"):
        size_bytes = int(info["content_length"])
        size_mb = size_bytes / (1024 * 1024)
        lines.append(f"  Size: {size_mb:.2f} MB ({size_bytes} bytes)")

    return [TextContent(type="text", text="\n".join(lines))]


def save_bulk_data_file(
    content: bytes, filename: str | None, bulk_data_uri: str, output_dir: str
) -> list[TextContent]:
    """Save bulk-data content to a file.

    Args:
        content: File content bytes.
        filename: Filename from Content-Disposition header.
        bulk_data_uri: Original URI for fallback filename.
        output_dir: Output directory path.

    Returns:
        Formatted TextContent list with download result.
    """
    output_path = Path(output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    # Generate filename if not provided
    if not filename:
        # Extract from URI (last path component)
        uri_parts = bulk_data_uri.strip("/").split("/")
        filename = uri_parts[-1] if uri_parts else "download"
        # Add extension if missing
        if "." not in filename:
            filename += ".mcap"

    # Sanitize filename to prevent path traversal
    safe_filename = Path(filename).name
    if not safe_filename:
        safe_filename = "download.mcap"

    file_path = (output_path / safe_filename).resolve()
    # Ensure the resolved path is still within output_dir
    if not str(file_path).startswith(str(output_path)):
        raise ValueError(f"Path traversal detected in filename: {filename}")

    file_path.write_bytes(content)

    size_mb = len(content) / (1024 * 1024)
    lines = [
        "Downloaded successfully!",
        f"  File: {file_path}",
        f"  Size: {size_mb:.2f} MB ({len(content)} bytes)",
    ]

    return [TextContent(type="text", text="\n".join(lines))]


async def download_rosbags_for_fault(
    client: SovdClient,
    entity_id: str,
    fault_code: str,
    entity_type: str,
    output_dir: str,
) -> list[TextContent]:
    """Download all rosbag snapshots for a fault.

    Args:
        client: SOVD client instance.
        entity_id: Entity identifier.
        fault_code: Fault code.
        entity_type: Entity type.
        output_dir: Output directory path.

    Returns:
        Formatted TextContent list with download results.
    """
    # Get fault with environment data
    fault_data = await client.get_fault(entity_id, fault_code, entity_type)

    # Extract environment data
    env_data = fault_data.get("environmentData") or fault_data.get("environment_data")
    if not env_data:
        return [
            TextContent(
                type="text",
                text=f"No environment data found for fault {fault_code}",
            )
        ]

    # Get extended data records
    records = env_data.get("extendedDataRecords") or env_data.get("extended_data_records")
    if not records:
        return [
            TextContent(
                type="text",
                text=f"No snapshot data found for fault {fault_code}",
            )
        ]

    # Get rosbag snapshots
    rosbag_snapshots = records.get("rosbagSnapshots") or records.get("rosbag_snapshots", [])
    if not rosbag_snapshots:
        freeze_frames = records.get("freezeFrameSnapshots") or records.get(
            "freeze_frame_snapshots", []
        )
        if freeze_frames:
            return [
                TextContent(
                    type="text",
                    text=f"Fault {fault_code} has only freeze frame snapshots "
                    f"({len(freeze_frames)} total), no rosbag recordings to download.",
                )
            ]
        return [
            TextContent(
                type="text",
                text=f"No rosbag snapshots found for fault {fault_code}",
            )
        ]

    output_path = Path(output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    downloaded: list[str] = []
    errors: list[str] = []

    for snap in rosbag_snapshots:
        snap_id = snap.get("snapshotId") or snap.get("snapshot_id", "unknown")
        bulk_uri = snap.get("bulkDataUri") or snap.get("bulk_data_uri")

        if not bulk_uri:
            errors.append(f"  - {snap_id}: No bulk_data_uri")
            continue

        try:
            content, filename = await client.download_bulk_data(bulk_uri)

            if not filename:
                filename = f"{snap_id}.mcap"

            # Sanitize filename to prevent path traversal
            safe_filename = Path(filename).name or f"{snap_id}.mcap"
            file_path = (output_path / safe_filename).resolve()
            if not str(file_path).startswith(str(output_path)):
                errors.append(f"  - {snap_id}: Path traversal detected in filename")
                continue

            file_path.write_bytes(content)

            size_mb = len(content) / (1024 * 1024)
            downloaded.append(f"  - {filename} ({size_mb:.2f} MB)")

        except Exception as e:
            errors.append(f"  - {snap_id}: {e!s}")

    lines = [f"Downloaded rosbags for fault {fault_code}:"]

    if downloaded:
        lines.append(f"\nSuccessfully downloaded ({len(downloaded)}):")
        lines.extend(downloaded)

    if errors:
        lines.append(f"\nErrors ({len(errors)}):")
        lines.extend(errors)

    lines.append(f"\nOutput directory: {output_path}")

    return [TextContent(type="text", text="\n".join(lines))]


# Map dotted names (from docs) to valid underscore names
TOOL_ALIASES: dict[str, str] = {
    "sovd.version": "sovd_version",
    "sovd_version": "sovd_version",
    "sovd_health": "sovd_health",
    "sovd.entities.list": "sovd_entities_list",
    "sovd_entities_list": "sovd_entities_list",
    "sovd_areas_list": "sovd_areas_list",
    "sovd_area_get": "sovd_area_get",
    "sovd_components_list": "sovd_components_list",
    "sovd_component_get": "sovd_component_get",
    "sovd.entities.get": "sovd_entities_get",
    "sovd_entities_get": "sovd_entities_get",
    "sovd.faults.list": "sovd_faults_list",
    "sovd_faults_list": "sovd_faults_list",
    "sovd_faults_get": "sovd_faults_get",
    "sovd_faults_clear": "sovd_faults_clear",
    # Apps & Functions
    "sovd_apps_list": "sovd_apps_list",
    "sovd_apps_get": "sovd_apps_get",
    "sovd_apps_dependencies": "sovd_apps_dependencies",
    "sovd_functions_list": "sovd_functions_list",
    "sovd_functions_get": "sovd_functions_get",
    "sovd_functions_hosts": "sovd_functions_hosts",
    # Area relationships
    "sovd_area_components": "sovd_area_components",
    "sovd_area_subareas": "sovd_area_subareas",
    "sovd_area_contains": "sovd_area_contains",
    # Component relationships
    "sovd_component_subcomponents": "sovd_component_subcomponents",
    "sovd_component_hosts": "sovd_component_hosts",
    "sovd_component_dependencies": "sovd_component_dependencies",
    # Entity data (entity-agnostic)
    "sovd_entity_data": "sovd_entity_data",
    "sovd_entity_topic_data": "sovd_entity_topic_data",
    "sovd_publish_topic": "sovd_publish_topic",
    # Operations - executions model
    "sovd_list_operations": "sovd_list_operations",
    "sovd_get_operation": "sovd_get_operation",
    "sovd_create_execution": "sovd_create_execution",
    "sovd_list_executions": "sovd_list_executions",
    "sovd_get_execution": "sovd_get_execution",
    "sovd_update_execution": "sovd_update_execution",
    "sovd_cancel_execution": "sovd_cancel_execution",
    # Configurations
    "sovd_list_configurations": "sovd_list_configurations",
    "sovd_get_configuration": "sovd_get_configuration",
    "sovd_set_configuration": "sovd_set_configuration",
    "sovd_delete_configuration": "sovd_delete_configuration",
    "sovd_delete_all_configurations": "sovd_delete_all_configurations",
    # Faults - extended
    "sovd_all_faults_list": "sovd_all_faults_list",
    "sovd_clear_all_faults": "sovd_clear_all_faults",
    "sovd_fault_snapshots": "sovd_fault_snapshots",
    "sovd_system_fault_snapshots": "sovd_system_fault_snapshots",
    # Bulk data
    "sovd_bulkdata_categories": "sovd_bulkdata_categories",
    "sovd_bulkdata_list": "sovd_bulkdata_list",
    "sovd_bulkdata_info": "sovd_bulkdata_info",
    "sovd_bulkdata_download": "sovd_bulkdata_download",
    "sovd_bulkdata_download_for_fault": "sovd_bulkdata_download_for_fault",
}


def register_tools(
    server: Server, client: SovdClient, plugins: list[McpPlugin] | None = None
) -> None:
    """Register all MCP tools on the server.

    Args:
        server: The MCP server to register tools on.
        client: The SOVD client for making API calls.
        plugins: Optional list of plugins providing additional tools.
    """
    # Tool name → plugin mapping, built during list_tools and used for dispatch
    plugin_tool_map: dict[str, McpPlugin] = {}

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available tools."""
        tools = [
            # ==================== Discovery ====================
            Tool(
                name="sovd_version",
                description="Get the SOVD API version information from ros2_medkit gateway. Use this to verify the gateway is running.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            Tool(
                name="sovd_health",
                description="Get health status of the SOVD gateway. Returns service status.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            Tool(
                name="sovd_entities_list",
                description="List all SOVD entities (areas and components combined) with optional substring filtering. This is the primary discovery tool - use it first to explore what's available in the system before querying specific components.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "filter": {
                            "type": "string",
                            "description": "Optional substring filter for entity id or name",
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="sovd_areas_list",
                description="List all SOVD areas (ROS 2 namespaces). Areas are top-level groupings like 'perception', 'control', 'diagnostics'. Use this to discover available areas before listing their components with sovd_area_components.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            Tool(
                name="sovd_area_get",
                description="Get detailed information about a specific area including its capabilities.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "area_id": {
                            "type": "string",
                            "description": "The area identifier",
                        },
                    },
                    "required": ["area_id"],
                },
            ),
            Tool(
                name="sovd_components_list",
                description="List all SOVD components (ROS 2 nodes) across all areas. Returns component IDs that can be used with other tools like sovd_faults_list, sovd_entity_data, etc.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            Tool(
                name="sovd_component_get",
                description="Get detailed information about a specific component including its capabilities.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "component_id": {
                            "type": "string",
                            "description": "The component identifier",
                        },
                    },
                    "required": ["component_id"],
                },
            ),
            Tool(
                name="sovd_entities_get",
                description="Get detailed information about a specific SOVD entity by its identifier, including live data if available. Use sovd_entities_list or sovd_components_list first to discover valid entity IDs.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entity_id": {
                            "type": "string",
                            "description": "The entity identifier to retrieve",
                        },
                    },
                    "required": ["entity_id"],
                },
            ),
            # ==================== Faults ====================
            Tool(
                name="sovd_faults_list",
                description="List all faults for a specific entity. IMPORTANT: First use sovd_components_list or sovd_area_components to discover valid entity IDs.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entity_id": {
                            "type": "string",
                            "description": "The entity identifier (use sovd_entities_list to discover valid IDs)",
                        },
                        "entity_type": {
                            "type": "string",
                            "description": "Entity type: 'components', 'apps', 'areas', or 'functions'",
                            "default": "components",
                        },
                    },
                    "required": ["entity_id"],
                },
            ),
            Tool(
                name="sovd_faults_get",
                description="Get a specific fault by its code from an entity. First use sovd_faults_list to discover available faults.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entity_id": {
                            "type": "string",
                            "description": "The entity identifier",
                        },
                        "fault_id": {
                            "type": "string",
                            "description": "The fault identifier (fault code)",
                        },
                        "entity_type": {
                            "type": "string",
                            "description": "Entity type: 'components', 'apps', 'areas', or 'functions'",
                            "default": "components",
                        },
                    },
                    "required": ["entity_id", "fault_id"],
                },
            ),
            Tool(
                name="sovd_faults_clear",
                description="Clear (acknowledge/dismiss) a fault from an entity. Use sovd_faults_list first to see active faults.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entity_id": {
                            "type": "string",
                            "description": "The entity identifier",
                        },
                        "fault_id": {
                            "type": "string",
                            "description": "The fault identifier to clear",
                        },
                        "entity_type": {
                            "type": "string",
                            "description": "Entity type: 'components', 'apps', 'areas', or 'functions'",
                            "default": "components",
                        },
                    },
                    "required": ["entity_id", "fault_id"],
                },
            ),
            Tool(
                name="sovd_all_faults_list",
                description="List all faults across the entire system. Returns faults from all components.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            Tool(
                name="sovd_clear_all_faults",
                description="Clear all faults for a specific entity. WARNING: This clears ALL active faults for the entity.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entity_id": {
                            "type": "string",
                            "description": "The entity identifier",
                        },
                        "entity_type": {
                            "type": "string",
                            "description": "Entity type: 'components', 'apps', 'areas', or 'functions'",
                            "default": "components",
                        },
                    },
                    "required": ["entity_id"],
                },
            ),
            Tool(
                name="sovd_fault_snapshots",
                description="Get diagnostic snapshots for a specific fault. Contains data captured at fault occurrence time.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entity_id": {
                            "type": "string",
                            "description": "The entity identifier",
                        },
                        "fault_code": {
                            "type": "string",
                            "description": "The fault code",
                        },
                        "entity_type": {
                            "type": "string",
                            "description": "Entity type: 'components', 'apps', 'areas', or 'functions'",
                            "default": "components",
                        },
                    },
                    "required": ["entity_id", "fault_code"],
                },
            ),
            Tool(
                name="sovd_system_fault_snapshots",
                description="Get system-wide diagnostic snapshots for a fault code.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "fault_code": {
                            "type": "string",
                            "description": "The fault code",
                        },
                    },
                    "required": ["fault_code"],
                },
            ),
            Tool(
                name="sovd_area_components",
                description="List all components within a specific area. Use sovd_areas_list first to discover valid area IDs (e.g., 'perception', 'control', 'diagnostics').",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "area_id": {
                            "type": "string",
                            "description": "The area identifier (use sovd_areas_list to discover valid IDs)",
                        },
                    },
                    "required": ["area_id"],
                },
            ),
            Tool(
                name="sovd_area_subareas",
                description="List sub-areas within an area. Use this to explore area hierarchy.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "area_id": {
                            "type": "string",
                            "description": "The area identifier",
                        },
                    },
                    "required": ["area_id"],
                },
            ),
            Tool(
                name="sovd_area_contains",
                description="List all entities contained in an area (components, apps, etc.).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "area_id": {
                            "type": "string",
                            "description": "The area identifier",
                        },
                    },
                    "required": ["area_id"],
                },
            ),
            # ==================== Apps ====================
            Tool(
                name="sovd_apps_list",
                description="List all SOVD apps (ROS 2 nodes). Apps are individual ROS 2 nodes that can have operations, data, configurations, and faults.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            Tool(
                name="sovd_apps_get",
                description="Get detailed information about a specific app by its identifier.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "app_id": {
                            "type": "string",
                            "description": "The app identifier",
                        },
                    },
                    "required": ["app_id"],
                },
            ),
            Tool(
                name="sovd_apps_dependencies",
                description="List dependencies for an app (other apps/components it depends on).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "app_id": {
                            "type": "string",
                            "description": "The app identifier",
                        },
                    },
                    "required": ["app_id"],
                },
            ),
            # ==================== Functions ====================
            Tool(
                name="sovd_functions_list",
                description="List all SOVD functions. Functions are capability groupings that may be hosted by multiple apps.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            Tool(
                name="sovd_functions_get",
                description="Get detailed information about a specific function.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "function_id": {
                            "type": "string",
                            "description": "The function identifier",
                        },
                    },
                    "required": ["function_id"],
                },
            ),
            Tool(
                name="sovd_functions_hosts",
                description="List apps that host a specific function.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "function_id": {
                            "type": "string",
                            "description": "The function identifier",
                        },
                    },
                    "required": ["function_id"],
                },
            ),
            # ==================== Component Relationships ====================
            Tool(
                name="sovd_component_subcomponents",
                description="List subcomponents of a component.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "component_id": {
                            "type": "string",
                            "description": "The component identifier",
                        },
                    },
                    "required": ["component_id"],
                },
            ),
            Tool(
                name="sovd_component_hosts",
                description="List apps hosted by a component.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "component_id": {
                            "type": "string",
                            "description": "The component identifier",
                        },
                    },
                    "required": ["component_id"],
                },
            ),
            Tool(
                name="sovd_component_dependencies",
                description="List dependencies of a component.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "component_id": {
                            "type": "string",
                            "description": "The component identifier",
                        },
                    },
                    "required": ["component_id"],
                },
            ),
            # ==================== Entity Data ====================
            Tool(
                name="sovd_entity_data",
                description="Read all topic data from an entity (returns all topics with their current values). Works with components, apps, areas, and functions.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entity_id": {
                            "type": "string",
                            "description": "The entity identifier",
                        },
                        "entity_type": {
                            "type": "string",
                            "description": "Entity type: 'components', 'apps', 'areas', or 'functions'",
                            "default": "components",
                        },
                    },
                    "required": ["entity_id"],
                },
            ),
            Tool(
                name="sovd_entity_topic_data",
                description="Read data from a specific topic within an entity. Use sovd_entity_data first to discover available topics.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entity_id": {
                            "type": "string",
                            "description": "The entity identifier",
                        },
                        "topic_name": {
                            "type": "string",
                            "description": "The topic name (use sovd_entity_data to discover available topics)",
                        },
                        "entity_type": {
                            "type": "string",
                            "description": "Entity type: 'components', 'apps', 'areas', or 'functions'",
                            "default": "components",
                        },
                    },
                    "required": ["entity_id", "topic_name"],
                },
            ),
            Tool(
                name="sovd_publish_topic",
                description="Publish data to an entity's topic. Use sovd_entity_data first to verify the topic exists and check its message format.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entity_id": {
                            "type": "string",
                            "description": "The entity identifier",
                        },
                        "topic_name": {
                            "type": "string",
                            "description": "The topic name to publish to",
                        },
                        "data": {
                            "type": "object",
                            "description": "The message data to publish as JSON object",
                        },
                        "entity_type": {
                            "type": "string",
                            "description": "Entity type: 'components', 'apps', 'areas', or 'functions'",
                            "default": "components",
                        },
                    },
                    "required": ["entity_id", "topic_name", "data"],
                },
            ),
            # ==================== Operations (Services & Actions) ====================
            Tool(
                name="sovd_list_operations",
                description="List all operations (ROS 2 services and actions) available for an entity. Works with components, apps, areas, and functions.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entity_id": {
                            "type": "string",
                            "description": "The entity identifier",
                        },
                        "entity_type": {
                            "type": "string",
                            "description": "Entity type: 'components', 'apps', 'areas', or 'functions'",
                            "default": "components",
                        },
                    },
                    "required": ["entity_id"],
                },
            ),
            Tool(
                name="sovd_get_operation",
                description="Get details of a specific operation including its schema and capabilities.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entity_id": {
                            "type": "string",
                            "description": "The entity identifier",
                        },
                        "operation_name": {
                            "type": "string",
                            "description": "The operation name",
                        },
                        "entity_type": {
                            "type": "string",
                            "description": "Entity type: 'components', 'apps', 'areas', or 'functions'",
                            "default": "components",
                        },
                    },
                    "required": ["entity_id", "operation_name"],
                },
            ),
            Tool(
                name="sovd_create_execution",
                description="Start an execution for an operation (service call or action goal). For services, returns result directly. For actions, returns execution_id to track progress.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entity_id": {
                            "type": "string",
                            "description": "The entity identifier",
                        },
                        "operation_name": {
                            "type": "string",
                            "description": "The operation name (service or action)",
                        },
                        "request_data": {
                            "type": "object",
                            "description": "Optional request data (goal for actions, request for services)",
                        },
                        "entity_type": {
                            "type": "string",
                            "description": "Entity type: 'components', 'apps', 'areas', or 'functions'",
                            "default": "components",
                        },
                    },
                    "required": ["entity_id", "operation_name"],
                },
            ),
            Tool(
                name="sovd_list_executions",
                description="List all executions for an operation. Use to see execution history and find execution IDs.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entity_id": {
                            "type": "string",
                            "description": "The entity identifier",
                        },
                        "operation_name": {
                            "type": "string",
                            "description": "The operation name",
                        },
                        "entity_type": {
                            "type": "string",
                            "description": "Entity type: 'components', 'apps', 'areas', or 'functions'",
                            "default": "components",
                        },
                    },
                    "required": ["entity_id", "operation_name"],
                },
            ),
            Tool(
                name="sovd_get_execution",
                description="Get execution status and feedback for a specific execution. Use after sovd_create_execution to track action progress.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entity_id": {
                            "type": "string",
                            "description": "The entity identifier",
                        },
                        "operation_name": {
                            "type": "string",
                            "description": "The operation name",
                        },
                        "execution_id": {
                            "type": "string",
                            "description": "The execution identifier",
                        },
                        "entity_type": {
                            "type": "string",
                            "description": "Entity type: 'components', 'apps', 'areas', or 'functions'",
                            "default": "components",
                        },
                    },
                    "required": ["entity_id", "operation_name", "execution_id"],
                },
            ),
            Tool(
                name="sovd_update_execution",
                description="Update an execution (e.g., stop capability). Use to control running actions.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entity_id": {
                            "type": "string",
                            "description": "The entity identifier",
                        },
                        "operation_name": {
                            "type": "string",
                            "description": "The operation name",
                        },
                        "execution_id": {
                            "type": "string",
                            "description": "The execution identifier",
                        },
                        "update_data": {
                            "type": "object",
                            "description": "Update data (e.g., {'stop': true} to stop execution)",
                        },
                        "entity_type": {
                            "type": "string",
                            "description": "Entity type: 'components', 'apps', 'areas', or 'functions'",
                            "default": "components",
                        },
                    },
                    "required": ["entity_id", "operation_name", "execution_id", "update_data"],
                },
            ),
            Tool(
                name="sovd_cancel_execution",
                description="Cancel a specific execution by its ID. Use sovd_list_executions to find the execution_id.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entity_id": {
                            "type": "string",
                            "description": "The entity identifier",
                        },
                        "operation_name": {
                            "type": "string",
                            "description": "The operation name",
                        },
                        "execution_id": {
                            "type": "string",
                            "description": "The execution identifier to cancel",
                        },
                        "entity_type": {
                            "type": "string",
                            "description": "Entity type: 'components', 'apps', 'areas', or 'functions'",
                            "default": "components",
                        },
                    },
                    "required": ["entity_id", "operation_name", "execution_id"],
                },
            ),
            # ==================== Configurations (ROS 2 Parameters) ====================
            Tool(
                name="sovd_list_configurations",
                description="List all configurations (ROS 2 parameters) for an entity. Works with components, apps, areas, and functions.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entity_id": {
                            "type": "string",
                            "description": "The entity identifier",
                        },
                        "entity_type": {
                            "type": "string",
                            "description": "Entity type: 'components', 'apps', 'areas', or 'functions'",
                            "default": "components",
                        },
                    },
                    "required": ["entity_id"],
                },
            ),
            Tool(
                name="sovd_get_configuration",
                description="Get a specific configuration (parameter) value. Use sovd_list_configurations first to discover available parameters.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entity_id": {
                            "type": "string",
                            "description": "The entity identifier",
                        },
                        "param_name": {
                            "type": "string",
                            "description": "The parameter name (use sovd_list_configurations to discover available parameters)",
                        },
                        "entity_type": {
                            "type": "string",
                            "description": "Entity type: 'components', 'apps', 'areas', or 'functions'",
                            "default": "components",
                        },
                    },
                    "required": ["entity_id", "param_name"],
                },
            ),
            Tool(
                name="sovd_set_configuration",
                description="Set a configuration (parameter) value. Use sovd_list_configurations first to discover available parameters and their current values.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entity_id": {
                            "type": "string",
                            "description": "The entity identifier",
                        },
                        "param_name": {
                            "type": "string",
                            "description": "The parameter name",
                        },
                        "value": {
                            "description": "The new parameter value (can be string, number, boolean, or array)",
                        },
                        "entity_type": {
                            "type": "string",
                            "description": "Entity type: 'components', 'apps', 'areas', or 'functions'",
                            "default": "components",
                        },
                    },
                    "required": ["entity_id", "param_name", "value"],
                },
            ),
            Tool(
                name="sovd_delete_configuration",
                description="Reset a configuration (parameter) to its default value. Use sovd_list_configurations first to see current parameter values.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entity_id": {
                            "type": "string",
                            "description": "The entity identifier",
                        },
                        "param_name": {
                            "type": "string",
                            "description": "The parameter name to reset",
                        },
                        "entity_type": {
                            "type": "string",
                            "description": "Entity type: 'components', 'apps', 'areas', or 'functions'",
                            "default": "components",
                        },
                    },
                    "required": ["entity_id", "param_name"],
                },
            ),
            Tool(
                name="sovd_delete_all_configurations",
                description="Reset all configurations (parameters) for an entity to their default values. WARNING: This affects all parameters - use with caution.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entity_id": {
                            "type": "string",
                            "description": "The entity identifier",
                        },
                        "entity_type": {
                            "type": "string",
                            "description": "Entity type: 'components', 'apps', 'areas', or 'functions'",
                            "default": "components",
                        },
                    },
                    "required": ["entity_id"],
                },
            ),
            # ==================== Bulk Data ====================
            Tool(
                name="sovd_bulkdata_categories",
                description="List available bulk-data categories for an entity. Bulk-data categories contain downloadable files like rosbag recordings.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entity_id": {
                            "type": "string",
                            "description": "The entity identifier",
                        },
                        "entity_type": {
                            "type": "string",
                            "description": "Entity type: 'components', 'apps', 'areas', or 'functions'",
                            "default": "apps",
                        },
                    },
                    "required": ["entity_id"],
                },
            ),
            Tool(
                name="sovd_bulkdata_list",
                description="List bulk-data items in a category. Use this to discover available rosbag recordings for download.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entity_id": {
                            "type": "string",
                            "description": "The entity identifier",
                        },
                        "category": {
                            "type": "string",
                            "description": "Category name (e.g., 'rosbags')",
                        },
                        "entity_type": {
                            "type": "string",
                            "description": "Entity type: 'components', 'apps', 'areas', or 'functions'",
                            "default": "apps",
                        },
                    },
                    "required": ["entity_id", "category"],
                },
            ),
            Tool(
                name="sovd_bulkdata_info",
                description="Get information about a specific bulk-data item. Use the bulk_data_uri from fault environment_data snapshots.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "bulk_data_uri": {
                            "type": "string",
                            "description": "Full bulk-data URI path from fault response (e.g., '/apps/motor/bulk-data/rosbags/uuid')",
                        },
                    },
                    "required": ["bulk_data_uri"],
                },
            ),
            Tool(
                name="sovd_bulkdata_download",
                description="Download a bulk-data file (e.g., rosbag recording) to the specified directory. Use the bulk_data_uri from fault environment_data snapshots.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "bulk_data_uri": {
                            "type": "string",
                            "description": "Full bulk-data URI path from fault response",
                        },
                        "output_dir": {
                            "type": "string",
                            "description": "Directory to save the file (default: /tmp)",
                            "default": "/tmp",
                        },
                    },
                    "required": ["bulk_data_uri"],
                },
            ),
            Tool(
                name="sovd_bulkdata_download_for_fault",
                description="Download all rosbag recordings associated with a specific fault. Retrieves the fault's environment_data and downloads all rosbag snapshots.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entity_id": {
                            "type": "string",
                            "description": "The entity identifier",
                        },
                        "fault_code": {
                            "type": "string",
                            "description": "The fault code",
                        },
                        "entity_type": {
                            "type": "string",
                            "description": "Entity type: 'components', 'apps', 'areas', or 'functions'",
                            "default": "apps",
                        },
                        "output_dir": {
                            "type": "string",
                            "description": "Directory to save the files (default: /tmp)",
                            "default": "/tmp",
                        },
                    },
                    "required": ["entity_id", "fault_code"],
                },
            ),
        ]
        # Append plugin tools
        if plugins:
            for plugin in plugins:
                try:
                    plugin_tools = plugin.list_tools()
                    for t in plugin_tools:
                        if t.name in TOOL_ALIASES:
                            logger.warning(
                                "Plugin %s: tool '%s' collides with built-in tool, skipping",
                                plugin.name,
                                t.name,
                            )
                            continue
                        if t.name in plugin_tool_map:
                            logger.warning(
                                "Plugin %s: tool '%s' collides with another plugin tool, skipping",
                                plugin.name,
                                t.name,
                            )
                            continue
                        tools.append(t)
                        plugin_tool_map[t.name] = plugin
                except Exception:
                    logger.exception("Failed to list tools from plugin: %s", plugin.name)
        return tools

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle tool calls.

        Args:
            name: The tool name to call.
            arguments: Tool arguments.

        Returns:
            List of TextContent with the result.
        """
        logger.info("Tool called: %s", name)

        normalized_name = TOOL_ALIASES.get(name, name)

        try:
            if normalized_name == "sovd_version":
                result = await client.get_version()
                return format_json_response(result)

            elif normalized_name == "sovd_entities_list":
                args = EntitiesListArgs(**arguments)
                entities = await client.list_entities()
                filtered = filter_entities(entities, args.filter)
                return format_json_response(filtered)

            elif normalized_name == "sovd_health":
                result = await client.get_health()
                return format_json_response(result)

            elif normalized_name == "sovd_areas_list":
                areas = await client.list_areas()
                return format_json_response(areas)

            elif normalized_name == "sovd_area_get":
                args = AreaIdArgs(**arguments)
                area = await client.get_area(args.area_id)
                return format_json_response(area)

            elif normalized_name == "sovd_components_list":
                components = await client.list_components()
                return format_json_response(components)

            elif normalized_name == "sovd_component_get":
                args = ComponentIdArgs(**arguments)
                component = await client.get_component(args.component_id)
                return format_json_response(component)

            elif normalized_name == "sovd_entities_get":
                args = EntityGetArgs(**arguments)
                entity = await client.get_entity(args.entity_id)
                return format_json_response(entity)

            elif normalized_name == "sovd_faults_list":
                args = FaultsListArgs(**arguments)
                faults = await client.list_faults(args.entity_id, args.entity_type)
                return format_fault_list(faults)

            elif normalized_name == "sovd_faults_get":
                args = FaultGetArgs(**arguments)
                fault = await client.get_fault(args.entity_id, args.fault_id, args.entity_type)
                return format_fault_response(fault)

            elif normalized_name == "sovd_faults_clear":
                args = FaultGetArgs(**arguments)
                result = await client.clear_fault(args.entity_id, args.fault_id, args.entity_type)
                return format_json_response(result)

            elif normalized_name == "sovd_area_components":
                args = AreaComponentsArgs(**arguments)
                components = await client.list_area_components(args.area_id)
                return format_json_response(components)

            elif normalized_name == "sovd_area_subareas":
                args = SubareasArgs(**arguments)
                subareas = await client.list_area_subareas(args.area_id)
                return format_json_response(subareas)

            elif normalized_name == "sovd_area_contains":
                args = AreaContainsArgs(**arguments)
                entities = await client.list_area_contains(args.area_id)
                return format_json_response(entities)

            # ==================== Apps ====================

            elif normalized_name == "sovd_apps_list":
                apps = await client.list_apps()
                return format_json_response(apps)

            elif normalized_name == "sovd_apps_get":
                args = AppIdArgs(**arguments)
                app = await client.get_app(args.app_id)
                return format_json_response(app)

            elif normalized_name == "sovd_apps_dependencies":
                args = AppIdArgs(**arguments)
                deps = await client.list_app_dependencies(args.app_id)
                return format_json_response(deps)

            # ==================== Functions ====================

            elif normalized_name == "sovd_functions_list":
                functions = await client.list_functions()
                return format_json_response(functions)

            elif normalized_name == "sovd_functions_get":
                args = FunctionIdArgs(**arguments)
                func = await client.get_function(args.function_id)
                return format_json_response(func)

            elif normalized_name == "sovd_functions_hosts":
                args = FunctionIdArgs(**arguments)
                hosts = await client.list_function_hosts(args.function_id)
                return format_json_response(hosts)

            # ==================== Component Relationships ====================

            elif normalized_name == "sovd_component_subcomponents":
                args = SubcomponentsArgs(**arguments)
                subs = await client.list_component_subcomponents(args.component_id)
                return format_json_response(subs)

            elif normalized_name == "sovd_component_hosts":
                args = ComponentHostsArgs(**arguments)
                hosts = await client.list_component_hosts(args.component_id)
                return format_json_response(hosts)

            elif normalized_name == "sovd_component_dependencies":
                args = DependenciesArgs(**arguments)
                deps = await client.list_component_dependencies(args.entity_id)
                return format_json_response(deps)

            # ==================== Extended Faults ====================

            elif normalized_name == "sovd_all_faults_list":
                faults = await client.list_all_faults()
                return format_fault_list(faults)

            elif normalized_name == "sovd_clear_all_faults":
                args = ClearAllFaultsArgs(**arguments)
                result = await client.clear_all_faults(args.entity_id, args.entity_type)
                return format_json_response(result)

            elif normalized_name == "sovd_fault_snapshots":
                args = FaultSnapshotsArgs(**arguments)
                snapshots = await client.get_fault_snapshots(
                    args.entity_id, args.fault_code, args.entity_type
                )
                return format_snapshots_response(snapshots)

            elif normalized_name == "sovd_system_fault_snapshots":
                args = SystemFaultSnapshotsArgs(**arguments)
                snapshots = await client.get_system_fault_snapshots(args.fault_code)
                return format_snapshots_response(snapshots)

            # ==================== Entity Data ====================

            elif normalized_name == "sovd_entity_data":
                args = EntityDataArgs(**arguments)
                data = await client.get_component_data(args.entity_id, args.entity_type)
                return format_json_response(data)

            elif normalized_name == "sovd_entity_topic_data":
                args = EntityTopicDataArgs(**arguments)
                data = await client.get_component_topic_data(
                    args.entity_id, args.topic_name, args.entity_type
                )
                return format_json_response(data)

            elif normalized_name == "sovd_publish_topic":
                args = PublishTopicArgs(**arguments)
                result = await client.publish_to_topic(
                    args.entity_id, args.topic_name, args.data, args.entity_type
                )
                return format_json_response(result)

            # ==================== Operations ====================

            elif normalized_name == "sovd_list_operations":
                args = ListOperationsArgs(**arguments)
                operations = await client.list_operations(args.entity_id, args.entity_type)
                return format_json_response(operations)

            elif normalized_name == "sovd_get_operation":
                args = GetOperationArgs(**arguments)
                operation = await client.get_operation(
                    args.entity_id, args.operation_name, args.entity_type
                )
                return format_json_response(operation)

            elif normalized_name == "sovd_create_execution":
                args = CreateExecutionArgs(**arguments)
                result = await client.create_execution(
                    args.entity_id,
                    args.operation_name,
                    args.request_data,
                    args.entity_type,
                )
                return format_json_response(result)

            elif normalized_name == "sovd_list_executions":
                args = ListExecutionsArgs(**arguments)
                executions = await client.list_executions(
                    args.entity_id, args.operation_name, args.entity_type
                )
                return format_json_response(executions)

            elif normalized_name == "sovd_get_execution":
                args = ExecutionArgs(**arguments)
                execution = await client.get_execution(
                    args.entity_id,
                    args.operation_name,
                    args.execution_id,
                    args.entity_type,
                )
                return format_json_response(execution)

            elif normalized_name == "sovd_update_execution":
                args = UpdateExecutionArgs(**arguments)
                result = await client.update_execution(
                    args.entity_id,
                    args.operation_name,
                    args.execution_id,
                    args.request_data,
                    args.entity_type,
                )
                return format_json_response(result)

            elif normalized_name == "sovd_cancel_execution":
                args = ExecutionArgs(**arguments)
                result = await client.cancel_execution(
                    args.entity_id,
                    args.operation_name,
                    args.execution_id,
                    args.entity_type,
                )
                return format_json_response(result)

            # ==================== Configurations ====================

            elif normalized_name == "sovd_list_configurations":
                args = ListConfigurationsArgs(**arguments)
                configs = await client.list_configurations(args.entity_id, args.entity_type)
                return format_json_response(configs)

            elif normalized_name == "sovd_get_configuration":
                args = GetConfigurationArgs(**arguments)
                config = await client.get_configuration(
                    args.entity_id, args.param_name, args.entity_type
                )
                return format_json_response(config)

            elif normalized_name == "sovd_set_configuration":
                args = SetConfigurationArgs(**arguments)
                result = await client.set_configuration(
                    args.entity_id, args.param_name, args.value, args.entity_type
                )
                return format_json_response(result)

            elif normalized_name == "sovd_delete_configuration":
                args = GetConfigurationArgs(**arguments)
                result = await client.delete_configuration(
                    args.entity_id, args.param_name, args.entity_type
                )
                return format_json_response(result)

            elif normalized_name == "sovd_delete_all_configurations":
                args = ListConfigurationsArgs(**arguments)
                result = await client.delete_all_configurations(args.entity_id, args.entity_type)
                return format_json_response(result)

            # ==================== Bulk Data ====================

            elif normalized_name == "sovd_bulkdata_categories":
                args = BulkDataCategoriesArgs(**arguments)
                categories = await client.list_bulk_data_categories(
                    args.entity_id, args.entity_type
                )
                return format_bulkdata_categories(categories, args.entity_id)

            elif normalized_name == "sovd_bulkdata_list":
                args = BulkDataListArgs(**arguments)
                items = await client.list_bulk_data(args.entity_id, args.category, args.entity_type)
                return format_bulkdata_list(items, args.entity_id, args.category)

            elif normalized_name == "sovd_bulkdata_info":
                args = BulkDataInfoArgs(**arguments)
                info = await client.get_bulk_data_info(args.bulk_data_uri)
                return format_bulkdata_info(info)

            elif normalized_name == "sovd_bulkdata_download":
                args = BulkDataDownloadArgs(**arguments)
                content, filename = await client.download_bulk_data(args.bulk_data_uri)
                return save_bulk_data_file(content, filename, args.bulk_data_uri, args.output_dir)

            elif normalized_name == "sovd_bulkdata_download_for_fault":
                args = BulkDataDownloadForFaultArgs(**arguments)
                return await download_rosbags_for_fault(
                    client, args.entity_id, args.fault_code, args.entity_type, args.output_dir
                )

            else:
                # Check plugin tool map before reporting unknown tool
                plugin = plugin_tool_map.get(normalized_name)
                if plugin is not None:
                    return await plugin.call_tool(normalized_name, arguments)
                return format_error(f"Unknown tool: {name}")

        except SovdClientError as e:
            error_msg = str(e)
            if e.request_id:
                error_msg += f" (request_id: {e.request_id})"
            logger.error("Tool %s failed: %s", name, error_msg)
            return format_error(error_msg)
        except Exception as e:
            logger.exception("Unexpected error in tool %s", name)
            return format_error(f"Internal error: {e}")


def register_resources(server: Server) -> None:
    """Register all MCP resources on the server.

    Args:
        server: The MCP server to register resources on.
    """

    @server.list_resources()
    async def list_resources() -> list[Resource]:
        """List available resources."""
        return [
            Resource(
                uri="sovd://openapi",
                name="SOVD OpenAPI Specification",
                description="Information about the SOVD OpenAPI specification",
                mimeType="text/plain",
            ),
        ]

    @server.read_resource()
    async def read_resource(uri: str) -> list[TextContent]:
        """Read a resource by URI.

        Args:
            uri: The resource URI to read.

        Returns:
            Resource content as MCP text.
        """
        if uri == "sovd://openapi":
            content = (
                "The OpenAPI specification for the SOVD API should be fetched "
                "directly from the ros2_medkit gateway.\n\n"
                "Typically available at: GET /openapi.json or GET /docs\n\n"
                "This is a placeholder resource. Configure your ros2_medkit "
                "gateway URL via the ROS2_MEDKIT_BASE_URL environment variable "
                "and access the API documentation directly from the gateway."
            )
            return [TextContent(type="text", text=content)]
        raise ValueError(f"Unknown resource URI: {uri}")


def setup_mcp_app(
    server: Server, settings: Settings, client: SovdClient, plugins: list[McpPlugin] | None = None
) -> None:
    """Set up the complete MCP application.

    Args:
        server: The MCP server to configure.
        settings: Application settings.
        client: The SOVD client for API calls.
        plugins: Optional list of plugins providing additional tools.
    """
    register_tools(server, client, plugins=plugins)
    register_resources(server)
    logger.info(
        "MCP server configured for %s",
        settings.base_url,
    )
