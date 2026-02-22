from __future__ import annotations

from collections.abc import Iterable, Sequence
import struct


def parse_layer_image_color_table(payload: bytes) -> list[int]:
    if not payload:
        return []

    # Keep parsing bounded even if the caller provided a large raw block.
    data = payload[:4096]

    # Canonical observed layout: use_full(u32), grey_count(u32), grey[grey_count], unknown(u32).
    if len(data) >= 8:
        _, grey_count = struct.unpack_from("<II", data, 0)
        if 1 <= grey_count <= 256 and 8 + grey_count <= len(data):
            return [int(item) & 0xFF for item in data[8 : 8 + grey_count]]

    # Fallback: direct table of grayscale values.
    table = list(data[:16] if len(data) >= 16 else data)
    return [int(item) & 0xFF for item in table]


def map_color_index_to_intensity(color_index: int, lut: Sequence[int] | None = None) -> int:
    if color_index == 0:
        return 0
    if lut is not None and 0 <= color_index < len(lut):
        return int(lut[color_index]) & 0xFF
    return min(255, max(0, color_index * 17))


def apply_lut(indices: Iterable[int], lut: Sequence[int] | None = None) -> list[int]:
    return [map_color_index_to_intensity(index, lut=lut) for index in indices]
