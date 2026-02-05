"""Tests for fault formatting functions and response models."""

from mcp.types import TextContent

from ros2_medkit_mcp.mcp_app import (
    format_environment_data,
    format_fault_item,
    format_fault_list,
    format_fault_response,
    format_snapshot,
    format_snapshots_response,
)
from ros2_medkit_mcp.models import (
    EnvironmentData,
    ExtendedDataRecords,
    FaultItem,
    FaultResponse,
    FaultStatus,
    FreezeFrameSnapshot,
    RosbagSnapshot,
)


class TestFaultItemModel:
    """Tests for FaultItem Pydantic model."""

    def test_minimal_fault_item(self) -> None:
        """Test FaultItem with only required fields."""
        item = FaultItem(code="P0123")
        assert item.code == "P0123"
        assert item.fault_name is None
        assert item.severity is None

    def test_full_fault_item(self) -> None:
        """Test FaultItem with all fields."""
        item = FaultItem(
            code="P0123",
            fault_name="Engine Overtemp",
            severity="critical",
            status=FaultStatus.ACTIVE,
            is_confirmed=True,
            is_current=True,
            counter=3,
            first_occurrence="2025-01-01T00:00:00Z",
            last_occurrence="2025-01-02T00:00:00Z",
        )
        assert item.code == "P0123"
        assert item.fault_name == "Engine Overtemp"
        assert item.severity == "critical"
        assert item.status == FaultStatus.ACTIVE
        assert item.is_confirmed is True
        assert item.counter == 3

    def test_fault_item_from_api_response(self) -> None:
        """Test FaultItem validation from API response with camelCase."""
        api_data = {
            "code": "P0456",
            "faultName": "Sensor Failure",
            "severity": "warning",
            "status": "ACTIVE",
            "isConfirmed": True,
            "isCurrent": False,
            "counter": 5,
            "firstOccurrence": "2025-01-01T10:00:00Z",
            "lastOccurrence": "2025-01-01T12:00:00Z",
        }
        item = FaultItem.model_validate(api_data)
        assert item.code == "P0456"
        assert item.fault_name == "Sensor Failure"
        assert item.is_confirmed is True
        assert item.is_current is False


class TestSnapshotModels:
    """Tests for snapshot Pydantic models."""

    def test_freeze_frame_snapshot(self) -> None:
        """Test FreezeFrameSnapshot model."""
        snap = FreezeFrameSnapshot(
            snapshot_id="snap-001",
            timestamp="2025-01-01T00:00:00Z",
            data_source="/temperature",
            data={"value": 85.5, "unit": "celsius"},
        )
        assert snap.snapshot_id == "snap-001"
        assert snap.data["value"] == 85.5

    def test_freeze_frame_from_api(self) -> None:
        """Test FreezeFrameSnapshot from API response."""
        api_data = {
            "snapshotId": "snap-002",
            "timestamp": "2025-01-01T00:00:00Z",
            "dataSource": "/sensor/data",
            "data": {"temp": 100},
        }
        snap = FreezeFrameSnapshot.model_validate(api_data)
        assert snap.snapshot_id == "snap-002"
        assert snap.data_source == "/sensor/data"

    def test_rosbag_snapshot(self) -> None:
        """Test RosbagSnapshot model."""
        snap = RosbagSnapshot(
            snapshot_id="rosbag-001",
            timestamp="2025-01-01T00:00:00Z",
            bulk_data_uri="/api/v1/bulk-data/rosbag-001.db3",
            file_size=1024000,
            is_available=True,
        )
        assert snap.snapshot_id == "rosbag-001"
        assert snap.bulk_data_uri == "/api/v1/bulk-data/rosbag-001.db3"
        assert snap.file_size == 1024000

    def test_rosbag_from_api(self) -> None:
        """Test RosbagSnapshot from API response."""
        api_data = {
            "snapshotId": "rosbag-002",
            "timestamp": "2025-01-01T00:00:00Z",
            "bulkDataUri": "/api/v1/bulk-data/file.db3",
            "fileSize": 2048000,
            "isAvailable": False,
        }
        snap = RosbagSnapshot.model_validate(api_data)
        assert snap.snapshot_id == "rosbag-002"
        assert snap.bulk_data_uri == "/api/v1/bulk-data/file.db3"
        assert snap.is_available is False


