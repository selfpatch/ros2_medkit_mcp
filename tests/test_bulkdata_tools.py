"""Tests for bulk-data MCP tools and models."""

import tempfile
from pathlib import Path

import httpx
import pytest
import respx

from ros2_medkit_mcp.client import SovdClient, SovdClientError
from ros2_medkit_mcp.config import Settings
from ros2_medkit_mcp.mcp_app import (
    download_rosbags_for_fault,
    format_bulkdata_categories,
    format_bulkdata_info,
    format_bulkdata_list,
    save_bulk_data_file,
)
from ros2_medkit_mcp.models import (
    BulkDataCategoriesArgs,
    BulkDataCategoryResponse,
    BulkDataDownloadArgs,
    BulkDataDownloadForFaultArgs,
    BulkDataInfoArgs,
    BulkDataItem,
    BulkDataListArgs,
    BulkDataListResponse,
)


@pytest.fixture
def settings() -> Settings:
    """Create test settings."""
    return Settings(
        base_url="http://test-sovd:8080/api/v1",
        bearer_token=None,
        timeout_seconds=5.0,
    )


@pytest.fixture
def client(settings: Settings) -> SovdClient:
    """Create test client."""
    return SovdClient(settings)


class TestBulkDataModels:
    """Tests for bulk-data Pydantic models."""

    def test_bulk_data_item(self) -> None:
        """Test BulkDataItem model."""
        data = {
            "id": "550e8400-uuid",
            "name": "MOTOR_OVERHEAT recording",
            "mimetype": "application/x-mcap",
            "size": 2097152,
            "creationDate": "2026-02-04T10:00:00Z",
        }

        item = BulkDataItem.model_validate(data)

        assert item.id == "550e8400-uuid"
        assert item.name == "MOTOR_OVERHEAT recording"
        assert item.mimetype == "application/x-mcap"
        assert item.size == 2097152
        assert item.creation_date == "2026-02-04T10:00:00Z"

    def test_bulk_data_item_minimal(self) -> None:
        """Test BulkDataItem with minimal fields."""
        data = {"id": "uuid-123"}

        item = BulkDataItem.model_validate(data)

        assert item.id == "uuid-123"
        assert item.name is None
        assert item.mimetype == "application/octet-stream"
        assert item.size is None

    def test_bulk_data_category_response(self) -> None:
        """Test BulkDataCategoryResponse model."""
        data = {"items": ["rosbags", "logs"]}

        response = BulkDataCategoryResponse.model_validate(data)

        assert "rosbags" in response.items
        assert "logs" in response.items
        assert len(response.items) == 2

    def test_bulk_data_category_response_empty(self) -> None:
        """Test BulkDataCategoryResponse with empty items."""
        data = {"items": []}

        response = BulkDataCategoryResponse.model_validate(data)

        assert response.items == []

    def test_bulk_data_list_response(self) -> None:
        """Test BulkDataListResponse model."""
        data = {
            "items": [
                {"id": "uuid-1", "name": "File 1", "mimetype": "application/x-mcap"},
                {"id": "uuid-2", "name": "File 2", "mimetype": "application/x-mcap"},
            ]
        }

        response = BulkDataListResponse.model_validate(data)

        assert len(response.items) == 2
        assert response.items[0].id == "uuid-1"
        assert response.items[1].name == "File 2"


class TestBulkDataArgModels:
    """Tests for bulk-data argument models."""

    def test_bulk_data_categories_args(self) -> None:
        """Test BulkDataCategoriesArgs model."""
        args = BulkDataCategoriesArgs(entity_id="motor_controller")

        assert args.entity_id == "motor_controller"
        assert args.entity_type == "apps"  # Default

    def test_bulk_data_list_args(self) -> None:
        """Test BulkDataListArgs model."""
        args = BulkDataListArgs(
            entity_id="motor_controller", category="rosbags", entity_type="components"
        )

        assert args.entity_id == "motor_controller"
        assert args.category == "rosbags"
        assert args.entity_type == "components"

    def test_bulk_data_info_args(self) -> None:
        """Test BulkDataInfoArgs model."""
        args = BulkDataInfoArgs(bulk_data_uri="/apps/motor/bulk-data/rosbags/uuid")

        assert args.bulk_data_uri == "/apps/motor/bulk-data/rosbags/uuid"

    def test_bulk_data_download_args(self) -> None:
        """Test BulkDataDownloadArgs model."""
        args = BulkDataDownloadArgs(
            bulk_data_uri="/apps/motor/bulk-data/rosbags/uuid", output_dir="/home/user/downloads"
        )

        assert args.bulk_data_uri == "/apps/motor/bulk-data/rosbags/uuid"
        assert args.output_dir == "/home/user/downloads"

    def test_bulk_data_download_args_default_dir(self) -> None:
        """Test BulkDataDownloadArgs default output_dir."""
        args = BulkDataDownloadArgs(bulk_data_uri="/apps/motor/bulk-data/rosbags/uuid")

        assert args.output_dir == "/tmp"

    def test_bulk_data_download_for_fault_args(self) -> None:
        """Test BulkDataDownloadForFaultArgs model."""
        args = BulkDataDownloadForFaultArgs(
            entity_id="motor_controller",
            fault_code="MOTOR_OVERHEAT",
            entity_type="apps",
            output_dir="/tmp/faults",
        )

        assert args.entity_id == "motor_controller"
        assert args.fault_code == "MOTOR_OVERHEAT"
        assert args.entity_type == "apps"
        assert args.output_dir == "/tmp/faults"


