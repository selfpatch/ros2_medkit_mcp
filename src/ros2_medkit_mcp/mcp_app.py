"""MCP application with tools and resources for ros2_medkit SOVD API.

This module defines the MCP server with all tools and resources,
intended to be reused by both stdio and HTTP transport entrypoints.
"""

import json
import logging
from typing import Any

from mcp.server import Server
from mcp.types import Resource, TextContent, Tool

from ros2_medkit_mcp.client import SovdClient, SovdClientError
from ros2_medkit_mcp.config import Settings
from ros2_medkit_mcp.models import (
    AppIdArgs,
    AreaComponentsArgs,
    AreaContainsArgs,
    ClearAllFaultsArgs,
    ComponentDataArgs,
    ComponentHostsArgs,
    ComponentTopicDataArgs,
    CreateExecutionArgs,
    EntitiesListArgs,
    EntityGetArgs,
    ExecutionArgs,
    FaultGetArgs,
    FaultSnapshotsArgs,
    FaultsListArgs,
    FunctionIdArgs,
    GetConfigurationArgs,
    GetOperationArgs,
    ListConfigurationsArgs,
    ListExecutionsArgs,
    ListOperationsArgs,
    PublishTopicArgs,
    SetConfigurationArgs,
    SubareasArgs,
    SubcomponentsArgs,
    SystemFaultSnapshotsArgs,
    ToolResult,
    filter_entities,
)

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


# Map dotted names (from docs) to valid underscore names
TOOL_ALIASES: dict[str, str] = {
    "sovd.version": "sovd_version",
    "sovd_version": "sovd_version",
    "sovd.entities.list": "sovd_entities_list",
    "sovd_entities_list": "sovd_entities_list",
    "sovd_areas_list": "sovd_areas_list",
    "sovd_components_list": "sovd_components_list",
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
    # Component data
    "sovd_component_data": "sovd_component_data",
    "sovd_component_topic_data": "sovd_component_topic_data",
    "sovd_publish_topic": "sovd_publish_topic",
    # Operations - executions model
    "sovd_list_operations": "sovd_list_operations",
    "sovd_get_operation": "sovd_get_operation",
    "sovd_create_execution": "sovd_create_execution",
    "sovd_list_executions": "sovd_list_executions",
    "sovd_get_execution": "sovd_get_execution",
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
}


