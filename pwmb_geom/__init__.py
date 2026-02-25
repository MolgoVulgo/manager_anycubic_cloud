from __future__ import annotations

from collections.abc import Sequence
import logging
import os

import numpy as np

from pwmb_core.types import PwmbDocument
from render3d_core.contours import PixelLayerLoops, build_contour_stack
from render3d_core.geometry_v2 import build_geometry_v2
from render3d_core.perf import BuildMetrics
from render3d_core.types import PwmbContourGeometry, PwmbContourStack

LOGGER = logging.getLogger("render3d.backend.cpp")
GEOM_CPP_CONTOURS_IMPL_ENV = "GEOM_CPP_CONTOURS_IMPL"
GEOM_CPP_TRIANGULATION_IMPL_ENV = "GEOM_CPP_TRIANGULATION_IMPL"
_VALID_CONTOUR_IMPLS = {"native", "opencv", "auto"}
_VALID_TRIANGULATION_IMPLS = {"native", "python", "auto"}
_WARNED_KEYS: set[str] = set()

try:
    from ._pwmb_geom import extract_polygons as _native_extract_polygons
except Exception as exc:  # pragma: no cover - runtime dependency not present in CI
    raise ImportError(
        "pwmb_geom native module is unavailable. Build pwmb_geom_cpp to enable GEOM_BACKEND=cpp."
    ) from exc

try:
    from ._pwmb_geom import has_opencv_contours as _native_has_opencv_contours
except Exception:  # pragma: no cover - backward compatibility with older native modules
    _native_has_opencv_contours = None

try:
    from ._pwmb_geom import triangulate_polygon_with_holes as _native_triangulate_polygon_with_holes
except Exception:  # pragma: no cover - backward compatibility with older native modules
    _native_triangulate_polygon_with_holes = None

try:
    from ._pwmb_geom import triangulate_polygon_with_holes_indexed as _native_triangulate_polygon_with_holes_indexed
except Exception:  # pragma: no cover - backward compatibility with older native modules
    _native_triangulate_polygon_with_holes_indexed = None


def _warn_once(key: str, msg: str, *args: object) -> None:
    if key in _WARNED_KEYS:
        return
    _WARNED_KEYS.add(key)
    LOGGER.warning(msg, *args)


def _probe_impl_argument_support() -> bool:
    probe = np.zeros((1, 1), dtype=np.uint8)
    try:
        _native_extract_polygons(probe, "native")
    except TypeError:
        return False
    return True


_NATIVE_SUPPORTS_IMPL_ARG = _probe_impl_argument_support()


def has_opencv_contours() -> bool:
    if _native_has_opencv_contours is None:
        return False
    try:
        return bool(_native_has_opencv_contours())
    except Exception:
        return False


def current_contours_impl() -> str:
    raw_value = os.getenv(GEOM_CPP_CONTOURS_IMPL_ENV, "native")
    requested = str(raw_value).strip().lower() or "native"
    if requested not in _VALID_CONTOUR_IMPLS:
        _warn_once(
            "invalid_cpp_contours_impl",
            "Unknown %s=%r, fallback to native",
            GEOM_CPP_CONTOURS_IMPL_ENV,
            raw_value,
        )
        return "native"
    if requested == "auto":
        return "opencv" if has_opencv_contours() else "native"
    if requested == "opencv" and not has_opencv_contours():
        _warn_once(
            "opencv_unavailable",
            "%s=opencv requested but OpenCV contours are unavailable, fallback to native",
            GEOM_CPP_CONTOURS_IMPL_ENV,
        )
        return "native"
    return requested


def has_native_triangulation() -> bool:
    return callable(_native_triangulate_polygon_with_holes)


def has_native_indexed_triangulation() -> bool:
    return callable(_native_triangulate_polygon_with_holes_indexed)


def current_triangulation_impl() -> str:
    raw_value = os.getenv(GEOM_CPP_TRIANGULATION_IMPL_ENV, "native")
    requested = str(raw_value).strip().lower() or "native"
    if requested not in _VALID_TRIANGULATION_IMPLS:
        _warn_once(
            "invalid_cpp_triangulation_impl",
            "Unknown %s=%r, fallback to native",
            GEOM_CPP_TRIANGULATION_IMPL_ENV,
            raw_value,
        )
        requested = "native"
    if requested == "auto":
        return "native" if has_native_triangulation() else "python"
    if requested == "native" and not has_native_triangulation():
        _warn_once(
            "native_triangulation_unavailable",
            "%s=native requested but native triangulation is unavailable, fallback to python",
            GEOM_CPP_TRIANGULATION_IMPL_ENV,
        )
        return "python"
    return requested