class TestExtendedDataRecords:
    """Tests for ExtendedDataRecords model."""

    def test_empty_records(self) -> None:
        """Test ExtendedDataRecords with empty lists."""
        records = ExtendedDataRecords()
        assert records.freeze_frame_snapshots == []
        assert records.rosbag_snapshots == []

    def test_records_with_snapshots(self) -> None:
        """Test ExtendedDataRecords with both snapshot types."""
        freeze = FreezeFrameSnapshot(
            snapshot_id="ff-1",
            timestamp="2025-01-01T00:00:00Z",
            data={"key": "value"},
        )
        rosbag = RosbagSnapshot(
            snapshot_id="rb-1",
            timestamp="2025-01-01T00:00:00Z",
            bulk_data_uri="/bulk-data/file.db3",
        )
        records = ExtendedDataRecords(
            freeze_frame_snapshots=[freeze],
            rosbag_snapshots=[rosbag],
        )
        assert len(records.freeze_frame_snapshots) == 1
        assert len(records.rosbag_snapshots) == 1

    def test_records_from_api(self) -> None:
        """Test ExtendedDataRecords from API response."""
        api_data = {
            "freezeFrameSnapshots": [
                {"snapshotId": "ff-1", "timestamp": "2025-01-01T00:00:00Z", "data": {}}
            ],
            "rosbagSnapshots": [
                {
                    "snapshotId": "rb-1",
                    "timestamp": "2025-01-01T00:00:00Z",
                    "bulkDataUri": "/bulk-data/test.db3",
                }
            ],
        }
        records = ExtendedDataRecords.model_validate(api_data)
        assert len(records.freeze_frame_snapshots) == 1
        assert len(records.rosbag_snapshots) == 1
        assert records.rosbag_snapshots[0].bulk_data_uri == "/bulk-data/test.db3"


class TestEnvironmentData:
    """Tests for EnvironmentData model."""

    def test_empty_environment_data(self) -> None:
        """Test EnvironmentData without records."""
        env = EnvironmentData()
        assert env.extended_data_records is None

    def test_environment_data_with_records(self) -> None:
        """Test EnvironmentData with ExtendedDataRecords."""
        records = ExtendedDataRecords(
            freeze_frame_snapshots=[
                FreezeFrameSnapshot(
                    snapshot_id="ff-1",
                    timestamp="2025-01-01T00:00:00Z",
                    data={"sensor": "value"},
                )
            ]
        )
        env = EnvironmentData(extended_data_records=records)
        assert env.extended_data_records is not None
        assert len(env.extended_data_records.freeze_frame_snapshots) == 1

    def test_environment_from_api(self) -> None:
        """Test EnvironmentData from API response."""
        api_data = {
            "extendedDataRecords": {
                "freezeFrameSnapshots": [
                    {"snapshotId": "ff-1", "timestamp": "2025-01-01T00:00:00Z", "data": {}}
                ],
                "rosbagSnapshots": [],
            }
        }
        env = EnvironmentData.model_validate(api_data)
        assert env.extended_data_records is not None
        assert len(env.extended_data_records.freeze_frame_snapshots) == 1


class TestFaultResponse:
    """Tests for FaultResponse model."""

    def test_fault_response_minimal(self) -> None:
        """Test FaultResponse with minimal data."""
        item = FaultItem(code="P0123")
        response = FaultResponse(item=item)
        assert response.item.code == "P0123"
        assert response.environment_data is None

    def test_fault_response_with_env_data(self) -> None:
        """Test FaultResponse with environment data."""
        item = FaultItem(code="P0123", fault_name="Test Fault")
        env = EnvironmentData(
            extended_data_records=ExtendedDataRecords(
                rosbag_snapshots=[
                    RosbagSnapshot(
                        snapshot_id="rb-1",
                        timestamp="2025-01-01T00:00:00Z",
                        bulk_data_uri="/bulk-data/test.db3",
                    )
                ]
            )
        )
        response = FaultResponse(item=item, environment_data=env)
        assert response.item.code == "P0123"
        assert response.environment_data is not None
        assert len(response.environment_data.extended_data_records.rosbag_snapshots) == 1


