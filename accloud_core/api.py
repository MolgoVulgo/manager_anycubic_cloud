from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
from typing import Any

from accloud_core.client import CloudHttpClient
from accloud_core.endpoints import ENDPOINTS
from accloud_core.errors import CloudApiError
from accloud_core.logging_contract import emit_event, get_op_id
from accloud_core.models import FileItem, GcodeInfo, Printer, Quota
from accloud_core.utils import pick_first


LOGGER = logging.getLogger("accloud.api")


class AnycubicCloudApi:
    """High-level API facade for cloud actions."""

    def __init__(self, client: CloudHttpClient) -> None:
        self._client = client

    def validate_session(self, *, op_id: str | None = None) -> dict[str, Any]:
        endpoint = ENDPOINTS["session_validate"]
        payload = _request_json(
            self._client,
            endpoint.method,
            endpoint.path,
            expected_status=(200, 201),
            endpoint_name="session.validate",
            op_id=op_id,
        )
        data = _extract_data(payload)
        return dict(data)

    def login_with_access_token(self, access_token: str, *, op_id: str | None = None) -> dict[str, Any]:
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
            endpoint_name="auth.login_with_access_token",
            op_id=op_id,
        )
        return dict(_extract_data(payload))

    def get_quota(self, *, op_id: str | None = None) -> Quota:
        endpoint = ENDPOINTS["quota"]
        payload = _request_json(
            self._client,
            endpoint.method,
            endpoint.path,
            expected_status=(200, 201),
            endpoint_name="quota.get",
            op_id=op_id,
        )
        data = _extract_data(payload)

        total = _to_bytes(pick_first(data, "total_bytes", "totalSize", "total"), default=0)
        used = _to_bytes(pick_first(data, "used_bytes", "usedSize", "used"), default=0)
        free = _to_bytes(pick_first(data, "free_bytes", "freeSize", "free"), default=max(total - used, 0))
        if total > 0 and free == 0 and used <= total:
            free = max(0, total - used)

        used_percent = _to_percent(pick_first(data, "used_percent", "usedPercent"), default=-1.0)
        if used_percent < 0.0:
            used_percent = (used / total * 100.0) if total > 0 else 0.0
        return Quota(total_bytes=total, used_bytes=used, free_bytes=free, used_percent=used_percent)

    def list_files(self, page: int = 1, page_size: int = 20, *, op_id: str | None = None) -> list[FileItem]:
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
                endpoint_name="files.list",
                op_id=op_id,
            )
        except CloudApiError:
            payload = _request_json_with_fallback(
                self._client,
                files_alt_endpoint.method,
                files_alt_endpoint.path,
                payload_attempts=payload_attempts,
                expected_status=(200, 201),
                endpoint_name="files.list_alt",
                op_id=op_id,
            )
        data = _extract_data(payload)
        raw_items = _extract_list(data)
        files: list[FileItem] = []
        for raw in raw_items:
            item_map = _as_map(raw)
            slice_param = _as_map(pick_first(item_map, "slice_param"))
            file_id = str(pick_first(item_map, "id", "file_id", "fileId", default="")).strip()
            name = str(
                pick_first(
                    item_map,
                    "old_filename",
                    "name",
                    "filename",
                    "file_name",
                    "fileName",
                    default="",
                )
            ).strip()
            if not name:
                name = _basename_from_path(_to_optional_str(pick_first(item_map, "path")) or "")
            if not name:
                name = "unnamed.pwmb"

            size_bytes = _to_bytes(
                pick_first(item_map, "size_bytes", "fileSize", "file_size", "size"),
                default=0,
            )
            raw_status = pick_first(item_map, "status", "state")
            status_text, status_code = _normalize_file_status(raw_status)

            created_at = _to_optional_timestamp_str(pick_first(item_map, "created_at", "createdAt", "createTime"))
            updated_at = _to_optional_timestamp_str(
                pick_first(item_map, "updated_at", "updatedAt", "updateTime", "modifyTime", "update_time")
            )
            upload_time = _to_optional_timestamp_str(
                pick_first(item_map, "upload_time", "uploadTime", "createTime", "createdAt", "created_at", "time")
            ) or created_at

            files.append(
                FileItem(
                    file_id=file_id or name,
                    name=name,
                    size_bytes=size_bytes,
                    upload_time=upload_time,
                    created_at=created_at,
                    updated_at=updated_at,
                    status=status_text,
                    status_code=status_code,
                    thumbnail_url=_to_optional_str(
                        pick_first(item_map, "thumbnail", "thumb", "thumbnail_url", "cover", "coverUrl", "preview")
                    ),
                    download_url=_to_optional_str(pick_first(item_map, "url", "download_url", "downloadUrl")),
                    gcode_id=_to_optional_str(pick_first(item_map, "gcode_id", "gcodeId")),
                    layer_count=_to_optional_int(
                        pick_first(
                            item_map,
                            "layers",
                            "layer_count",
                            "layerCount",
                            default=pick_first(slice_param, "layers"),
                        )
                    ),
                    print_time_s=_to_optional_int(
                        pick_first(
                            item_map,
                            "print_time_s",
                            "printTime",
                            "print_time",
                            "estimate",
                            default=pick_first(slice_param, "estimate"),
                        )
                    ),
                    layer_thickness_mm=_to_optional_float(
                        pick_first(
                            item_map,
                            "layer_height",
                            "layerHeight",
                            "thickness",
                            default=pick_first(slice_param, "zthick"),
                        )
                    ),
                    machine_name=_to_optional_str(
                        pick_first(
                            item_map,
                            "machine_name",
                            "machineName",
                            "device_name",
                            "deviceName",
                            default=pick_first(slice_param, "machine_name"),
                        )
                    ),
                    material_name=_to_optional_str(
                        pick_first(item_map, "material_name", default=pick_first(slice_param, "material_name"))
                    ),
                    resin_usage_ml=_to_optional_float(
                        pick_first(
                            item_map,
                            "supplies_usage",
                            "material",
                            default=pick_first(slice_param, "supplies_usage"),
                        )
                    ),
                    size_x_mm=_to_optional_float(pick_first(item_map, "size_x", default=pick_first(slice_param, "size_x"))),
                    size_y_mm=_to_optional_float(pick_first(item_map, "size_y", default=pick_first(slice_param, "size_y"))),
                    size_z_mm=_to_optional_float(pick_first(item_map, "size_z", default=pick_first(slice_param, "size_z"))),
                    file_extension=_to_optional_str(
                        pick_first(item_map, "file_extension", default=name.rsplit(".", 1)[-1] if "." in name else None)
                    ),
                    bottom_layers=_to_optional_int(
                        pick_first(item_map, "bottom_layers", "bott_layers", default=pick_first(slice_param, "bott_layers"))
                    ),
                    exposure_time_s=_to_optional_float(
                        pick_first(item_map, "exposure_time", default=pick_first(slice_param, "exposure_time"))
                    ),
                    off_time_s=_to_optional_float(
                        pick_first(item_map, "off_time", default=pick_first(slice_param, "off_time"))
                    ),
                    printer_names=_to_str_list(
                        pick_first(
                            item_map,
                            "printer_names",
                            default=pick_first(slice_param, "machine_name"),
                        )
                    ),
                    md5=_to_optional_str(pick_first(item_map, "md5", "origin_file_md5")),
                    region=_to_optional_str(pick_first(item_map, "region")),
                    bucket=_to_optional_str(pick_first(item_map, "bucket")),
                    object_path=_to_optional_str(pick_first(item_map, "path", "object_path")),
                )
            )
        return files

    def get_file_details(self, file_id: str, *, op_id: str | None = None) -> FileItem:
        items = self.list_files(page=1, page_size=100, op_id=op_id)
        for item in items:
            if item.file_id == file_id:
                return item
        raise CloudApiError(f"File not found in cloud listing: {file_id}")

    def get_gcode_info(self, file_id: str, *, op_id: str | None = None) -> GcodeInfo:
        endpoint = ENDPOINTS["gcode_info"]
        payload = _request_json(
            self._client,
            endpoint.method,
            endpoint.path,
            expected_status=(200, 201),
            endpoint_name="gcode.info",
            op_id=op_id,
            params={"id": file_id},
        )
        data = _extract_data(payload)
        return GcodeInfo(
            layers=_to_optional_int(pick_first(data, "layers", "layer_count", "layerCount")),
            print_time_s=_to_optional_int(pick_first(data, "print_time_s", "printTime", "print_time", "estimate")),
            resin_volume_ml=_to_optional_float(pick_first(data, "resin_volume_ml", "resinVolume", "resinVolumeMl")),
            extra={k: v for k, v in data.items()},
        )

    def download_file(self, file_id: str, destination: str, *, op_id: str | None = None) -> None:
        endpoint = ENDPOINTS["download"]
        normalized_id = str(file_id).strip()
        payload_attempts: list[Mapping[str, Any]] = []
        if normalized_id.isdigit():
            numeric_id = int(normalized_id)
            payload_attempts.append({"id": numeric_id})
            payload_attempts.append({"ids": [numeric_id]})
        payload_attempts.extend(
            [
                {"id": normalized_id},
                {"file_id": normalized_id},
                {"fileId": normalized_id},
                {"ids": [normalized_id]},
            ]
        )
        payload = _request_json_with_fallback(
            self._client,
            endpoint.method,
            endpoint.path,
            payload_attempts=tuple(payload_attempts),
            expected_status=(200, 201),
            endpoint_name="files.download_url",
            op_id=op_id,
        )
        try:
            _assert_success_payload(payload)
            raw_data: Any = payload.get("data")
            signed_url = _extract_download_signed_url(raw_data)
            if not signed_url:
                signed_url = _extract_download_signed_url(payload)
            if not signed_url:
                raise CloudApiError("Missing signed download URL in response")
            signed_response = self._client.request(
                "GET",
                signed_url,
                expected_status=200,
                include_session_headers=False,
                op_id=_resolved_op_id(op_id),
            )
            try:
                _write_bytes(Path(destination), signed_response.content)
            finally:
                signed_response.close()
        except ValueError as exc:
            raise CloudApiError(f"Invalid download payload for file_id={file_id}") from exc

    def upload_file(self, source_path: str, *, op_id: str | None = None) -> str:
        active_op_id = _resolved_op_id(op_id)
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
            endpoint_name="storage.lock",
            op_id=active_op_id,
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
                    content=handle,
                    include_session_headers=False,
                    op_id=active_op_id,
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
                endpoint_name="storage.register",
                op_id=active_op_id,
            )
            register_data = _extract_data(register_payload)
        finally:
            try:
                self._client.request(
                    unlock_endpoint.method,
                    unlock_endpoint.path,
                    expected_status=(200, 201),
                    json={"id": pick_first(lock_data, "id", "lock_id"), "is_delete_cos": 0},
                    op_id=active_op_id,
                ).close()
            except Exception:
                # Unlock failures are non-fatal for the caller.
                pass

        file_id = _to_optional_str(pick_first(register_data, "id", "file_id", "fileId"))
        if file_id:
            return file_id
        return source.name

    def delete_file(self, file_id: str, *, op_id: str | None = None) -> None:
        endpoint = ENDPOINTS["delete"]
        active_op_id = _resolved_op_id(op_id)
        normalized_file_id = str(file_id).strip()
        if not normalized_file_id:
            raise CloudApiError("Cannot delete file without file_id.")

        payload_attempts = (
            {"idArr": [int(normalized_file_id)] if normalized_file_id.isdigit() else [normalized_file_id]},
            {"idArr": [normalized_file_id]},
        )

        last_error: CloudApiError | None = None
        for payload in payload_attempts:
            try:
                response_payload = self._client.request_json(
                    endpoint.method,
                    endpoint.path,
                    expected_status=(200, 201, 202),
                    json=dict(payload),
                    op_id=active_op_id,
                )
                _log_api_call(
                    endpoint_name="files.delete",
                    payload=response_payload,
                    op_id=active_op_id,
                )
                _assert_success_payload(response_payload)
                return
            except CloudApiError as exc:
                _log_api_error(endpoint_name="files.delete", op_id=active_op_id, error=exc)
                last_error = exc
                continue

        if last_error is not None:
            raise last_error
        raise CloudApiError("Delete file failed.")

    def send_print_order(self, file_id: str, printer_id: str, *, op_id: str | None = None) -> None:
        endpoint = ENDPOINTS["print_order"]
        active_op_id = _resolved_op_id(op_id)
        normalized_file_id = str(file_id).strip()
        normalized_printer_id = str(printer_id).strip()
        if not normalized_file_id:
            raise CloudApiError("Cannot send print order without file_id.")
        if not normalized_printer_id:
            raise CloudApiError("Cannot send print order without printer_id.")

        # Legacy clients use form payload with nested JSON string in `data`.
        legacy_data_payload = {
            "file_id": normalized_file_id,
            "matrix": "",
            "filetype": 0,
            "project_type": 1,
            "template_id": -2074360784,
        }
        legacy_form = {
            "printer_id": normalized_printer_id,
            "project_id": "0",
            "order_id": "1",
            "is_delete_file": "0",
            "data": json.dumps(legacy_data_payload, separators=(",", ":"), ensure_ascii=True),
        }

        # Try the known-working legacy contract first, then fall back to simplified JSON shape.
        attempts = (
            {"data": legacy_form},
            {
                "json": {
                    "printer_id": normalized_printer_id,
                    "project_id": 0,
                    "order_id": 1,
                    "is_delete_file": 0,
                    "data": legacy_data_payload,
                }
            },
            {"json": {"file_id": normalized_file_id, "printer_id": normalized_printer_id}},
        )

        last_error: CloudApiError | None = None
        for request_kwargs in attempts:
            try:
                payload = self._client.request_json(
                    endpoint.method,
                    endpoint.path,
                    expected_status=(200, 201, 202),
                    op_id=active_op_id,
                    **request_kwargs,
                )
                _log_api_call(
                    endpoint_name="print.send_order",
                    payload=payload,
                    op_id=active_op_id,
                )
                _assert_success_payload(payload)
                return
            except CloudApiError as exc:
                _log_api_error(endpoint_name="print.send_order", op_id=active_op_id, error=exc)
                last_error = exc
                continue

        if last_error is not None:
            raise last_error
        raise CloudApiError("Print order failed.")

    def list_projects(
        self,
        *,
        printer_id: str,
        print_status: int | None = 1,
        page: int = 1,
        limit: int = 1,
        op_id: str | None = None,
    ) -> list[dict[str, Any]]:
        endpoint = ENDPOINTS["projects"]
        normalized_printer_id = str(printer_id).strip()
        if not normalized_printer_id:
            raise CloudApiError("Cannot list projects without printer_id.")

        params: dict[str, Any] = {
            "limit": max(1, int(limit)),
            "page": max(1, int(page)),
            "printer_id": int(normalized_printer_id) if normalized_printer_id.isdigit() else normalized_printer_id,
        }
        if print_status is not None:
            params["print_status"] = int(print_status)
        payload = _request_json(
            self._client,
            endpoint.method,
            endpoint.path,
            expected_status=(200, 201),
            endpoint_name="projects.list",
            op_id=op_id,
            params=params,
        )
        data = _extract_data(payload)
        raw_items = _extract_list(data)
        output: list[dict[str, Any]] = []
        for raw in raw_items:
            item_map = _as_map(raw)
            if not item_map:
                continue
            output.append(dict(item_map))
        return output

    def list_printers(self, *, op_id: str | None = None) -> list[Printer]:
        endpoint = ENDPOINTS["printers"]
        payload = _request_json(
            self._client,
            endpoint.method,
            endpoint.path,
            expected_status=(200, 201),
            endpoint_name="printers.list",
            op_id=op_id,
        )
        data = _extract_data(payload)
        raw_items = _extract_list(data)
        printers: list[Printer] = []
        for raw in raw_items:
            item_map = _as_map(raw)
            settings_map = _as_map(pick_first(item_map, "settings"))
            device_message_map = _as_map(pick_first(item_map, "device_message"))
            project_map = _as_map(pick_first(item_map, "project"))
            base_map = _as_map(pick_first(item_map, "base"))
            printer_id = str(pick_first(item_map, "id", "printer_id", "printerId", default="")).strip()
            name = str(pick_first(item_map, "name", "printer_name", "printerName", default=printer_id)).strip()
            available = _to_optional_int(pick_first(item_map, "available"))
            device_status = _to_optional_int(pick_first(item_map, "device_status"))
            status_code = _to_optional_int(pick_first(item_map, "status"))
            is_printing = _to_optional_int(pick_first(item_map, "is_printing"))
            reason = _to_optional_str(pick_first(item_map, "reason", "msg"))
            progress_percent = _to_optional_int(
                pick_first(
                    device_message_map,
                    "progress",
                    default=pick_first(
                        settings_map,
                        "progress",
                        default=pick_first(project_map, "progress", default=pick_first(item_map, "progress")),
                    ),
                )
            )
            remain_time_min = _to_optional_int(
                pick_first(
                    device_message_map,
                    "remain_time",
                    default=pick_first(
                        settings_map,
                        "remain_time",
                        default=pick_first(project_map, "remain_time", default=pick_first(item_map, "remain_time")),
                    ),
                )
            )
            elapsed_time_min = _to_optional_int(
                pick_first(
                    device_message_map,
                    "print_time",
                    default=pick_first(
                        settings_map,
                        "print_time",
                        default=pick_first(project_map, "print_time", default=pick_first(item_map, "print_time")),
                    ),
                )
            )
            current_layer = _to_optional_int(
                pick_first(
                    device_message_map,
                    "curr_layer",
                    "current_layer",
                    default=pick_first(
                        settings_map,
                        "curr_layer",
                        "current_layer",
                        default=pick_first(project_map, "curr_layer", "current_layer"),
                    ),
                )
            )
            total_layers = _to_optional_int(
                pick_first(
                    device_message_map,
                    "total_layers",
                    default=pick_first(
                        settings_map,
                        "total_layers",
                        default=pick_first(project_map, "total_layers"),
                    ),
                )
            )
            current_file_name = _to_optional_str(
                pick_first(
                    device_message_map,
                    "filename",
                    "file_name",
                    default=pick_first(
                        settings_map,
                        "filename",
                        "file_name",
                        default=pick_first(
                            project_map,
                            "name",
                            "filename",
                            "gcode_name",
                            default=pick_first(item_map, "filename", "gcode_name"),
                        ),
                    ),
                )
            )
            task_id = _to_optional_str(
                pick_first(
                    device_message_map,
                    "taskid",
                    "task_id",
                    default=pick_first(
                        settings_map,
                        "taskid",
                        "task_id",
                        default=pick_first(
                            project_map,
                            "task_id",
                            "taskid",
                            "id",
                            default=pick_first(item_map, "taskid", "id"),
                        ),
                    ),
                )
            )
            print_status = _to_optional_int(pick_first(item_map, "print_status", default=pick_first(project_map, "print_status")))
            online = _resolve_printer_online(
                available=available,
                device_status=device_status,
                status_code=status_code,
                fallback=pick_first(item_map, "online", "isOnline", "connected", default=False),
            )
            state = _resolve_printer_state(
                online=online,
                is_printing=is_printing,
                raw_state=_to_optional_str(pick_first(item_map, "state", default=pick_first(project_map, "state"))),
                reason=reason,
            )
            printers.append(
                Printer(
                    printer_id=printer_id or name,
                    name=name,
                    online=online,
                    state=state,
                    model=_to_optional_str(pick_first(item_map, "model")),
                    printer_type=_to_optional_str(pick_first(item_map, "type", "printer_type")),
                    description=_to_optional_str(pick_first(item_map, "description")),
                    reason=reason,
                    device_status=device_status,
                    is_printing=is_printing,
                    last_update_time=_to_optional_timestamp_str(
                        pick_first(item_map, "last_update_time", "lastUpdateTime", "create_time")
                    ),
                    material_type=_to_optional_str(pick_first(item_map, "material_type")),
                    material_used=_to_optional_str(pick_first(item_map, "material_used")),
                    print_total_time=_to_optional_str(pick_first(item_map, "print_totaltime", "print_total_time")),
                    print_count=_to_optional_int(
                        pick_first(item_map, "print_count", default=pick_first(base_map, "print_count"))
                    ),
                    image_url=_to_optional_str(pick_first(item_map, "img", "image")),
                    machine_type=_to_optional_int(pick_first(item_map, "machine_type")),
                    key=_to_optional_str(pick_first(item_map, "key")),
                    current_file_name=current_file_name,
                    progress_percent=progress_percent,
                    remain_time_min=remain_time_min,
                    elapsed_time_min=elapsed_time_min,
                    current_layer=current_layer,
                    total_layers=total_layers,
                    task_id=task_id,
                    print_status=print_status,
                )
            )
        return printers


