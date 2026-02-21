from __future__ import annotations

from dataclasses import dataclass

from pwmb3d.types import PwmbContourGeometry, PwmbContourStack


@dataclass(frozen=True, slots=True)
class CacheKey:
    file_signature: str
    pwmb_version: int
    decoder_kind: str
    pws_convention: str | None
    lut_signature: str
    threshold: int
    bin_mode: str
    xy_stride: int
    z_stride: int
    simplify_epsilon: float
    max_layers: int
    max_vertices: int
    render_mode: str


class BuildCache:
    def __init__(self) -> None:
        self._contours: dict[CacheKey, PwmbContourStack] = {}
        self._geometry: dict[CacheKey, PwmbContourGeometry] = {}

    def get_contours(self, key: CacheKey) -> PwmbContourStack | None:
        return self._contours.get(key)

    def set_contours(self, key: CacheKey, value: PwmbContourStack) -> None:
        self._contours[key] = value

    def get_geometry(self, key: CacheKey) -> PwmbContourGeometry | None:
        return self._geometry.get(key)

    def set_geometry(self, key: CacheKey, value: PwmbContourGeometry) -> None:
        self._geometry[key] = value

    def clear(self) -> None:
        self._contours.clear()
        self._geometry.clear()

