from __future__ import annotations

from collections.abc import Iterable, Sequence


def map_color_index_to_intensity(color_index: int, lut: Sequence[int] | None = None) -> int:
    if color_index == 0:
        return 0
    if lut is not None and 0 <= color_index < len(lut):
        return int(lut[color_index]) & 0xFF
    return min(255, max(0, color_index * 17))


def apply_lut(indices: Iterable[int], lut: Sequence[int] | None = None) -> list[int]:
    return [map_color_index_to_intensity(index, lut=lut) for index in indices]