class TestFormatFunctions:
    """Tests for bulk-data formatting functions."""

    def test_format_bulkdata_categories(self) -> None:
        """Test format_bulkdata_categories function."""
        categories = ["rosbags", "logs"]
        result = format_bulkdata_categories(categories, "motor_controller")

        assert len(result) == 1
        assert "motor_controller" in result[0].text
        assert "rosbags" in result[0].text
        assert "logs" in result[0].text

    def test_format_bulkdata_categories_empty(self) -> None:
        """Test format_bulkdata_categories with empty list."""
        result = format_bulkdata_categories([], "motor_controller")

        assert len(result) == 1
        assert "No bulk-data categories" in result[0].text

    def test_format_bulkdata_list(self) -> None:
        """Test format_bulkdata_list function."""
        items = [
            {
                "id": "uuid-1",
                "name": "MOTOR_OVERHEAT recording",
                "mimetype": "application/x-mcap",
                "size": 1048576,
                "creationDate": "2026-02-04T10:00:00Z",
            },
            {
                "id": "uuid-2",
                "name": "LOW_BATTERY recording",
                "mimetype": "application/x-mcap",
                "size": 2097152,
            },
        ]
        result = format_bulkdata_list(items, "motor_controller", "rosbags")

        text = result[0].text
        assert "2 total" in text
        assert "uuid-1" in text
        assert "uuid-2" in text
        assert "MOTOR_OVERHEAT" in text
        assert "1.00 MB" in text
        assert "2.00 MB" in text
        assert "2026-02-04" in text

    def test_format_bulkdata_list_empty(self) -> None:
        """Test format_bulkdata_list with empty list."""
        result = format_bulkdata_list([], "motor_controller", "rosbags")

        assert "No rosbags available" in result[0].text

    def test_format_bulkdata_info(self) -> None:
        """Test format_bulkdata_info function."""
        info = {
            "uri": "/apps/motor/bulk-data/rosbags/uuid",
            "filename": "MOTOR_OVERHEAT.mcap",
            "content_type": "application/x-mcap",
            "content_length": "1048576",
        }
        result = format_bulkdata_info(info)

        text = result[0].text
        assert "/apps/motor/bulk-data/rosbags/uuid" in text
        assert "MOTOR_OVERHEAT.mcap" in text
        assert "application/x-mcap" in text
        assert "1.00 MB" in text

    def test_format_bulkdata_info_minimal(self) -> None:
        """Test format_bulkdata_info with minimal info."""
        info = {"uri": "/test/uri", "content_type": "application/octet-stream"}
        result = format_bulkdata_info(info)

        text = result[0].text
        assert "/test/uri" in text
        assert "application/octet-stream" in text


class TestSaveBulkDataFile:
    """Tests for save_bulk_data_file function."""

    def test_save_with_filename(self) -> None:
        """Test saving file with provided filename."""
        content = b"fake rosbag content"

        with tempfile.TemporaryDirectory() as tmpdir:
            result = save_bulk_data_file(
                content, "test_file.mcap", "/apps/motor/bulk-data/rosbags/uuid", tmpdir
            )

            assert "Downloaded successfully" in result[0].text
            assert "test_file.mcap" in result[0].text

            file_path = Path(tmpdir) / "test_file.mcap"
            assert file_path.exists()
            assert file_path.read_bytes() == content

    def test_save_without_filename(self) -> None:
        """Test saving file without provided filename (extracted from URI)."""
        content = b"fake rosbag content"

        with tempfile.TemporaryDirectory() as tmpdir:
            result = save_bulk_data_file(
                content, None, "/apps/motor/bulk-data/rosbags/my-uuid-123", tmpdir
            )

            assert "Downloaded successfully" in result[0].text
            # Should use last URI component with .mcap extension
            assert "my-uuid-123.mcap" in result[0].text

    def test_save_creates_directory(self) -> None:
        """Test that output directory is created if not exists."""
        content = b"test content"

        with tempfile.TemporaryDirectory() as tmpdir:
            nested_dir = Path(tmpdir) / "nested" / "directory"
            assert not nested_dir.exists()

            result = save_bulk_data_file(content, "test.mcap", "/test/uri", str(nested_dir))

            assert "Downloaded successfully" in result[0].text
            assert nested_dir.exists()
            assert (nested_dir / "test.mcap").exists()