class TestFormatFaultItem:
    """Tests for format_fault_item function."""

    def test_format_minimal_fault(self) -> None:
        """Test formatting fault with only code."""
        item = FaultItem(code="P0123")
        output = format_fault_item(item)
        assert "Fault: P0123" in output

    def test_format_full_fault(self) -> None:
        """Test formatting fault with all details."""
        item = FaultItem(
            code="P0123",
            fault_name="Engine Overtemp",
            severity="critical",
            status=FaultStatus.ACTIVE,
            is_confirmed=True,
            counter=5,
            first_occurrence="2025-01-01T00:00:00Z",
        )
        output = format_fault_item(item)
        assert "Fault: P0123 - Engine Overtemp" in output
        assert "Severity: critical" in output
        assert "Status: ACTIVE" in output
        assert "Confirmed: True" in output
        assert "Occurrences: 5" in output
        assert "First Seen: 2025-01-01" in output


class TestFormatFaultList:
    """Tests for format_fault_list function."""

    def test_format_empty_list(self) -> None:
        """Test formatting empty fault list."""
        result = format_fault_list([])
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "No faults found" in result[0].text

    def test_format_single_fault(self) -> None:
        """Test formatting list with one fault."""
        faults = [{"code": "P0123", "faultName": "Test Fault", "severity": "warning"}]
        result = format_fault_list(faults)
        assert len(result) == 1
        assert "Found 1 fault(s)" in result[0].text
        assert "P0123" in result[0].text
        assert "Test Fault" in result[0].text

    def test_format_multiple_faults(self) -> None:
        """Test formatting list with multiple faults."""
        faults = [
            {"code": "P0123", "faultName": "Fault 1"},
            {"code": "P0456", "faultName": "Fault 2"},
            {"code": "P0789", "faultName": "Fault 3"},
        ]
        result = format_fault_list(faults)
        assert "Found 3 fault(s)" in result[0].text
        assert "P0123" in result[0].text
        assert "P0456" in result[0].text
        assert "P0789" in result[0].text

    def test_format_fallback_on_invalid_data(self) -> None:
        """Test that formatting falls back gracefully on invalid data."""
        # Missing required 'code' field - should fall back to basic formatting
        faults = [{"unknown_field": "value"}]
        result = format_fault_list(faults)
        # Should not raise, should return something
        assert len(result) == 1


class TestFormatSnapshot:
    """Tests for format_snapshot function."""

    def test_format_freeze_frame(self) -> None:
        """Test formatting freeze frame snapshot."""
        snap = FreezeFrameSnapshot(
            snapshot_id="ff-001",
            timestamp="2025-01-01T00:00:00Z",
            data_source="/temperature",
            data={"value": 85.5},
        )
        output = format_snapshot(snap)
        assert "Snapshot: ff-001" in output
        assert "Timestamp: 2025-01-01" in output
        assert "Source: /temperature" in output
        assert "Data:" in output
        assert "85.5" in output

    def test_format_rosbag_snapshot(self) -> None:
        """Test formatting rosbag snapshot."""
        snap = RosbagSnapshot(
            snapshot_id="rb-001",
            timestamp="2025-01-01T00:00:00Z",
            bulk_data_uri="/api/v1/bulk-data/rb-001.db3",
            file_size=1048576,  # 1 MB
            is_available=True,
        )
        output = format_snapshot(snap)
        assert "Snapshot: rb-001" in output
        assert "Download URI: /api/v1/bulk-data/rb-001.db3" in output
        assert "File Size: 1.00 MB" in output
        assert "Available: True" in output


