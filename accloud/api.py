from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from accloud.client import CloudHttpClient
from accloud.endpoints import ENDPOINTS
from accloud.errors import CloudApiError
from accloud.models import FileItem, GcodeInfo, Printer, Quota
from accloud.utils import pick_first


class AnycubicCloudApi:
    """High-level API facade for cloud actions."""

    def __init__(self, client: CloudHttpClient) -> None:
        self._client = client

    def validate_session(self) -> dict[str, Any]:
        endpoint = ENDPOINTS["session_validate"]
        payload = self._client.request_json(endpoint.method, endpoint.path, expected_status=(200, 201))
        data = _extract_data(payload)
        return dict(data)

    def login_with_access_token(self, access_token: str) -> dict[str, Any]:
        endpoint = ENDPOINTS["login_with_access_token"]
        attempts = (
            {"access_token": access_token, "device_type": "web"},
            {"accessToken": access_token, "device_type": "web"},
            {"accessToken": access_token},
        )
        payload = _request_json_with_fallback(
            self._client,
            endpoint.method,
            endpoint.path,
            payload_attempts=attempts,
            expected_status=(200, 201),
        )
        return dict(_extract_data(payload))

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
        files_endpoint = ENDPOINTS["files"]
        files_alt_endpoint = ENDPOINTS["files_alt"]
        payload_attempts = (
            {"page": page, "limit": page_size},
            {"page": page, "page_size": page_size},
        )
        try:
            payload = _request_json_with_fallback(
                self._client,
                files_endpoint.method,
                files_endpoint.path,
                payload_attempts=payload_attempts,
                expected_status=(200, 201),
            )
        except CloudApiError:
            payload = _request_json_with_fallback(
                self._client,
                files_alt_endpoint.method,
                files_alt_endpoint.path,
                payload_attempts=payload_attempts,
                expected_status=(200, 201),
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
        items = self.list_files(page=1, page_size=100)
        for item in items:
            if item.file_id == file_id:
                return item
        raise CloudApiError(f"File not found in cloud listing: {file_id}")

    def get_gcode_info(self, file_id: str) -> GcodeInfo:
        endpoint = ENDPOINTS["gcode_info"]
        payload = self._client.request_json(
            endpoint.method,
            endpoint.path,
            expected_status=(200, 201),
            params={"id": file_id},
        )
        data = _extract_data(payload)
        return GcodeInfo(
            layers=_to_optional_int(pick_first(data, "layers", "layer_count", "layerCount")),
            print_time_s=_to_optional_int(pick_first(data, "print_time_s", "printTime", "print_time")),
            resin_volume_ml=_to_optional_float(pick_first(data, "resin_volume_ml", "resinVolume", "resinVolumeMl")),
            extra={k: v for k, v in data.items()},
        )

    def download_file(self, file_id: str, destination: str) -> None:
        endpoint = ENDPOINTS["download"]
        payload = _request_json_with_fallback(
            self._client,
            endpoint.method,
            endpoint.path,
            payload_attempts=(
                {"id": file_id},
                {"file_id": file_id},
                {"fileId": file_id},
                {"ids": [file_id]},
            ),
            expected_status=(200, 201),
        )
        try:
            data = _extract_data(payload)
            signed_url = _to_optional_str(
                pick_first(data, "url", "download_url", "signedUrl", "signed_url")
            )
            if not signed_url and isinstance(data, str):
                signed_url = _to_optional_str(data)
            if not signed_url:
                raise CloudApiError("Missing signed download URL in response")
            signed_response = self._client.request("GET", signed_url, expected_status=200)
            try:
                _write_bytes(Path(destination), signed_response.content)
            finally:
                signed_response.close()
        except ValueError as exc:
            raise CloudApiError(f"Invalid download payload for file_id={file_id}") from exc

    def upload_file(self, source_path: str) -> str:
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {source}")
        file_size = source.stat().st_size

        lock_endpoint = ENDPOINTS["upload_lock"]
        register_endpoint = ENDPOINTS["upload_register"]
        unlock_endpoint = ENDPOINTS["upload_unlock"]

        lock_payload = _request_json_with_fallback(
            self._client,
            lock_endpoint.method,
            lock_endpoint.path,
            payload_attempts=(
                {
                    "name": source.name,
                    "size": file_size,
                    "is_temp_file": 0,
                },
            ),
            expected_status=(200, 201),
        )
        lock_data = _extract_data(lock_payload)
        signed_url = _to_optional_str(
            pick_first(lock_data, "preSignUrl", "presignUrl", "signedUrl", "upload_url", "url")
        )
        if not signed_url:
            raise CloudApiError("Missing signed upload URL in lockStorageSpace response")

        try:
            with source.open("rb") as handle:
                upload_response = self._client.request(
                    "PUT",
                    signed_url,
                    expected_status=(200, 201),
                    content=handle.read(),
                    headers={"Content-Type": "application/octet-stream"},
                )
            upload_response.close()

            register_payload = _request_json_with_fallback(
                self._client,
                register_endpoint.method,
                register_endpoint.path,
                payload_attempts=(
                    {"user_lock_space_id": pick_first(lock_data, "id", "lock_id")},
                ),
                expected_status=(200, 201),
            )
            register_data = _extract_data(register_payload)
        finally:
            try:
                self._client.request(
                    unlock_endpoint.method,
                    unlock_endpoint.path,
                    expected_status=(200, 201),
                    json={"id": pick_first(lock_data, "id", "lock_id"), "is_delete_cos": 0},
                ).close()
            except Exception:
                # Unlock failures are non-fatal for the caller.
                pass

        file_id = _to_optional_str(pick_first(register_data, "id", "file_id", "fileId"))
        if file_id:
            return file_id
        return source.name

    def delete_file(self, file_id: str) -> None:
        endpoint = ENDPOINTS["delete"]
        _request_json_with_fallback(
            self._client,
            endpoint.method,
            endpoint.path,
            payload_attempts=(
                {"idArr": [int(file_id)] if str(file_id).isdigit() else [file_id]},
                {"idArr": [file_id]},
            ),
            expected_status=(200, 201, 202),
        )

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
    _assert_success_payload(payload)
    if "data" in payload and isinstance(payload["data"], dict):
        return _as_map(payload["data"])
    return payload


def _assert_success_payload(payload: Mapping[str, Any]) -> None:
    if "code" not in payload:
        return
    code_raw = payload.get("code")
    try:
        code = int(code_raw)
    except (TypeError, ValueError):
        code = None
    if code == 1:
        return

    message = _to_optional_str(pick_first(payload, "msg", "message", "error")) or "Cloud API returned non-success code"
    raise CloudApiError(message)


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


def _request_json_with_fallback(
    client: CloudHttpClient,
    method: str,
    path: str,
    *,
    payload_attempts: tuple[Mapping[str, Any], ...],
    expected_status: int | tuple[int, ...],
) -> dict[str, Any]:
    last_error: Exception | None = None
    for payload in payload_attempts:
        try:
            return client.request_json(
                method,
                path,
                expected_status=expected_status,
                json=dict(payload),
            )
        except CloudApiError as exc:
            last_error = exc
            continue
    if last_error is not None:
        raise last_error
    return client.request_json(method, path, expected_status=expected_status)