def register_tools(server: Server, client: SovdClient) -> None:
    """Register all MCP tools on the server.

    Args:
        server: The MCP server to register tools on.
        client: The SOVD client for making API calls.
    """

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available tools."""
        return [
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
                name="sovd_components_list",
                description="List all SOVD components (ROS 2 nodes) across all areas. Returns component IDs that can be used with other tools like sovd_faults_list, sovd_component_data, etc.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
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
            Tool(
                name="sovd_faults_list",
                description="List all faults for a specific component. IMPORTANT: First use sovd_components_list or sovd_area_components to discover valid component IDs. Component ID must match exactly (e.g., 'lidar_sensor', 'temp_sensor').",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "component_id": {
                            "type": "string",
                            "description": "The component identifier (use sovd_components_list to discover valid IDs)",
                        },
                    },
                    "required": ["component_id"],
                },
            ),
            Tool(
                name="sovd_faults_get",
                description="Get a specific fault by its code from a component. First use sovd_faults_list to discover available faults for the component.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "component_id": {
                            "type": "string",
                            "description": "The component identifier",
                        },
                        "fault_id": {
                            "type": "string",
                            "description": "The fault identifier (fault code)",
                        },
                    },
                    "required": ["component_id", "fault_id"],
                },
            ),
            Tool(
                name="sovd_faults_clear",
                description="Clear (acknowledge/dismiss) a fault from a component. Use sovd_faults_list first to see active faults.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "component_id": {
                            "type": "string",
                            "description": "The component identifier",
                        },
                        "fault_id": {
                            "type": "string",
                            "description": "The fault identifier to clear",
                        },
                    },
                    "required": ["component_id", "fault_id"],
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
            # ==================== Component Data ====================
            Tool(
                name="sovd_component_data",
                description="Read all topic data from a component (returns all topics with their current values). Use sovd_components_list first to discover valid component IDs.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "component_id": {
                            "type": "string",
                            "description": "The component identifier (use sovd_components_list to discover valid IDs)",
                        },
                    },
                    "required": ["component_id"],
                },
            ),
            Tool(
                name="sovd_component_topic_data",
                description="Read data from a specific topic within a component. Use sovd_component_data first to discover available topics for the component.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "component_id": {
                            "type": "string",
                            "description": "The component identifier",
                        },
                        "topic_name": {
                            "type": "string",
                            "description": "The topic name (use sovd_component_data to discover available topics)",
                        },
                    },
                    "required": ["component_id", "topic_name"],
                },
            ),
            Tool(
                name="sovd_publish_topic",
                description="Publish data to a component's topic. Use sovd_component_data first to verify the topic exists and check its message format.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "component_id": {
                            "type": "string",
                            "description": "The component identifier",
                        },
                        "topic_name": {
                            "type": "string",
                            "description": "The topic name to publish to",
                        },
                        "data": {
                            "type": "object",
                            "description": "The message data to publish as JSON object",
                        },
                    },
                    "required": ["component_id", "topic_name", "data"],
                },
            ),
            # ==================== Operations (Services & Actions) ====================
            Tool(
                name="sovd_list_operations",
                description="List all operations (ROS 2 services and actions) available for an entity. Use sovd_components_list or sovd_apps_list first to discover valid entity IDs.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "component_id": {
                            "type": "string",
                            "description": "The entity identifier (use sovd_components_list to discover valid IDs)",
                        },
                    },
                    "required": ["component_id"],
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
                description="List all configurations (ROS 2 parameters) for a component. Use sovd_components_list first to discover valid component IDs.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "component_id": {
                            "type": "string",
                            "description": "The component identifier (use sovd_components_list to discover valid IDs)",
                        },
                    },
                    "required": ["component_id"],
                },
            ),
            Tool(
                name="sovd_get_configuration",
                description="Get a specific configuration (parameter) value. Use sovd_list_configurations first to discover available parameters for the component.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "component_id": {
                            "type": "string",
                            "description": "The component identifier",
                        },
                        "param_name": {
                            "type": "string",
                            "description": "The parameter name (use sovd_list_configurations to discover available parameters)",
                        },
                    },
                    "required": ["component_id", "param_name"],
                },
            ),
            Tool(
                name="sovd_set_configuration",
                description="Set a configuration (parameter) value. Use sovd_list_configurations first to discover available parameters and their current values.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "component_id": {
                            "type": "string",
                            "description": "The component identifier",
                        },
                        "param_name": {
                            "type": "string",
                            "description": "The parameter name",
                        },
                        "value": {
                            "description": "The new parameter value (can be string, number, boolean, or array)",
                        },
                    },
                    "required": ["component_id", "param_name", "value"],
                },
            ),
            Tool(
                name="sovd_delete_configuration",
                description="Reset a configuration (parameter) to its default value. Use sovd_list_configurations first to see current parameter values.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "component_id": {
                            "type": "string",
                            "description": "The component identifier",
                        },
                        "param_name": {
                            "type": "string",
                            "description": "The parameter name to reset",
                        },
                    },
                    "required": ["component_id", "param_name"],
                },
            ),
            Tool(
                name="sovd_delete_all_configurations",
                description="Reset all configurations (parameters) for a component to their default values. WARNING: This affects all parameters - use with caution.",
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
        ]

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

            elif normalized_name == "sovd_areas_list":
                areas = await client.list_areas()
                return format_json_response(areas)

            elif normalized_name == "sovd_components_list":
                components = await client.list_components()
                return format_json_response(components)

            elif normalized_name == "sovd_entities_get":
                args = EntityGetArgs(**arguments)
                entity = await client.get_entity(args.entity_id)
                return format_json_response(entity)

            elif normalized_name == "sovd_faults_list":
                args = FaultsListArgs(**arguments)
                faults = await client.list_faults(args.component_id)
                return format_json_response(faults)

            elif normalized_name == "sovd_faults_get":
                args = FaultGetArgs(**arguments)
                fault = await client.get_fault(args.component_id, args.fault_id)
                return format_json_response(fault)

            elif normalized_name == "sovd_faults_clear":
                args = FaultGetArgs(**arguments)
                result = await client.clear_fault(args.component_id, args.fault_id)
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
                args = SubcomponentsArgs(**arguments)
                deps = await client.list_component_dependencies(args.component_id)
                return format_json_response(deps)

            # ==================== Extended Faults ====================

            elif normalized_name == "sovd_all_faults_list":
                faults = await client.list_all_faults()
                return format_json_response(faults)

            elif normalized_name == "sovd_clear_all_faults":
                args = ClearAllFaultsArgs(**arguments)
                result = await client.clear_all_faults(
                    args.entity_id, args.entity_type
                )
                return format_json_response(result)

            elif normalized_name == "sovd_fault_snapshots":
                args = FaultSnapshotsArgs(**arguments)
                snapshots = await client.get_fault_snapshots(
                    args.entity_id, args.fault_code, args.entity_type
                )
                return format_json_response(snapshots)

            elif normalized_name == "sovd_system_fault_snapshots":
                args = SystemFaultSnapshotsArgs(**arguments)
                snapshots = await client.get_system_fault_snapshots(args.fault_code)
                return format_json_response(snapshots)

            # ==================== Component Data ====================

            elif normalized_name == "sovd_component_data":
                args = ComponentDataArgs(**arguments)
                data = await client.get_component_data(args.component_id)
                return format_json_response(data)

            elif normalized_name == "sovd_component_topic_data":
                args = ComponentTopicDataArgs(**arguments)
                data = await client.get_component_topic_data(
                    args.component_id, args.topic_name
                )
                return format_json_response(data)

            elif normalized_name == "sovd_publish_topic":
                args = PublishTopicArgs(**arguments)
                result = await client.publish_to_topic(
                    args.component_id, args.topic_name, args.data
                )
                return format_json_response(result)

            # ==================== Operations ====================

            elif normalized_name == "sovd_list_operations":
                args = ListOperationsArgs(**arguments)
                operations = await client.list_operations(args.component_id)
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
                configs = await client.list_configurations(args.component_id)
                return format_json_response(configs)

            elif normalized_name == "sovd_get_configuration":
                args = GetConfigurationArgs(**arguments)
                config = await client.get_configuration(
                    args.component_id, args.param_name
                )
                return format_json_response(config)

            elif normalized_name == "sovd_set_configuration":
                args = SetConfigurationArgs(**arguments)
                result = await client.set_configuration(
                    args.component_id, args.param_name, args.value
                )
                return format_json_response(result)

            elif normalized_name == "sovd_delete_configuration":
                args = GetConfigurationArgs(**arguments)
                result = await client.delete_configuration(
                    args.component_id, args.param_name
                )
                return format_json_response(result)

            elif normalized_name == "sovd_delete_all_configurations":
                args = ListConfigurationsArgs(**arguments)
                result = await client.delete_all_configurations(args.component_id)
                return format_json_response(result)

            else:
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


def setup_mcp_app(server: Server, settings: Settings, client: SovdClient) -> None:
    """Set up the complete MCP application.

    Args:
        server: The MCP server to configure.
        settings: Application settings.
        client: The SOVD client for API calls.
    """
    register_tools(server, client)
    register_resources(server)
    logger.info(
        "MCP server configured for %s",
        settings.base_url,
    )
