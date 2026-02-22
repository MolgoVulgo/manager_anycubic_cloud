from __future__ import annotations

import re
import struct

from pwmb.types import HeaderInfo, LayerDef, MachineInfo


def parse_header_table(payload: bytes) -> HeaderInfo:
    info = HeaderInfo()
    if not payload:
        return info

    info.pixel_size_um = _read_f32(payload, 0, 0.0)
    info.layer_height_mm = _read_f32(payload, 4, 0.0)
    info.exposure_time_s = _read_f32(payload, 8, 0.0)
    info.bottom_exposure_time_s = _read_f32(payload, 12, 0.0)
    info.bottom_layers_count = _read_u32(payload, 16, 0)

    anti_aliasing = _read_u32(payload, 40, 0)
    if anti_aliasing <= 0:
        anti_aliasing = _find_u32_in_range(payload, minimum=1, maximum=32, default=1)
    info.anti_aliasing = max(1, anti_aliasing)

    resolution_x = _read_u32(payload, 44, 0)
    resolution_y = _read_u32(payload, 48, 0)
    if resolution_x <= 0 or resolution_y <= 0:
        resolution_x, resolution_y = _find_resolution_pair(payload)
    info.resolution_x = max(0, resolution_x)
    info.resolution_y = max(0, resolution_y)

    return info


def parse_machine_table(payload: bytes) -> MachineInfo:
    info = MachineInfo()
    if not payload:
        return info

    tokens = _extract_ascii_tokens(payload)
    normalized_tokens = [token.strip() for token in tokens if token.strip()]

    image_format = "unknown"
    for token in normalized_tokens:
        lower = token.lower()
        if "pw0img" in lower:
            image_format = "pw0Img"
            break
        if "pwsimg" in lower:
            image_format = "pwsImg"
            break
    info.layer_image_format = image_format

    for token in normalized_tokens:
        lower = token.lower()
        if "pw0img" in lower or "pwsimg" in lower:
            continue
        info.machine_name = token
        break

    info.max_antialiasing_level = _find_u32_in_range(payload, minimum=1, maximum=32, default=1)
    return info


def parse_layerdef_table(payload: bytes) -> list[LayerDef]:
    if len(payload) < 4:
        return []

    layer_count = _read_u32(payload, 0, 0)
    if layer_count <= 0:
        return []

    remaining = len(payload) - 4
    if remaining <= 0:
        return []

    entry_size = _resolve_layer_entry_size(layer_count=layer_count, payload_size=remaining)
    if entry_size < 8:
        return []

    max_count_from_payload = remaining // entry_size
    count = min(layer_count, max_count_from_payload)
    layers: list[LayerDef] = []
    cursor = 4

    for index in range(count):
        if cursor + 8 > len(payload):
            break
        data_address = _read_u32(payload, cursor, 0)
        data_length = _read_u32(payload, cursor + 4, 0)

        exposure_time_s = None
        if cursor + 12 <= len(payload):
            value = _read_f32(payload, cursor + 8, 0.0)
            if value > 0:
                exposure_time_s = value

        layer_height_mm = None
        if cursor + 24 <= len(payload):
            value = _read_f32(payload, cursor + 20, 0.0)
            if value > 0:
                layer_height_mm = value
        elif cursor + 16 <= len(payload):
            value = _read_f32(payload, cursor + 12, 0.0)
            if value > 0:
                layer_height_mm = value

        non_zero_pixel_count = None
        if cursor + 28 <= len(payload):
            non_zero_pixel_count = _read_u32(payload, cursor + 24, 0)
        elif cursor + 20 <= len(payload):
            non_zero_pixel_count = _read_u32(payload, cursor + 16, 0)

        layers.append(
            LayerDef(
                index=index,
                data_address=data_address,
                data_length=data_length,
                exposure_time_s=exposure_time_s,
                layer_height_mm=layer_height_mm,
                non_zero_pixel_count=non_zero_pixel_count,
            )
        )
        cursor += entry_size

    return layers


def _read_u32(payload: bytes, offset: int, default: int) -> int:
    if offset < 0 or offset + 4 > len(payload):
        return default
    return struct.unpack_from("<I", payload, offset)[0]


def _read_f32(payload: bytes, offset: int, default: float) -> float:
    if offset < 0 or offset + 4 > len(payload):
        return default
    value = struct.unpack_from("<f", payload, offset)[0]
    if not (value == value):
        return default
    return float(value)


def _extract_ascii_tokens(payload: bytes) -> list[str]:
    decoded = payload.decode("ascii", errors="ignore")
    candidates = re.split(r"[\x00\r\n\t]+", decoded)
    tokens: list[str] = []
    for candidate in candidates:
        cleaned = candidate.strip()
        if len(cleaned) < 3:
            continue
        if not any(ch.isalpha() for ch in cleaned):
            continue
        tokens.append(cleaned)
    return tokens


def _find_u32_in_range(payload: bytes, minimum: int, maximum: int, default: int) -> int:
    values: list[int] = []
    for offset in range(0, len(payload) - 3, 4):
        value = _read_u32(payload, offset, 0)
        if minimum <= value <= maximum:
            values.append(value)
    if not values:
        return default
    return max(values)


def _find_resolution_pair(payload: bytes) -> tuple[int, int]:
    best: tuple[int, int] | None = None
    best_area = 0
    for offset in range(0, len(payload) - 7, 4):
        width = _read_u32(payload, offset, 0)
        height = _read_u32(payload, offset + 4, 0)
        if width < 64 or height < 64:
            continue
        if width > 20_000 or height > 20_000:
            continue
        area = width * height
        if area <= 0 or area > 200_000_000:
            continue
        if area > best_area:
            best_area = area
            best = (width, height)
    if best is None:
        return (0, 0)
    return best


def _resolve_layer_entry_size(layer_count: int, payload_size: int) -> int:
    candidates = (32, 36, 40, 28, 24, 20, 16)
    for size in candidates:
        needed = layer_count * size
        if needed <= payload_size and payload_size - needed < size:
            return size
    if layer_count <= 0:
        return 0
    return max(8, payload_size // layer_count)
