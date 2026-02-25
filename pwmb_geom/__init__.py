from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from pwmb_core.types import PwmbDocument
from render3d_core.contours import PixelLayerLoops, build_contour_stack
from render3d_core.geometry_v2 import build_geometry_v2
from render3d_core.perf import BuildMetrics
from render3d_core.types import PwmbContourGeometry, PwmbContourStack

try:
    from ._pwmb_geom import extract_polygons as _native_extract_polygons
except Exception as exc:  # pragma: no cover - runtime dependency not present in CI
    raise ImportError(
        "pwmb_geom native module is unavailable. Build pwmb_geom_cpp to enable GEOM_BACKEND=cpp."
    ) from exc


def build_contours(
    document: PwmbDocument,
    *,
    threshold: int,
    binarization_mode: str,
    xy_stride: int,
    metrics: BuildMetrics | None = None,
) -> PwmbContourStack:
    return build_contour_stack(
        document=document,
        threshold=threshold,
        binarization_mode=binarization_mode,
        xy_stride=xy_stride,
        metrics=metrics,
        pixel_extractor=_extract_native_layer_loops,
    )


def build_geometry(
    contour_stack: PwmbContourStack,
    *,
    max_layers: int | None,
    max_vertices: int | None,
    max_xy_stride: int,
    include_fill: bool = True,
    metrics: BuildMetrics | None = None,
) -> PwmbContourGeometry:
    return build_geometry_v2(
        contour_stack,
        max_layers=max_layers,
        max_vertices=max_vertices,
        max_xy_stride=max_xy_stride,
        include_fill=include_fill,
        metrics=metrics,
    )


def _extract_native_layer_loops(mask: np.ndarray) -> PixelLayerLoops:
    payload = _native_extract_polygons(mask)
    if not isinstance(payload, dict):
        raise TypeError("pwmb_geom.extract_polygons must return a dict")
    outer = _normalize_loops(payload.get("outer", []))
    holes = _normalize_loops(payload.get("holes", []))
    return PixelLayerLoops(outer=outer, holes=holes)


def _normalize_loops(raw: object) -> list[list[tuple[int, int]]]:
    if not isinstance(raw, Sequence):
        return []
    loops: list[list[tuple[int, int]]] = []
    for loop_raw in raw:
        loop = _normalize_loop(loop_raw)
        if len(loop) >= 3:
            loops.append(loop)
    return loops


def _normalize_loop(raw: object) -> list[tuple[int, int]]:
    if not isinstance(raw, Sequence):
        return []
    points: list[tuple[int, int]] = []
    for point_raw in raw:
        if not isinstance(point_raw, Sequence) or len(point_raw) != 2:
            continue
        try:
            x = int(point_raw[0])
            y = int(point_raw[1])
        except (TypeError, ValueError):
            continue
        points.append((x, y))
    return points
