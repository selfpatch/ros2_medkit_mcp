"""Pytest configuration for ros2_medkit_mcp tests.

Disables ROS 2 launch_testing plugins that conflict with standard pytest.
"""

import sys

# Remove ROS 2 paths to avoid plugin conflicts
sys.path = [p for p in sys.path if "/opt/ros" not in p]

# Disable problematic ROS 2 plugins by blocking their collection
collect_ignore_glob = ["**/launch_test_*.py"]


def pytest_configure(config):
    """Configure pytest to work without ROS 2 launch plugins."""
    # Unregister launch_testing_ros plugin if loaded
    plugin_manager = config.pluginmanager

    # Try to unregister problematic plugins
    for plugin_name in [
        "launch_testing_ros_pytest_entrypoint",
        "launch_testing.pytest_entry_point",
    ]:
        try:
            plugin = plugin_manager.get_plugin(plugin_name)
            if plugin:
                plugin_manager.unregister(plugin)
        except Exception:
            pass
