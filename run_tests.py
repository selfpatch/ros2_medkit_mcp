#!/usr/bin/env python3
"""Run tests in isolation from ROS 2 environment.

This script removes ROS 2 paths from sys.path before running pytest
to avoid conflicts with launch_testing plugins.
"""

import sys

# Remove ROS 2 paths before importing pytest
sys.path = [p for p in sys.path if '/opt/ros' not in p]

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main(sys.argv[1:] or ["-v", "tests/"]))
