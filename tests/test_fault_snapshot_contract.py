"""The snapshot shape a real gateway sends, captured from one.

These tests exist because the ones they sit beside did not. The formatter and the
rosbag download tool both read ``extended_data_records.rosbagSnapshots``, a
container the gateway has never populated, and every test around them built its
fixtures from that same fiction - so the suite was green while the MCP server
showed no snapshot for any fault, ever.

``fixtures/fault_detail_two_recordings.json`` is a verbatim response from a
running gateway holding a fault that came back twice (ros2_medkit#620), so this
file fails the moment the wire shape and the code disagree again.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ros2_medkit_mcp.mcp_app import format_environment_data, format_fault_response
from ros2_medkit_mcp.models import EnvironmentData

FIXTURE = Path(__file__).parent / "fixtures" / "fault_detail_two_recordings.json"


@pytest.fixture
def gateway_response() -> dict[str, Any]:
    """A real fault detail, straight off a gateway."""
    # Explicit encoding: the fixture is UTF-8 regardless of the runner's locale.
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_snapshots_live_beside_extended_data_records_not_inside_them(
    gateway_response: dict[str, Any],
) -> None:
    """Pin where the gateway actually puts them.

    Everything downstream was reading the wrong container; this is the assertion
    that would have caught it.
    """
    env = gateway_response["environment_data"]

    assert "snapshots" in env
    assert {s["type"] for s in env["snapshots"]} == {"freeze_frame", "rosbag"}

    records = env.get("extended_data_records", {})
    assert "rosbagSnapshots" not in records
    assert "rosbag_snapshots" not in records
    assert set(records) <= {"first_occurrence", "last_occurrence"}


def test_a_fault_that_came_back_keeps_a_recording_per_occurrence(
    gateway_response: dict[str, Any],
) -> None:
    """Two occurrences, two bags, each with its own id in name and URI."""
    recordings = [
        s for s in gateway_response["environment_data"]["snapshots"] if s["type"] == "rosbag"
    ]

    assert len(recordings) == 2
    assert len({r["bulk_data_uri"] for r in recordings}) == 2
    assert len({r["name"] for r in recordings}) == 2
    for recording in recordings:
        # The last URI segment is the recording id, and it is what the name is
        # built from - that is the pairing a client relies on to download one
        # specific occurrence.
        assert recording["bulk_data_uri"].rsplit("/", 1)[-1] in recording["name"]


def test_the_formatter_surfaces_both_recordings(gateway_response: dict[str, Any]) -> None:
    """Both bags reach the model output, each with a URI an LLM can act on."""
    env = EnvironmentData.model_validate(gateway_response["environment_data"])
    output = format_environment_data(env)

    assert "Rosbag Recordings (2):" in output
    for recording in [
        s for s in gateway_response["environment_data"]["snapshots"] if s["type"] == "rosbag"
    ]:
        assert recording["bulk_data_uri"] in output


def test_the_freeze_frame_survives_the_same_trip(gateway_response: dict[str, Any]) -> None:
    """Freeze frames were lost to the same wrong container, not just rosbags."""
    env = EnvironmentData.model_validate(gateway_response["environment_data"])
    output = format_environment_data(env)

    assert "Freeze Frame Snapshots (1):" in output
    # captured_at is nested under the x-medkit extension rather than sitting at
    # the top level, so a model that reads it flat renders nothing here.
    assert "Captured At:" in output


def test_the_whole_response_formats_without_losing_the_recordings(
    gateway_response: dict[str, Any],
) -> None:
    """The path the MCP tool actually calls, end to end on a real payload."""
    text = format_fault_response(gateway_response)[0].text

    assert "Rosbag Recordings (2):" in text
    for recording in [
        s for s in gateway_response["environment_data"]["snapshots"] if s["type"] == "rosbag"
    ]:
        assert recording["bulk_data_uri"] in text
