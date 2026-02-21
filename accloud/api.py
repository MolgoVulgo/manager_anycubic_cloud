from __future__ import annotations

from accloud.client import CloudHttpClient
from accloud.models import FileItem, GcodeInfo, Printer, Quota


class AnycubicCloudApi:
    """High-level API facade for cloud actions."""

    def __init__(self, client: CloudHttpClient) -> None:
        self._client = client

    def get_quota(self) -> Quota:
        raise NotImplementedError("Phase 1 skeleton: implement in phase 3")

    def list_files(self, page: int = 1, page_size: int = 20) -> list[FileItem]:
        _ = (page, page_size)
        raise NotImplementedError("Phase 1 skeleton: implement in phase 3")

    def get_file_details(self, file_id: str) -> FileItem:
        _ = file_id
        raise NotImplementedError("Phase 1 skeleton: implement in phase 3")

    def get_gcode_info(self, file_id: str) -> GcodeInfo:
        _ = file_id
        raise NotImplementedError("Phase 1 skeleton: implement in phase 3")

    def download_file(self, file_id: str, destination: str) -> None:
        _ = (file_id, destination)
        raise NotImplementedError("Phase 1 skeleton: implement in phase 3")

    def upload_file(self, source_path: str) -> str:
        _ = source_path
        raise NotImplementedError("Phase 1 skeleton: implement in phase 3")

    def delete_file(self, file_id: str) -> None:
        _ = file_id
        raise NotImplementedError("Phase 1 skeleton: implement in phase 3")

    def send_print_order(self, file_id: str, printer_id: str) -> None:
        _ = (file_id, printer_id)
        raise NotImplementedError("Phase 1 skeleton: implement in phase 3")

    def list_printers(self) -> list[Printer]:
        raise NotImplementedError("Phase 1 skeleton: implement in phase 3")