class TestFormatEnvironmentData:
    """Tests for format_environment_data function."""

    def test_format_with_freeze_frames(self) -> None:
        """Test formatting environment data with freeze frames."""
        env = EnvironmentData(
            extended_data_records=ExtendedDataRecords(
                freeze_frame_snapshots=[
                    FreezeFrameSnapshot(
                        snapshot_id="ff-1",
                        timestamp="2025-01-01T00:00:00Z",
                        data={"temp": 100},
                    )
                ]
            )
        )
        output = format_environment_data(env)
        assert "Environment Data:" in output
        assert "Freeze Frame Snapshots (1):" in output
        assert "ff-1" in output

    def test_format_with_rosbags(self) -> None:
        """Test formatting environment data with rosbags."""
        env = EnvironmentData(
            extended_data_records=ExtendedDataRecords(
                rosbag_snapshots=[
                    RosbagSnapshot(
                        snapshot_id="rb-1",
                        timestamp="2025-01-01T00:00:00Z",
                        bulk_data_uri="/bulk-data/file.db3",
                    )
                ]
            )
        )
        output = format_environment_data(env)
        assert "Environment Data:" in output
        assert "Rosbag Snapshots (1):" in output
        assert "rb-1" in output
        assert "/bulk-data/file.db3" in output


class TestFormatFaultResponse:
    """Tests for format_fault_response function."""

    def test_format_response_minimal(self) -> None:
        """Test formatting fault response with minimal data."""
        response_data = {"item": {"code": "P0123"}}
        result = format_fault_response(response_data)
        assert len(result) == 1
        assert "P0123" in result[0].text

    def test_format_response_with_env_data(self) -> None:
        """Test formatting fault response with environment data."""
        response_data = {
            "item": {"code": "P0123", "faultName": "Test Fault", "severity": "critical"},
            "environmentData": {
                "extendedDataRecords": {
                    "freezeFrameSnapshots": [
                        {"snapshotId": "ff-1", "timestamp": "2025-01-01T00:00:00Z", "data": {}}
                    ],
                    "rosbagSnapshots": [
                        {
                            "snapshotId": "rb-1",
                            "timestamp": "2025-01-01T00:00:00Z",
                            "bulkDataUri": "/bulk-data/test.db3",
                        }
                    ],
                }
            },
        }
        result = format_fault_response(response_data)
        text = result[0].text
        assert "P0123" in text
        assert "Test Fault" in text
        assert "Environment Data:" in text
        assert "Freeze Frame Snapshots" in text
        assert "Rosbag Snapshots" in text
        assert "/bulk-data/test.db3" in text

    def test_format_response_snake_case_env_data(self) -> None:
        """Test formatting fault response with snake_case environment_data key."""
        response_data = {
            "item": {"code": "P0456"},
            "environment_data": {
                "extendedDataRecords": {
                    "freezeFrameSnapshots": [],
                    "rosbagSnapshots": [
                        {
                            "snapshotId": "rb-1",
                            "timestamp": "2025-01-01T00:00:00Z",
                            "bulkDataUri": "/bulk-data/test.db3",
                        }
                    ],
                }
            },
        }
        result = format_fault_response(response_data)
        assert "/bulk-data/test.db3" in result[0].text


class TestFormatSnapshotsResponse:
    """Tests for format_snapshots_response function."""

    def test_format_empty_snapshots(self) -> None:
        """Test formatting response with no snapshots."""
        response_data = {"freezeFrameSnapshots": [], "rosbagSnapshots": []}
        result = format_snapshots_response(response_data)
        assert "Diagnostic Snapshots:" in result[0].text
        assert "No snapshots available" in result[0].text

    def test_format_with_snapshots(self) -> None:
        """Test formatting response with both snapshot types."""
        response_data = {
            "freezeFrameSnapshots": [
                {"snapshotId": "ff-1", "timestamp": "2025-01-01T00:00:00Z", "data": {"val": 1}}
            ],
            "rosbagSnapshots": [
                {
                    "snapshotId": "rb-1",
                    "timestamp": "2025-01-01T00:00:00Z",
                    "bulkDataUri": "/bulk-data/test.db3",
                    "fileSize": 2097152,
                }
            ],
        }
        result = format_snapshots_response(response_data)
        text = result[0].text
        assert "Diagnostic Snapshots:" in text
        assert "Freeze Frame Snapshots (1):" in text
        assert "Rosbag Snapshots (1):" in text
        assert "ff-1" in text
        assert "rb-1" in text
        assert "/bulk-data/test.db3" in text
        assert "2.00 MB" in text
