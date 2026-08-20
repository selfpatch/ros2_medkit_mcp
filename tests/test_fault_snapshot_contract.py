"""The snapshot shape a real gateway sends, driven through the real formatters.

These tests exist because the ones they sat beside did not: the formatter read
``extended_data_records.rosbagSnapshots``, a container the gateway has never
populated, and every fixture around it was built from that same fiction - so the
suite was green while the MCP server showed no snapshot for any fault, ever.

``fixtures/fault_detail_two_recordings.json`` was captured from a running
gateway holding a fault that came back twice (ros2_medkit#620); the rosbag
``x-medkit.captured_at`` entries mirror what that branch's fault handler emits
per recording. The fixture is the wire here - it cannot catch the gateway
moving the shape again on its own - so every test below pushes it through the
``src/`` formatters and asserts on their OUTPUT, where a src regression can
actually fail.
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
        # Since #620 the capture time is the only field that tells one
        # occurrence's bag from another's - it must survive per recording, not
        # only on the freeze frame.
        assert recording["x-medkit"]["captured_at"] in output


def test_a_long_history_reaches_the_output_whole() -> None:
    """No hidden cap: ``max_bags_per_fault`` allows dozens, and a fault with
    more recordings than the fixture's two must list every one."""
    snapshots = [
        {
            "type": "rosbag",
            "name": f"rosbag_fault_X_{i}",
            "bulk_data_uri": f"/apps/probe/bulk-data/rosbags/fault_X_{i}",
            "size_bytes": 1024,
            "duration_sec": 2.0,
            "format": "mcap",
            "x-medkit": {"captured_at": f"2026-08-15T16:05:0{i}.000Z"},
        }
        for i in range(5)
    ]
    env = EnvironmentData.model_validate({"snapshots": snapshots})
    output = format_environment_data(env)

    assert "Rosbag Recordings (5):" in output
    for i in range(5):
        assert f"/apps/probe/bulk-data/rosbags/fault_X_{i}" in output


def test_the_freeze_frame_survives_the_same_trip(gateway_response: dict[str, Any]) -> None:
    """Freeze frames were lost to the same wrong container, not just rosbags."""
    env = EnvironmentData.model_validate(gateway_response["environment_data"])
    output = format_environment_data(env)

    assert "Freeze Frame Snapshots (1):" in output
    # captured_at is nested under the x-medkit extension rather than sitting at
    # the top level, so a model that reads it flat renders nothing here.
    assert "Captured At:" in output
    # The captured VALUE, not only its heading: the whole point of a freeze
    # frame is the reading at the moment of the trip.
    assert "Data: 1" in output


def test_the_whole_response_formats_without_losing_the_recordings(
    gateway_response: dict[str, Any],
) -> None:
    """The path the MCP tool actually calls, end to end on a real payload."""
    text = format_fault_response(gateway_response)[0].text

    # The fault itself must survive the trip: the gateway sends severity as a
    # number and status as an object, and a FaultItem that rejects them used to
    # silently reduce this whole header to one bare code line.
    assert "E2E_FLAPPING_SENSOR - Intermittent sensor dropout seen twice" in text
    assert "Severity: 2 (ERROR)" in text
    assert "Status: active" in text
    assert "First Occurrence: 2026-08-15T16:05:49.981Z" in text

    assert "Rosbag Recordings (2):" in text
    for recording in [
        s for s in gateway_response["environment_data"]["snapshots"] if s["type"] == "rosbag"
    ]:
        assert recording["bulk_data_uri"] in text
