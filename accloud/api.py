from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from accloud.client import CloudHttpClient
from accloud.endpoints import ENDPOINTS, endpoint_path
from accloud.errors import CloudApiError
from accloud.models import FileItem, GcodeInfo, Printer, Quota
from accloud.utils import pick_first


class AnycubicCloudApi:
    """High-level API facade for cloud actions."""

    def __init__(self, client: CloudHttpClient) -> None:
        self._client = client

    def get_quota(self) -> Quota:
        endpoint = ENDPOINTS["quota"]
        payload = self._client.request_json(endpoint.method, endpoint.path, expected_status=(200, 201))
        data = _extract_data(payload)

        total = _to_int(pick_first(data, "total", "total_bytes", "totalSize"), default=0)
        used = _to_int(pick_first(data, "used", "used_bytes", "usedSize"), default=0)
        free = _to_int(pick_first(data, "free", "free_bytes", "freeSize"), default=max(total - used, 0))
        used_percent = _to_float(
            pick_first(data, "used_percent", "usedPercent", default=(used / total * 100.0 if total > 0 else 0.0)),
            default=0.0,
        )
        return Quota(total_bytes=total, used_bytes=used, free_bytes=free, used_percent=used_percent)

    def list_files(self, page: int = 1, page_size: int = 20) -> list[FileItem]:
        endpoint = ENDPOINTS["files"]
        payload = self._client.request_json(
            endpoint.method,
            endpoint.path,
            expected_status=(200, 201),
            params={"page": page, "page_size": page_size},
        )
        data = _extract_data(payload)
        raw_items = _extract_list(data)
        files: list[FileItem] = []
        for raw in raw_items:
            item_map = _as_map(raw)
            file_id = str(pick_first(item_map, "id", "file_id", "fileId", default="")).strip()
            name = str(pick_first(item_map, "name", "file_name", "fileName", default="unnamed.pwmb")).strip()
            size_bytes = _to_int(
                pick_first(item_map, "size", "size_bytes", "fileSize", "file_size", default=0),
                default=0,
            )
            status = pick_first(item_map, "status", "state")
            files.append(
                FileItem(
                    file_id=file_id or name,
                    name=name,
                    size_bytes=size_bytes,
                    created_at=_to_optional_str(pick_first(item_map, "created_at", "createdAt", "createTime")),
                    updated_at=_to_optional_str(pick_first(item_map, "updated_at", "updatedAt", "updateTime")),
                    status=_to_optional_str(status),
                )
            )
        return files

    def get_file_details(self, file_id: str) -> FileItem:
        endpoint = ENDPOINTS["file_details"]
        path = endpoint_path("file_details", file_id=file_id)
        payload = self._client.request_json(endpoint.method, path, expected_status=(200, 201))
        data = _extract_data(payload)
        return FileItem(
            file_id=str(pick_first(data, "id", "file_id", "fileId", default=file_id)),
            name=str(pick_first(data, "name", "file_name", "fileName", default=file_id)),
            size_bytes=_to_int(pick_first(data, "size", "size_bytes", "fileSize", default=0), default=0),
            created_at=_to_optional_str(pick_first(data, "created_at", "createdAt", "createTime")),
            updated_at=_to_optional_str(pick_first(data, "updated_at", "updatedAt", "updateTime")),
            status=_to_optional_str(pick_first(data, "status", "state")),
        )

    def get_gcode_info(self, file_id: str) -> GcodeInfo:
        endpoint = ENDPOINTS["gcode_info"]
        path = endpoint_path("gcode_info", file_id=file_id)
        payload = self._client.request_json(endpoint.method, path, expected_status=(200, 201))
        data = _extract_data(payload)
        return GcodeInfo(
            layers=_to_optional_int(pick_first(data, "layers", "layer_count", "layerCount")),
            print_time_s=_to_optional_int(pick_first(data, "print_time_s", "printTime", "print_time")),
            resin_volume_ml=_to_optional_float(pick_first(data, "resin_volume_ml", "resinVolume", "resinVolumeMl")),
            extra={k: v for k, v in data.items()},
        )

    def download_file(self, file_id: str, destination: str) -> None:
        endpoint = ENDPOINTS["download"]
        path = endpoint_path("download", file_id=file_id)
        response = self._client.request(endpoint.method, path, expected_status=(200, 201))
        try:
            content_type = response.headers.get("Content-Type", "").lower()
            if "application/json" in content_type:
                payload = response.json()
                data = _extract_data(payload)
                signed_url = _to_optional_str(
                    pick_first(data, "url", "download_url", "signedUrl", "signed_url")
                )
                if not signed_url:
                    raise CloudApiError("Missing signed download URL in response")
                signed_response = self._client.request("GET", signed_url, expected_status=200)
                try:
                    _write_bytes(Path(destination), signed_response.content)
                finally:
                    signed_response.close()
            else:
                _write_bytes(Path(destination), response.content)
        finally:
            response.close()

    def upload_file(self, source_path: str) -> str:
        endpoint = ENDPOINTS["upload"]
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {source}")
        with source.open("rb") as handle:
            response = self._client.request(
                endpoint.method,
                endpoint.path,
                expected_status=(200, 201),
                files={"file": (source.name, handle, "application/octet-stream")},
            )
        try:
            payload = response.json()
        except ValueError:
            return source.name
        data = _extract_data(payload)
        file_id = _to_optional_str(pick_first(data, "id", "file_id", "fileId"))
        return file_id or source.name

    def delete_file(self, file_id: str) -> None:
        endpoint = ENDPOINTS["delete"]
        path = endpoint_path("delete", file_id=file_id)
        response = self._client.request(endpoint.method, path, expected_status=(200, 202, 204))
        response.close()

    def send_print_order(self, file_id: str, printer_id: str) -> None:
        endpoint = ENDPOINTS["print_order"]
        payload = {"file_id": file_id, "printer_id": printer_id}
        response = self._client.request(
            endpoint.method,
            endpoint.path,
            expected_status=(200, 201, 202),
            json=payload,
        )
        response.close()

    def list_printers(self) -> list[Printer]:
        endpoint = ENDPOINTS["printers"]
        payload = self._client.request_json(endpoint.method, endpoint.path, expected_status=(200, 201))
        data = _extract_data(payload)
        raw_items = _extract_list(data)
        printers: list[Printer] = []
        for raw in raw_items:
            item_map = _as_map(raw)
            printer_id = str(pick_first(item_map, "id", "printer_id", "printerId", default="")).strip()
            name = str(pick_first(item_map, "name", "printer_name", "printerName", default=printer_id)).strip()
            online_raw = pick_first(item_map, "online", "isOnline", "connected", default=False)
            state = _to_optional_str(pick_first(item_map, "state", "status"))
            printers.append(
                Printer(
                    printer_id=printer_id or name,
                    name=name,
                    online=_to_bool(online_raw),
                    state=state,
                )
            )
        return printers


def _extract_data(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    if "data" in payload and isinstance(payload["data"], dict):
        return _as_map(payload["data"])
    return payload


def _extract_list(data: Mapping[str, Any]) -> list[Any]:
    for key in ("items", "files", "printers", "list", "results", "rows"):
        value = data.get(key)
        if isinstance(value, list):
            return value
    if isinstance(data.get("data"), list):
        return list(data["data"])
    return []


def _as_map(value: Any) -> Mapping[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "online", "connected"}
    return False


def _write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