class TestClientBulkDataMethods:
    """Tests for SovdClient bulk-data methods."""

    @respx.mock
    async def test_list_bulk_data_categories(self, client: SovdClient) -> None:
        """Test list_bulk_data_categories method."""
        respx.get("http://test-sovd:8080/api/v1/apps/motor/bulk-data").mock(
            return_value=httpx.Response(200, json={"items": ["rosbags", "logs"]})
        )

        result = await client.list_bulk_data_categories("motor", "apps")

        assert result == ["rosbags", "logs"]
        await client.close()

    @respx.mock
    async def test_list_bulk_data(self, client: SovdClient) -> None:
        """Test list_bulk_data method."""
        items = [
            {"id": "uuid-1", "name": "File 1"},
            {"id": "uuid-2", "name": "File 2"},
        ]
        respx.get("http://test-sovd:8080/api/v1/apps/motor/bulk-data/rosbags").mock(
            return_value=httpx.Response(200, json={"items": items})
        )

        result = await client.list_bulk_data("motor", "rosbags", "apps")

        assert len(result) == 2
        assert result[0]["id"] == "uuid-1"
        await client.close()

    @respx.mock
    async def test_get_bulk_data_info(self, client: SovdClient) -> None:
        """Test get_bulk_data_info method."""
        respx.head("http://test-sovd:8080/api/v1/apps/motor/bulk-data/rosbags/uuid").mock(
            return_value=httpx.Response(
                200,
                headers={
                    "Content-Type": "application/x-mcap",
                    "Content-Length": "1048576",
                    "Content-Disposition": 'attachment; filename="test.mcap"',
                },
            )
        )

        result = await client.get_bulk_data_info("/apps/motor/bulk-data/rosbags/uuid")

        assert result["content_type"] == "application/x-mcap"
        assert result["content_length"] == "1048576"
        assert result["filename"] == "test.mcap"
        await client.close()

    @respx.mock
    async def test_get_bulk_data_info_not_found(self, client: SovdClient) -> None:
        """Test get_bulk_data_info with 404."""
        respx.head("http://test-sovd:8080/api/v1/apps/motor/bulk-data/rosbags/uuid").mock(
            return_value=httpx.Response(404)
        )

        with pytest.raises(SovdClientError) as exc_info:
            await client.get_bulk_data_info("/apps/motor/bulk-data/rosbags/uuid")

        assert exc_info.value.status_code == 404
        await client.close()

    @respx.mock
    async def test_download_bulk_data(self, client: SovdClient) -> None:
        """Test download_bulk_data method."""
        content = b"fake rosbag content" * 100
        respx.get("http://test-sovd:8080/api/v1/apps/motor/bulk-data/rosbags/uuid").mock(
            return_value=httpx.Response(
                200,
                content=content,
                headers={"Content-Disposition": 'attachment; filename="test.mcap"'},
            )
        )

        result_content, filename = await client.download_bulk_data(
            "/apps/motor/bulk-data/rosbags/uuid"
        )

        assert result_content == content
        assert filename == "test.mcap"
        await client.close()

    @respx.mock
    async def test_download_bulk_data_no_filename(self, client: SovdClient) -> None:
        """Test download_bulk_data without Content-Disposition."""
        content = b"fake rosbag content"
        respx.get("http://test-sovd:8080/api/v1/apps/motor/bulk-data/rosbags/uuid").mock(
            return_value=httpx.Response(200, content=content)
        )

        result_content, filename = await client.download_bulk_data(
            "/apps/motor/bulk-data/rosbags/uuid"
        )

        assert result_content == content
        assert filename is None
        await client.close()