def build_contours(
    document: PwmbDocument,
    *,
    threshold: int,
    binarization_mode: str,
    xy_stride: int,
    metrics: BuildMetrics | None = None,
    cancel_token: object | None = None,
) -> PwmbContourStack:
    return build_contour_stack(
        document=document,
        threshold=threshold,
        binarization_mode=binarization_mode,
        xy_stride=xy_stride,
        metrics=metrics,
        pixel_extractor=_extract_native_layer_loops,
        cancel_token=cancel_token,
    )


def build_geometry(
    contour_stack: PwmbContourStack,
    *,
    max_layers: int | None,
    max_vertices: int | None,
    max_xy_stride: int,
    include_fill: bool = True,
    metrics: BuildMetrics | None = None,
    cancel_token: object | None = None,
) -> PwmbContourGeometry:
    triangulation_impl = current_triangulation_impl()
    triangulator = _triangulate_native_polygon_with_holes if triangulation_impl == "native" else None
    return build_geometry_v2(
        contour_stack,
        max_layers=max_layers,
        max_vertices=max_vertices,
        max_xy_stride=max_xy_stride,
        include_fill=include_fill,
        metrics=metrics,
        triangulator=triangulator,
        cancel_token=cancel_token,
    )


def _extract_native_layer_loops(mask: np.ndarray) -> PixelLayerLoops:
    impl = current_contours_impl()
    if _NATIVE_SUPPORTS_IMPL_ARG:
        payload = _native_extract_polygons(mask, impl)
    else:
        if impl != "native":
            _warn_once(
                "impl_arg_not_supported",
                "Native module does not support impl selection; ignoring %s=%s",
                GEOM_CPP_CONTOURS_IMPL_ENV,
                impl,
            )
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


def _triangulate_native_polygon_with_holes(
    outer: list[tuple[float, float]],
    holes: list[list[tuple[float, float]]],
) -> list[tuple[tuple[float, float], tuple[float, float], tuple[float, float]]]:
    if _native_triangulate_polygon_with_holes is None:
        return []
    payload = _native_triangulate_polygon_with_holes(outer, holes)
    if not isinstance(payload, Sequence):
        return []
    triangles: list[tuple[tuple[float, float], tuple[float, float], tuple[float, float]]] = []
    for tri_raw in payload:
        if not isinstance(tri_raw, Sequence) or len(tri_raw) != 3:
            continue
        p0 = _normalize_point2d(tri_raw[0])
        p1 = _normalize_point2d(tri_raw[1])
        p2 = _normalize_point2d(tri_raw[2])
        if p0 is None or p1 is None or p2 is None:
            continue
        triangles.append((p0, p1, p2))
    return triangles


def _triangulate_native_polygon_with_holes_indexed(
    outer: list[tuple[float, float]],
    holes: list[list[tuple[float, float]]],
) -> dict[str, np.ndarray]:
    if _native_triangulate_polygon_with_holes_indexed is None:
        return {"vertices": np.zeros((0, 2), dtype=np.float32), "indices": np.zeros((0, 3), dtype=np.uint32)}
    payload = _native_triangulate_polygon_with_holes_indexed(outer, holes)
    if not isinstance(payload, dict):
        return {"vertices": np.zeros((0, 2), dtype=np.float32), "indices": np.zeros((0, 3), dtype=np.uint32)}
    vertices = payload.get("vertices")
    indices = payload.get("indices")
    try:
        vertices_arr = np.asarray(vertices, dtype=np.float32)
        indices_arr = np.asarray(indices, dtype=np.uint32)
    except Exception:
        return {"vertices": np.zeros((0, 2), dtype=np.float32), "indices": np.zeros((0, 3), dtype=np.uint32)}
    if vertices_arr.ndim != 2 or vertices_arr.shape[1] != 2:
        return {"vertices": np.zeros((0, 2), dtype=np.float32), "indices": np.zeros((0, 3), dtype=np.uint32)}
    if indices_arr.ndim != 2 or indices_arr.shape[1] != 3:
        return {"vertices": np.zeros((0, 2), dtype=np.float32), "indices": np.zeros((0, 3), dtype=np.uint32)}
    return {
        "vertices": np.ascontiguousarray(vertices_arr, dtype=np.float32),
        "indices": np.ascontiguousarray(indices_arr, dtype=np.uint32),
    }


def _normalize_point2d(raw: object) -> tuple[float, float] | None:
    if not isinstance(raw, Sequence) or len(raw) != 2:
        return None
    try:
        return (float(raw[0]), float(raw[1]))
    except (TypeError, ValueError):
        return None
