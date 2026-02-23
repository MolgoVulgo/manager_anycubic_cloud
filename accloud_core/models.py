from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Quota:
    total_bytes: int
    used_bytes: int
    free_bytes: int
    used_percent: float


@dataclass(slots=True)
class FileItem:
    file_id: str
    name: str
    size_bytes: int
    upload_time: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    status: str | None = None
    status_code: int | None = None
    thumbnail_url: str | None = None
    download_url: str | None = None
    gcode_id: str | None = None
    layer_count: int | None = None
    print_time_s: int | None = None
    layer_thickness_mm: float | None = None
    machine_name: str | None = None
    material_name: str | None = None
    resin_usage_ml: float | None = None
    size_x_mm: float | None = None
    size_y_mm: float | None = None
    size_z_mm: float | None = None
    file_extension: str | None = None
    bottom_layers: int | None = None
    exposure_time_s: float | None = None
    off_time_s: float | None = None
    printer_names: list[str] = field(default_factory=list)
    md5: str | None = None
    region: str | None = None
    bucket: str | None = None
    object_path: str | None = None


@dataclass(slots=True)
class GcodeInfo:
    layers: int | None = None
    print_time_s: int | None = None
    resin_volume_ml: float | None = None
    extra: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class Printer:
    printer_id: str
    name: str
    online: bool
    state: str | None = None
    model: str | None = None
    printer_type: str | None = None
    description: str | None = None
    reason: str | None = None
    device_status: int | None = None
    is_printing: int | None = None
    last_update_time: str | None = None
    material_type: str | None = None
    material_used: str | None = None
    print_total_time: str | None = None
    print_count: int | None = None
    image_url: str | None = None
    machine_type: int | None = None
    key: str | None = None
    current_file_name: str | None = None
    progress_percent: int | None = None
    remain_time_min: int | None = None
    elapsed_time_min: int | None = None
    current_layer: int | None = None
    total_layers: int | None = None
    task_id: str | None = None
    print_status: int | None = None


@dataclass(slots=True)
class SessionData:
    tokens: dict[str, str] = field(default_factory=dict)

    def auth_headers(self) -> dict[str, str]:
        authorization = _resolve_authorization(self.tokens)
        if not authorization:
            return {}
        return {"Authorization": authorization}


def _resolve_authorization(tokens: dict[str, str]) -> str | None:
    explicit = str(tokens.get("Authorization", "")).strip()
    if explicit:
        return explicit if " " in explicit else f"Bearer {explicit}"

    for key in ("access_token", "id_token", "token"):
        candidate = str(tokens.get(key, "")).strip()
        if not candidate:
            continue
        return candidate if candidate.lower().startswith("bearer ") else f"Bearer {candidate}"

    return None
