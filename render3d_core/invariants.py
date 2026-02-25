from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from render3d_core.types import Point2D, Point4D, PwmbContourGeometry, PwmbContourStack


@dataclass(slots=True)
class GeometryInvariantSnapshot:
    contour_area_mm2: float
    mesh_area_mm2: float
    contour_bbox: tuple[float, float, float, float] | None
    mesh_bbox: tuple[float, float, float, float, float, float] | None
    triangle_count: int
    degenerate_triangles: int

    def as_dict(self) -> dict[str, object]:
        return {
            "contour_area_mm2": round(self.contour_area_mm2, 6),
            "mesh_area_mm2": round(self.mesh_area_mm2, 6),
            "contour_bbox": self.contour_bbox,
            "mesh_bbox": self.mesh_bbox,
            "triangle_count": int(self.triangle_count),
            "degenerate_triangles": int(self.degenerate_triangles),
        }


def build_invariant_snapshot(
    contour_stack: PwmbContourStack,
    geometry: PwmbContourGeometry,
) -> GeometryInvariantSnapshot:
    return GeometryInvariantSnapshot(
        contour_area_mm2=contour_area_mm2(contour_stack),
        mesh_area_mm2=mesh_area_mm2(geometry),
        contour_bbox=contour_bbox(contour_stack),
        mesh_bbox=mesh_bbox(geometry),
        triangle_count=len(geometry.triangle_vertices) // 3,
        degenerate_triangles=degenerate_triangle_count(geometry),
    )


def contour_area_mm2(contour_stack: PwmbContourStack) -> float:
    total = 0.0
    for loops in contour_stack.layers.values():
        outer = sum(abs(_signed_area(loop)) for loop in loops.outer)
        holes = sum(abs(_signed_area(loop)) for loop in loops.holes)
        total += max(0.0, outer - holes)
    return float(total)


def mesh_area_mm2(geometry: PwmbContourGeometry) -> float:
    vertices = _as_vertices_array(geometry.triangle_vertices)
    if vertices.shape[0] < 3:
        return 0.0
    usable = vertices.shape[0] - (vertices.shape[0] % 3)
    if usable <= 0:
        return 0.0
    tri = vertices[:usable].reshape((-1, 3, 4))
    ax = tri[:, 0, 0]
    ay = tri[:, 0, 1]
    bx = tri[:, 1, 0]
    by = tri[:, 1, 1]
    cx = tri[:, 2, 0]
    cy = tri[:, 2, 1]
    area = np.abs(((bx - ax) * (cy - ay)) - ((by - ay) * (cx - ax))) * 0.5
    return float(np.sum(area, dtype=np.float64))


def degenerate_triangle_count(geometry: PwmbContourGeometry, eps: float = 1e-12) -> int:
    vertices = _as_vertices_array(geometry.triangle_vertices)
    if vertices.shape[0] < 3:
        return 0
    usable = vertices.shape[0] - (vertices.shape[0] % 3)
    if usable <= 0:
        return 0
    tri = vertices[:usable].reshape((-1, 3, 4))
    ax = tri[:, 0, 0]
    ay = tri[:, 0, 1]
    bx = tri[:, 1, 0]
    by = tri[:, 1, 1]
    cx = tri[:, 2, 0]
    cy = tri[:, 2, 1]
    area2 = np.abs(((bx - ax) * (cy - ay)) - ((by - ay) * (cx - ax)))
    return int(np.count_nonzero(area2 <= float(eps)))


def contour_bbox(contour_stack: PwmbContourStack) -> tuple[float, float, float, float] | None:
    min_x: float | None = None
    min_y: float | None = None
    max_x: float | None = None
    max_y: float | None = None
    for loops in contour_stack.layers.values():
        for loop in [*loops.outer, *loops.holes]:
            for x, y in loop:
                min_x = x if min_x is None else min(min_x, x)
                min_y = y if min_y is None else min(min_y, y)
                max_x = x if max_x is None else max(max_x, x)
                max_y = y if max_y is None else max(max_y, y)
    if min_x is None or min_y is None or max_x is None or max_y is None:
        return None
    return (float(min_x), float(min_y), float(max_x), float(max_y))


def mesh_bbox(geometry: PwmbContourGeometry) -> tuple[float, float, float, float, float, float] | None:
    tri = _as_vertices_array(geometry.triangle_vertices)
    line = _as_vertices_array(geometry.line_vertices)
    point = _as_vertices_array(geometry.point_vertices)
    arrays = [arr for arr in (tri, line, point) if arr.shape[0] > 0]
    if not arrays:
        return None
    cloud = arrays[0] if len(arrays) == 1 else np.concatenate(arrays, axis=0)
    mins = np.min(cloud[:, :3], axis=0)
    maxs = np.max(cloud[:, :3], axis=0)
    return (
        float(mins[0]),
        float(mins[1]),
        float(mins[2]),
        float(maxs[0]),
        float(maxs[1]),
        float(maxs[2]),
    )


def _as_vertices_array(vertices: list[Point4D] | np.ndarray) -> np.ndarray:
    if isinstance(vertices, np.ndarray):
        if vertices.size == 0:
            return np.zeros((0, 4), dtype=np.float32)
        arr = vertices
    else:
        if not vertices:
            return np.zeros((0, 4), dtype=np.float32)
        arr = np.asarray(vertices, dtype=np.float32)
    arr = np.asarray(arr, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr.reshape((-1, 4))
    elif arr.ndim != 2 or arr.shape[1] != 4:
        arr = arr.reshape((-1, 4))
    return np.ascontiguousarray(arr, dtype=np.float32)


def _signed_area(points: list[Point2D]) -> float:
    total = 0.0
    size = len(points)
    for idx in range(size):
        x1, y1 = points[idx]
        x2, y2 = points[(idx + 1) % size]
        total += (x1 * y2) - (x2 * y1)
    return total * 0.5