class TestDownloadRosbagsForFault:
    """Tests for download_rosbags_for_fault function."""

    @respx.mock
    async def test_download_rosbags_success(self, client: SovdClient) -> None:
        """Test downloading rosbags for a fault."""
        fault_response = {
            "item": {"code": "MOTOR_OVERHEAT", "faultName": "Motor Overheating"},
            "environmentData": {
                "extendedDataRecords": {
                    "freezeFrameSnapshots": [],
                    "rosbagSnapshots": [
                        {
                            "snapshotId": "rb-1",
                            "timestamp": "2026-02-04T10:00:00Z",
                            "bulkDataUri": "/apps/motor/bulk-data/rosbags/rb-1",
                        },
                        {
                            "snapshotId": "rb-2",
                            "timestamp": "2026-02-04T10:01:00Z",
                            "bulkDataUri": "/apps/motor/bulk-data/rosbags/rb-2",
                        },
                    ],
                }
            },
        }

        respx.get("http://test-sovd:8080/api/v1/apps/motor/faults/MOTOR_OVERHEAT").mock(
            return_value=httpx.Response(200, json=fault_response)
        )
        respx.get("http://test-sovd:8080/api/v1/apps/motor/bulk-data/rosbags/rb-1").mock(
            return_value=httpx.Response(
                200,
                content=b"rosbag1",
                headers={"Content-Disposition": 'filename="fault1.mcap"'},
            )
        )
        respx.get("http://test-sovd:8080/api/v1/apps/motor/bulk-data/rosbags/rb-2").mock(
            return_value=httpx.Response(
                200,
                content=b"rosbag2",
                headers={"Content-Disposition": 'filename="fault2.mcap"'},
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = await download_rosbags_for_fault(
                client, "motor", "MOTOR_OVERHEAT", "apps", tmpdir
            )

            text = result[0].text
            assert "MOTOR_OVERHEAT" in text
            assert "Successfully downloaded (2)" in text
            assert "fault1.mcap" in text
            assert "fault2.mcap" in text

            assert (Path(tmpdir) / "fault1.mcap").exists()
            assert (Path(tmpdir) / "fault2.mcap").exists()

        await client.close()

    @respx.mock
    async def test_download_only_freeze_frames(self, client: SovdClient) -> None:
        """Test fault with only freeze frames (no rosbags)."""
        fault_response = {
            "item": {"code": "MINOR_FAULT"},
            "environmentData": {
                "extendedDataRecords": {
                    "freezeFrameSnapshots": [
                        {"snapshotId": "ff-1", "timestamp": "2026-02-04T10:00:00Z", "data": {}}
                    ],
                    "rosbagSnapshots": [],
                }
            },
        }

        respx.get("http://test-sovd:8080/api/v1/apps/motor/faults/MINOR_FAULT").mock(
            return_value=httpx.Response(200, json=fault_response)
        )

        result = await download_rosbags_for_fault(client, "motor", "MINOR_FAULT", "apps", "/tmp")

        text = result[0].text
        assert "only freeze frame snapshots" in text
        assert "1 total" in text

        await client.close()

    @respx.mock
    async def test_download_no_environment_data(self, client: SovdClient) -> None:
        """Test fault without environment data."""
        fault_response = {"item": {"code": "NO_ENV_FAULT"}}

        respx.get("http://test-sovd:8080/api/v1/apps/motor/faults/NO_ENV_FAULT").mock(
            return_value=httpx.Response(200, json=fault_response)
        )

        result = await download_rosbags_for_fault(client, "motor", "NO_ENV_FAULT", "apps", "/tmp")

        assert "No environment data found" in result[0].text

        await client.close()

    @respx.mock
    async def test_download_with_errors(self, client: SovdClient) -> None:
        """Test downloading with some failures."""
        fault_response = {
            "item": {"code": "TEST_FAULT"},
            "environmentData": {
                "extendedDataRecords": {
                    "freezeFrameSnapshots": [],
                    "rosbagSnapshots": [
                        {
                            "snapshotId": "rb-ok",
                            "timestamp": "2026-02-04T10:00:00Z",
                            "bulkDataUri": "/apps/motor/bulk-data/rosbags/rb-ok",
                        },
                        {
                            "snapshotId": "rb-fail",
                            "timestamp": "2026-02-04T10:01:00Z",
                            "bulkDataUri": "/apps/motor/bulk-data/rosbags/rb-fail",
                        },
                    ],
                }
            },
        }

        respx.get("http://test-sovd:8080/api/v1/apps/motor/faults/TEST_FAULT").mock(
            return_value=httpx.Response(200, json=fault_response)
        )
        respx.get("http://test-sovd:8080/api/v1/apps/motor/bulk-data/rosbags/rb-ok").mock(
            return_value=httpx.Response(200, content=b"ok")
        )
        respx.get("http://test-sovd:8080/api/v1/apps/motor/bulk-data/rosbags/rb-fail").mock(
            return_value=httpx.Response(500, text="Server Error")
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = await download_rosbags_for_fault(client, "motor", "TEST_FAULT", "apps", tmpdir)

            text = result[0].text
            assert "Successfully downloaded (1)" in text
            assert "Errors (1)" in text
            assert "rb-fail" in text

        await client.close()