def _extract_data(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    _assert_success_payload(payload)
    if "data" in payload and isinstance(payload["data"], dict):
        return _as_map(payload["data"])
    return payload


def _extract_download_signed_url(value: Any) -> str | None:
    if isinstance(value, str):
        return _to_optional_str(value)

    if isinstance(value, dict):
        mapping = _as_map(value)
        signed_url = _to_optional_str(
            pick_first(mapping, "url", "download_url", "signedUrl", "signed_url")
        )
        if signed_url:
            return signed_url
        nested = pick_first(mapping, "data", "result")
        if nested is not None and nested is not value:
            return _extract_download_signed_url(nested)
        return None

    if isinstance(value, list):
        for item in value:
            signed_url = _extract_download_signed_url(item)
            if signed_url:
                return signed_url
        return None

    return None


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
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("{") and text.endswith("}"):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                return {}
            if isinstance(parsed, dict):
                return parsed
    return {}


def _to_str_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        output: list[str] = []
        for item in value:
            text = _to_optional_str(item)
            if text:
                output.append(text)
        return output
    text = _to_optional_str(value)
    if text:
        return [text]
    return []


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


def _to_bytes(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if not text:
        return default

    # Fast path for integer-like values.
    try:
        return int(float(text))
    except ValueError:
        pass

    parsed = _parse_size_text(text)
    if parsed is None:
        return default
    return parsed


def _parse_size_text(text: str) -> int | None:
    normalized = text.strip().lower().replace("bytes", "b")
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*([kmgtp]?b)", normalized)
    if not match:
        return None

    value = float(match.group(1))
    unit = match.group(2)
    factors = {
        "b": 1,
        "kb": 1024,
        "mb": 1024 * 1024,
        "gb": 1024 * 1024 * 1024,
        "tb": 1024 * 1024 * 1024 * 1024,
        "pb": 1024 * 1024 * 1024 * 1024 * 1024,
    }
    factor = factors.get(unit)
    if factor is None:
        return None
    return int(value * factor)


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


def _to_optional_timestamp_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        ts = float(value)
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.isdigit():
            ts = float(text)
        else:
            return text

    # Handle ms epoch when needed.
    if ts > 10_000_000_000:
        ts = ts / 1000.0
    if ts <= 0:
        return None
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except (OverflowError, OSError, ValueError):
        return None


def _to_percent(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("%", "")
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def _normalize_file_status(value: Any) -> tuple[str | None, int | None]:
    if value is None:
        return None, None

    code: int | None = None
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.strip().isdigit()):
        code = _to_optional_int(value)

    if code is not None:
        if code == 1:
            return "ready", code
        if code in {2, 4, 5}:
            return "printing", code
        if code in {0, 3}:
            return "queued", code
        if code < 0:
            return "error", code
        return f"status-{code}", code

    text = str(value).strip().lower()
    if not text:
        return None, None
    if text in {"ready", "done", "success", "uploaded"}:
        return "ready", None
    if text in {"printing", "running", "queued", "pending"}:
        return "printing" if text in {"printing", "running"} else "queued", None
    if text in {"error", "failed", "offline"}:
        return "error", None
    return text, None


def _resolve_printer_online(*, available: int | None, device_status: int | None, status_code: int | None, fallback: Any) -> bool:
    if available is not None:
        return available == 1
    if device_status is not None:
        return device_status == 1
    if status_code is not None:
        return status_code == 1
    return _to_bool(fallback)


def _resolve_printer_state(
    *,
    online: bool,
    is_printing: int | None,
    raw_state: str | None,
    reason: str | None,
) -> str:
    if raw_state:
        return raw_state
    if not online:
        return reason or "offline"
    if is_printing is not None and is_printing > 0:
        return "printing"
    return "online"


def _basename_from_path(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    return text.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]


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
    endpoint_name: str,
    op_id: str | None = None,
) -> dict[str, Any]:
    active_op_id = _resolved_op_id(op_id)
    last_error: Exception | None = None
    for payload in payload_attempts:
        try:
            return _request_json(
                client,
                method,
                path,
                expected_status=expected_status,
                endpoint_name=endpoint_name,
                op_id=active_op_id,
                json=dict(payload),
            )
        except CloudApiError as exc:
            last_error = exc
            continue
    if last_error is not None:
        raise last_error
    return _request_json(
        client,
        method,
        path,
        expected_status=expected_status,
        endpoint_name=endpoint_name,
        op_id=active_op_id,
    )


def _request_json(
    client: CloudHttpClient,
    method: str,
    path: str,
    *,
    expected_status: int | tuple[int, ...],
    endpoint_name: str,
    op_id: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    active_op_id = _resolved_op_id(op_id)
    try:
        payload = client.request_json(
            method,
            path,
            expected_status=expected_status,
            op_id=active_op_id,
            **kwargs,
        )
    except CloudApiError as exc:
        _log_api_error(endpoint_name=endpoint_name, op_id=active_op_id, error=exc)
        raise

    _log_api_call(endpoint_name=endpoint_name, payload=payload, op_id=active_op_id)
    return payload


def _resolved_op_id(op_id: str | None) -> str:
    value = str(op_id).strip() if op_id else ""
    if value:
        return value
    return get_op_id()


def _log_api_call(*, endpoint_name: str, payload: Mapping[str, Any], op_id: str) -> None:
    code = _payload_code(payload)
    if code is None or code == 1:
        emit_event(
            LOGGER,
            logging.INFO,
            event="api.call_ok",
            msg="Cloud API call succeeded",
            component="accloud.api",
            op_id=op_id,
            data={"accloud": {"endpoint": endpoint_name, "code": code}},
        )
        return

    emit_event(
        LOGGER,
        logging.WARNING,
        event="api.call_fail",
        msg="Cloud API call returned non-success code",
        component="accloud.api",
        op_id=op_id,
        data={
            "accloud": {
                "endpoint": endpoint_name,
                "code": code,
                "msg_api": _to_optional_str(pick_first(payload, "msg", "message", "error")),
            }
        },
    )


def _log_api_error(*, endpoint_name: str, op_id: str, error: Exception) -> None:
    emit_event(
        LOGGER,
        logging.WARNING,
        event="api.call_fail",
        msg="Cloud API call failed",
        component="accloud.api",
        op_id=op_id,
        data={"accloud": {"endpoint": endpoint_name}},
        error={"type": type(error).__name__, "message": str(error)},
    )


def _payload_code(payload: Mapping[str, Any]) -> int | None:
    if "code" not in payload:
        return None
    raw = payload.get("code")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None
