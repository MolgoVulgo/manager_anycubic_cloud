from __future__ import annotations

from dataclasses import dataclass

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
    vertices = geometry.triangle_vertices
    total = 0.0
    for index in range(0, len(vertices), 3):
        if index + 2 >= len(vertices):
            break
        ax, ay, _az, _al = vertices[index]
        bx, by, _bz, _bl = vertices[index + 1]
        cx, cy, _cz, _cl = vertices[index + 2]
        area = abs(((bx - ax) * (cy - ay)) - ((by - ay) * (cx - ax))) * 0.5
        total += area
    return float(total)


def degenerate_triangle_count(geometry: PwmbContourGeometry, eps: float = 1e-12) -> int:
    vertices = geometry.triangle_vertices
    degenerated = 0
    for index in range(0, len(vertices), 3):
        if index + 2 >= len(vertices):
            break
        ax, ay, _az, _al = vertices[index]
        bx, by, _bz, _bl = vertices[index + 1]
        cx, cy, _cz, _cl = vertices[index + 2]
        area2 = abs(((bx - ax) * (cy - ay)) - ((by - ay) * (cx - ax)))
        if area2 <= eps:
            degenerated += 1
    return degenerated


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
    cloud: list[Point4D] = []
    cloud.extend(geometry.triangle_vertices)
    cloud.extend(geometry.line_vertices)
    cloud.extend(geometry.point_vertices)
    if not cloud:
        return None

    min_x = cloud[0][0]
    min_y = cloud[0][1]
    min_z = cloud[0][2]
    max_x = cloud[0][0]
    max_y = cloud[0][1]
    max_z = cloud[0][2]
    for x, y, z, _layer in cloud[1:]:
        min_x = min(min_x, x)
        min_y = min(min_y, y)
        min_z = min(min_z, z)
        max_x = max(max_x, x)
        max_y = max(max_y, y)
        max_z = max(max_z, z)
    return (float(min_x), float(min_y), float(min_z), float(max_x), float(max_y), float(max_z))


def _signed_area(points: list[Point2D]) -> float:
    total = 0.0
    size = len(points)
    for idx in range(size):
        x1, y1 = points[idx]
        x2, y2 = points[(idx + 1) % size]
        total += (x1 * y2) - (x2 * y1)
    return total * 0.5
