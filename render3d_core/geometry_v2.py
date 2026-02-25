from __future__ import annotations

from collections import defaultdict
import logging
import math
from time import perf_counter
from typing import Callable

import numpy as np

from accloud_core.logging_contract import emit_event, get_op_id
from render3d_core.perf import BuildMetrics
from render3d_core.task_runner import CancelledError
from render3d_core.types import LayerRange, Point2D, PwmbContourGeometry, PwmbContourStack


Point3DLayer = tuple[float, float, float, float]
Triangle2D = tuple[Point2D, Point2D, Point2D]
TriangulationResult = list[Triangle2D] | dict[str, np.ndarray]
LOGGER_BUILD = logging.getLogger("render3d.build")


def build_geometry_v2(
    stack: PwmbContourStack,
    *,
    max_layers: int | None = None,
    max_vertices: int | None = None,
    max_xy_stride: int = 1,
    include_fill: bool = True,
    metrics: BuildMetrics | None = None,
    triangulator: Callable[[list[Point2D], list[list[Point2D]]], TriangulationResult] | None = None,
    cancel_token: object | None = None,
) -> PwmbContourGeometry:
    _raise_if_cancelled(cancel_token)
    op_id = get_op_id()
    emit_event(
        LOGGER_BUILD,
        logging.INFO,
        event="build.stage_start",
        msg="Geometry build stage started",
        component="render3d.build",
        op_id=op_id,
        data={
            "render3d": {
                "stage": "triangulate",
                "layers_visible": len(stack.layers),
                "include_fill": bool(include_fill),
            }
        },
    )
    try:
        start_ms = perf_counter()
        geometry = PwmbContourGeometry()
        if not stack.layers:
            _finalize_contiguous_buffers(geometry, metrics=metrics)
            emit_event(
                LOGGER_BUILD,
                logging.INFO,
                event="build.stage_done",
                msg="Geometry build stage completed (empty stack)",
                component="render3d.build",
                op_id=op_id,
                data={"render3d": {"stage": "triangulate", "layers_visible": 0, "tris": 0, "verts": 0}},
            )
            return geometry

        stride = max(1, int(max_xy_stride))
        layer_ids = sorted(stack.layers.keys())
        if max_layers is not None and max_layers > 0:
            layer_ids = layer_ids[: int(max_layers)]
        if not layer_ids:
            _finalize_contiguous_buffers(geometry, metrics=metrics)
            emit_event(
                LOGGER_BUILD,
                logging.INFO,
                event="build.stage_done",
                msg="Geometry build stage completed (no selected layers)",
                component="render3d.build",
                op_id=op_id,
                data={"render3d": {"stage": "triangulate", "layers_visible": 0, "tris": 0, "verts": 0}},
            )
            return geometry

        z_center = (float(layer_ids[0]) + float(layer_ids[-1])) * 0.5
        vertex_budget = max_vertices if max_vertices is not None and max_vertices > 0 else None

        stop_all = False
        for layer_id in layer_ids:
            _raise_if_cancelled(cancel_token)
            layer_loops = stack.layers.get(layer_id)
            if layer_loops is None:
                continue
            z = (float(layer_id) - z_center) * float(stack.pitch_z_mm)

            outer_loops = [_prepare_loop(loop, stride=stride) for loop in layer_loops.outer]
            hole_loops = [_prepare_loop(loop, stride=stride) for loop in layer_loops.holes]
            outer_loops = [loop for loop in outer_loops if len(loop) >= 3 and abs(_signed_area(loop)) > 1e-12]
            hole_loops = [loop for loop in hole_loops if len(loop) >= 3 and abs(_signed_area(loop)) > 1e-12]

            tri_start = len(geometry.triangle_vertices)
            tri_count = 0
            if include_fill:
                hole_map = _assign_holes_to_outers(outer_loops, hole_loops)
                for outer_index, outer in enumerate(outer_loops):
                    _raise_if_cancelled(cancel_token)
                    holes = hole_map.get(outer_index, [])
                    triangulation_result = (
                        triangulator(outer, holes)
                        if triangulator is not None
                        else _triangulate_polygon_with_holes(outer, holes)
                    )
                    for a, b, c in _iter_triangles(triangulation_result):
                        _raise_if_cancelled(cancel_token)
                        if _would_exceed_budget(geometry, vertex_budget, additional=3):
                            stop_all = True
                            break
                        tri_count += 3
                        geometry.triangle_vertices.extend(
                            [
                                _to_point4(a, z, layer_id),
                                _to_point4(b, z, layer_id),
                                _to_point4(c, z, layer_id),
                            ]
                        )
                    if stop_all:
                        break
            geometry.tri_range[layer_id] = LayerRange(start=tri_start, count=tri_count)

            line_start = len(geometry.line_vertices)
            line_count = 0
            point_start = len(geometry.point_vertices)
            point_count = 0
            for loop in [*outer_loops, *hole_loops]:
                _raise_if_cancelled(cancel_token)
                size = len(loop)
                for idx in range(size):
                    _raise_if_cancelled(cancel_token)
                    if _would_exceed_budget(geometry, vertex_budget, additional=2):
                        stop_all = True
                        break
                    p1 = loop[idx]
                    p2 = loop[(idx + 1) % size]
                    geometry.line_vertices.append(_to_point4(p1, z, layer_id))
                    geometry.line_vertices.append(_to_point4(p2, z, layer_id))
                    line_count += 2
                if stop_all:
                    break
                for point in loop:
                    _raise_if_cancelled(cancel_token)
                    if _would_exceed_budget(geometry, vertex_budget, additional=1):
                        stop_all = True
                        break
                    geometry.point_vertices.append(_to_point4(point, z, layer_id))
                    point_count += 1
                if stop_all:
                    break

            geometry.line_range[layer_id] = LayerRange(start=line_start, count=line_count)
            geometry.point_range[layer_id] = LayerRange(start=point_start, count=point_count)

            if stop_all:
                break

        triangulation_ms = (perf_counter() - start_ms) * 1000.0
        if metrics is not None:
            metrics.triangulation_ms_total += triangulation_ms
        _finalize_contiguous_buffers(geometry, metrics=metrics)
        if metrics is not None:
            metrics.triangles_total = len(geometry.triangle_vertices) // 3
            metrics.vertices_total = (
                len(geometry.triangle_vertices)
                + len(geometry.line_vertices)
                + len(geometry.point_vertices)
            )

        emit_event(
            LOGGER_BUILD,
            logging.INFO,
            event="build.stage_done",
            msg="Geometry build stage completed",
            component="render3d.build",
            op_id=op_id,
            data={
                "render3d": {
                    "stage": "triangulate",
                    "layers_visible": len(layer_ids),
                    "include_fill": bool(include_fill),
                    "tris": len(geometry.triangle_vertices) // 3,
                    "verts": len(geometry.triangle_vertices),
                }
            },
        )
        return geometry
    except CancelledError as exc:
        emit_event(
            LOGGER_BUILD,
            logging.WARNING,
            event="build.stage_cancel",
            msg="Geometry build stage cancelled",
            component="render3d.build",
            op_id=op_id,
            data={"render3d": {"stage": "triangulate"}},
            error={"type": type(exc).__name__, "message": str(exc)},
        )
        raise
    except Exception as exc:
        emit_event(
            LOGGER_BUILD,
            logging.ERROR,
            event="build.stage_fail",
            msg="Geometry build stage failed",
            component="render3d.build",
            op_id=op_id,
            data={"render3d": {"stage": "triangulate"}},
            error={"type": type(exc).__name__, "message": str(exc)},
        )
        raise


def _prepare_loop(loop: list[Point2D], *, stride: int) -> list[Point2D]:
    cleaned = _remove_duplicate_points(loop)
    if len(cleaned) < 3:
        return []
    if stride <= 1 or len(cleaned) <= 3:
        return _simplify_collinear(cleaned)

    sampled = cleaned[::stride]
    if cleaned[-1] != sampled[-1]:
        sampled.append(cleaned[-1])
    if len(sampled) < 3:
        sampled = cleaned
    return _simplify_collinear(sampled)


def _remove_duplicate_points(loop: list[Point2D]) -> list[Point2D]:
    if not loop:
        return []
    cleaned: list[Point2D] = [loop[0]]
    for point in loop[1:]:
        if point != cleaned[-1]:
            cleaned.append(point)
    if len(cleaned) > 1 and cleaned[0] == cleaned[-1]:
        cleaned.pop()
    return cleaned


def _simplify_collinear(loop: list[Point2D], eps: float = 1e-12) -> list[Point2D]:
    if len(loop) < 3:
        return loop

    points = list(loop)
    changed = True
    while changed and len(points) >= 3:
        changed = False
        reduced: list[Point2D] = []
        size = len(points)
        for idx in range(size):
            prev = points[(idx - 1) % size]
            curr = points[idx]
            nxt = points[(idx + 1) % size]
            if abs(_cross(prev, curr, nxt)) <= eps:
                changed = True
                continue
            reduced.append(curr)
        if len(reduced) < 3:
            return []
        points = reduced
    return points


def _to_point4(point: Point2D, z: float, layer_id: int) -> Point3DLayer:
    return (float(point[0]), float(point[1]), float(z), float(layer_id))


def _would_exceed_budget(
    geometry: PwmbContourGeometry,
    budget: int | None,
    *,
    additional: int,
) -> bool:
    if budget is None:
        return False
    total = len(geometry.triangle_vertices) + len(geometry.line_vertices) + len(geometry.point_vertices)
    return total + additional > budget


def _raise_if_cancelled(cancel_token: object | None) -> None:
    if cancel_token is None:
        return
    checker = getattr(cancel_token, "raise_if_cancelled", None)
    if callable(checker):
        checker()


def _iter_triangles(result: TriangulationResult) -> list[Triangle2D]:
    if isinstance(result, dict):
        return _triangles_from_indexed_payload(result)
    return result


def _triangles_from_indexed_payload(payload: dict[str, np.ndarray]) -> list[Triangle2D]:
    raw_vertices = payload.get("vertices")
    raw_indices = payload.get("indices")
    if raw_vertices is None or raw_indices is None:
        return []

    vertices = np.asarray(raw_vertices, dtype=np.float32)
    indices = np.asarray(raw_indices, dtype=np.uint32)
    if vertices.ndim != 2 or vertices.shape[1] != 2:
        return []
    if indices.ndim != 2 or indices.shape[1] != 3:
        return []
    if indices.size == 0 or vertices.size == 0:
        return []

    try:
        flat_vertices = vertices[indices.reshape(-1)]
    except Exception:
        return []

    triangles: list[Triangle2D] = []
    for idx in range(0, int(flat_vertices.shape[0]), 3):
        a = flat_vertices[idx]
        b = flat_vertices[idx + 1]
        c = flat_vertices[idx + 2]
        triangles.append(
            (
                (float(a[0]), float(a[1])),
                (float(b[0]), float(b[1])),
                (float(c[0]), float(c[1])),
            )
        )
    return triangles


def _finalize_contiguous_buffers(geometry: PwmbContourGeometry, *, metrics: BuildMetrics | None) -> None:
    start = perf_counter()
    tri = _as_contiguous_vertices(geometry.triangle_vertices)
    line = _as_contiguous_vertices(geometry.line_vertices)
    point = _as_contiguous_vertices(geometry.point_vertices)
    geometry.triangle_vertices = tri
    geometry.line_vertices = line
    geometry.point_vertices = point
    geometry.triangle_indices = _sequential_indices(int(tri.shape[0]), width=3)
    geometry.line_indices = _sequential_indices(int(line.shape[0]), width=2)
    geometry.point_indices = _sequential_indices(int(point.shape[0]), width=1)
    if metrics is not None:
        metrics.buffers_ms_total += (perf_counter() - start) * 1000.0


def _as_contiguous_vertices(vertices: list[Point3DLayer] | np.ndarray) -> np.ndarray:
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


def _sequential_indices(vertex_count: int, *, width: int) -> np.ndarray:
    count = max(0, int(vertex_count))
    if width <= 0:
        return np.zeros((0,), dtype=np.uint32)
    if width == 1:
        return np.arange(count, dtype=np.uint32)
    usable = count - (count % width)
    if usable <= 0:
        return np.zeros((0, width), dtype=np.uint32)
    return np.arange(usable, dtype=np.uint32).reshape((-1, width))


def _assign_holes_to_outers(
    outers: list[list[Point2D]],
    holes: list[list[Point2D]],
) -> dict[int, list[list[Point2D]]]:
    assigned: dict[int, list[list[Point2D]]] = defaultdict(list)
    if not outers or not holes:
        return assigned

    outer_areas = [abs(_signed_area(loop)) for loop in outers]
    for hole in holes:
        probe = _probe_point(hole)
        container_index: int | None = None
        container_area = math.inf
        for idx, outer in enumerate(outers):
            if not _point_in_polygon(probe, outer):
                continue
            area = outer_areas[idx]
            if area < container_area:
                container_index = idx
                container_area = area
        if container_index is not None:
            assigned[container_index].append(hole)
    return assigned


def _triangulate_polygon_with_holes(
    outer: list[Point2D],
    holes: list[list[Point2D]],
) -> list[tuple[Point2D, Point2D, Point2D]]:
    loops = [outer, *holes]
    if _loops_are_axis_aligned(loops):
        return _triangulate_axis_aligned_loops(loops)

    scanline = _triangulate_scanline_loops(loops)
    if scanline:
        return scanline

    polygon = _ensure_orientation(outer, ccw=True)
    for hole in holes:
        hole_cw = _ensure_orientation(hole, ccw=False)
        merged = _merge_hole_into_polygon(polygon, hole_cw)
        if merged is None:
            continue
        polygon = merged
    ear = _ear_clip(polygon)
    if ear:
        return ear
    return _triangulate_scanline_loops(loops)


def _loops_are_axis_aligned(loops: list[list[Point2D]], eps: float = 1e-12) -> bool:
    for loop in loops:
        size = len(loop)
        if size < 3:
            return False
        for idx in range(size):
            x1, y1 = loop[idx]
            x2, y2 = loop[(idx + 1) % size]
            if abs(x1 - x2) > eps and abs(y1 - y2) > eps:
                return False
    return True


def _triangulate_axis_aligned_loops(loops: list[list[Point2D]]) -> list[tuple[Point2D, Point2D, Point2D]]:
    eps = 1e-12
    y_values = sorted({point[1] for loop in loops for point in loop})
    if len(y_values) < 2:
        return []

    triangles: list[tuple[Point2D, Point2D, Point2D]] = []
    for idx in range(len(y_values) - 1):
        y0 = y_values[idx]
        y1 = y_values[idx + 1]
        if (y1 - y0) <= eps:
            continue

        y_mid = (y0 + y1) * 0.5
        x_intersections: list[float] = []
        for loop in loops:
            size = len(loop)
            for edge_idx in range(size):
                x1, y1_edge = loop[edge_idx]
                x2, y2_edge = loop[(edge_idx + 1) % size]
                if abs(y1_edge - y2_edge) <= eps:
                    continue
                y_min = min(y1_edge, y2_edge)
                y_max = max(y1_edge, y2_edge)
                if y_mid < y_min or y_mid >= y_max:
                    continue
                x = x1 + (y_mid - y1_edge) * (x2 - x1) / (y2_edge - y1_edge)
                x_intersections.append(x)

        x_intersections.sort()
        pair_count = len(x_intersections) // 2
        for pair_index in range(pair_count):
            x0 = x_intersections[pair_index * 2]
            x1 = x_intersections[pair_index * 2 + 1]
            if (x1 - x0) <= eps:
                continue
            triangles.append(((x0, y0), (x1, y0), (x1, y1)))
            triangles.append(((x0, y0), (x1, y1), (x0, y1)))
    return triangles


def _triangulate_scanline_loops(loops: list[list[Point2D]], eps: float = 1e-12) -> list[tuple[Point2D, Point2D, Point2D]]:
    y_values = sorted({point[1] for loop in loops for point in loop})
    if len(y_values) < 2:
        return []

    triangles: list[tuple[Point2D, Point2D, Point2D]] = []
    for idx in range(len(y_values) - 1):
        y0 = y_values[idx]
        y1 = y_values[idx + 1]
        if (y1 - y0) <= eps:
            continue
        y_mid = (y0 + y1) * 0.5
        crossings: list[tuple[float, tuple[Point2D, Point2D]]] = []

        for loop in loops:
            size = len(loop)
            for edge_idx in range(size):
                p1 = loop[edge_idx]
                p2 = loop[(edge_idx + 1) % size]
                if abs(p1[1] - p2[1]) <= eps:
                    continue
                edge_y_min = min(p1[1], p2[1])
                edge_y_max = max(p1[1], p2[1])
                if edge_y_max <= y0 or edge_y_min >= y1:
                    continue
                x_mid = _x_at_y(p1, p2, y_mid)
                crossings.append((x_mid, (p1, p2)))

        crossings.sort(key=lambda item: item[0])
        pair_count = len(crossings) // 2
        for pair_idx in range(pair_count):
            left_edge = crossings[pair_idx * 2][1]
            right_edge = crossings[pair_idx * 2 + 1][1]
            xl0 = _x_at_y(left_edge[0], left_edge[1], y0)
            xl1 = _x_at_y(left_edge[0], left_edge[1], y1)
            xr0 = _x_at_y(right_edge[0], right_edge[1], y0)
            xr1 = _x_at_y(right_edge[0], right_edge[1], y1)

            quad = ((xl0, y0), (xr0, y0), (xr1, y1), (xl1, y1))
            tri1 = (quad[0], quad[1], quad[2])
            tri2 = (quad[0], quad[2], quad[3])
            if abs(_cross(tri1[0], tri1[1], tri1[2])) > eps:
                triangles.append(tri1)
            if abs(_cross(tri2[0], tri2[1], tri2[2])) > eps:
                triangles.append(tri2)
    return triangles


def _x_at_y(p1: Point2D, p2: Point2D, y: float, eps: float = 1e-12) -> float:
    y1 = p1[1]
    y2 = p2[1]
    if abs(y2 - y1) <= eps:
        return min(p1[0], p2[0])
    t = (y - y1) / (y2 - y1)
    return p1[0] + t * (p2[0] - p1[0])


def _merge_hole_into_polygon(outer: list[Point2D], hole: list[Point2D]) -> list[Point2D] | None:
    if len(outer) < 3 or len(hole) < 3:
        return None

    hole_idx = max(range(len(hole)), key=lambda idx: (hole[idx][0], -hole[idx][1]))
    hole_vertex = hole[hole_idx]
    outer_idx = _find_visible_vertex_index(outer=outer, hole=hole, hole_index=hole_idx)
    if outer_idx is None:
        return None
    outer_vertex = outer[outer_idx]

    outer_rot = outer[outer_idx:] + outer[:outer_idx]
    hole_rot = hole[hole_idx:] + hole[:hole_idx]
    merged = [outer_vertex]
    merged.extend(hole_rot)
    merged.append(hole_vertex)
    merged.append(outer_vertex)
    merged.extend(outer_rot[1:])
    merged = _remove_duplicate_points(merged)
    merged = _simplify_collinear(merged)
    if len(merged) < 3 or abs(_signed_area(merged)) <= 1e-12:
        return None
    return _ensure_orientation(merged, ccw=True)


def _find_visible_vertex_index(
    *,
    outer: list[Point2D],
    hole: list[Point2D],
    hole_index: int,
) -> int | None:
    h = hole[hole_index]
    best_idx: int | None = None
    best_distance = math.inf
    outer_edges = _polygon_edges(outer)
    hole_edges = _polygon_edges(hole)

    for idx, candidate in enumerate(outer):
        if candidate == h:
            continue
        segment = (h, candidate)
        if _segment_crosses_edges(
            segment,
            outer_edges,
            allowed_touch={candidate},
        ):
            continue
        if _segment_crosses_edges(
            segment,
            hole_edges,
            allowed_touch={h, hole[(hole_index - 1) % len(hole)], hole[(hole_index + 1) % len(hole)]},
        ):
            continue
        midpoint = ((h[0] + candidate[0]) * 0.5, (h[1] + candidate[1]) * 0.5)
        if not _point_in_polygon(midpoint, outer):
            continue
        if _point_in_polygon(midpoint, hole):
            continue

        distance = _dist2(h, candidate)
        if distance < best_distance:
            best_distance = distance
            best_idx = idx

    if best_idx is not None:
        return best_idx
    # Fallback: nearest outer vertex.
    return min(range(len(outer)), key=lambda idx: _dist2(h, outer[idx]))


def _segment_crosses_edges(
    segment: tuple[Point2D, Point2D],
    edges: list[tuple[Point2D, Point2D]],
    *,
    allowed_touch: set[Point2D],
) -> bool:
    a1, a2 = segment
    for b1, b2 in edges:
        shared = {a1, a2}.intersection({b1, b2})
        if shared and shared.issubset(allowed_touch):
            continue
        if _segments_intersect(a1, a2, b1, b2):
            return True
    return False


def _ear_clip(polygon: list[Point2D]) -> list[tuple[Point2D, Point2D, Point2D]]:
    vertices = _remove_duplicate_points(polygon)
    vertices = _simplify_collinear(vertices)
    if len(vertices) < 3:
        return []
    vertices = _ensure_orientation(vertices, ccw=True)

    triangles: list[tuple[Point2D, Point2D, Point2D]] = []
    indices = list(range(len(vertices)))
    guard = 0
    max_guard = max(1_000, len(indices) * len(indices) * 4)

    while len(indices) > 3 and guard < max_guard:
        guard += 1
        ear_found = False
        for i in range(len(indices)):
            i_prev = indices[(i - 1) % len(indices)]
            i_curr = indices[i]
            i_next = indices[(i + 1) % len(indices)]
            prev_point = vertices[i_prev]
            curr_point = vertices[i_curr]
            next_point = vertices[i_next]

            if _cross(prev_point, curr_point, next_point) <= 1e-12:
                continue

            ear = (prev_point, curr_point, next_point)
            if any(
                _point_in_triangle(vertices[idx], ear)
                for idx in indices
                if idx not in {i_prev, i_curr, i_next}
            ):
                continue

            triangles.append(ear)
            del indices[i]
            ear_found = True
            break

        if not ear_found:
            break

    if len(indices) == 3:
        triangles.append((vertices[indices[0]], vertices[indices[1]], vertices[indices[2]]))
    elif len(indices) > 3:
        # Deterministic fallback in degenerate cases.
        root = indices[0]
        for i in range(1, len(indices) - 1):
            triangles.append((vertices[root], vertices[indices[i]], vertices[indices[i + 1]]))
    return [tri for tri in triangles if abs(_cross(tri[0], tri[1], tri[2])) > 1e-12]


def _point_in_triangle(point: Point2D, triangle: tuple[Point2D, Point2D, Point2D]) -> bool:
    a, b, c = triangle
    # Barycentric sign method.
    s1 = _cross(point, a, b)
    s2 = _cross(point, b, c)
    s3 = _cross(point, c, a)
    has_neg = (s1 < -1e-12) or (s2 < -1e-12) or (s3 < -1e-12)
    has_pos = (s1 > 1e-12) or (s2 > 1e-12) or (s3 > 1e-12)
    return not (has_neg and has_pos)


def _probe_point(loop: list[Point2D]) -> Point2D:
    xs = [point[0] for point in loop]
    ys = [point[1] for point in loop]
    center = ((min(xs) + max(xs)) * 0.5, (min(ys) + max(ys)) * 0.5)
    if _point_in_polygon(center, loop):
        return center
    avg = (sum(xs) / float(len(xs)), sum(ys) / float(len(ys)))
    if _point_in_polygon(avg, loop):
        return avg
    first = loop[0]
    return (first[0] + 1e-6, first[1] + 1e-6)


def _point_in_polygon(point: Point2D, polygon: list[Point2D]) -> bool:
    x, y = point
    inside = False
    size = len(polygon)
    for idx in range(size):
        x1, y1 = polygon[idx]
        x2, y2 = polygon[(idx + 1) % size]
        if _point_on_segment(point, (x1, y1), (x2, y2)):
            return True
        intersects = (y1 > y) != (y2 > y)
        if intersects:
            x_intersect = ((x2 - x1) * (y - y1) / (y2 - y1)) + x1
            if x_intersect >= x:
                inside = not inside
    return inside


def _point_on_segment(point: Point2D, a: Point2D, b: Point2D, eps: float = 1e-12) -> bool:
    px, py = point
    ax, ay = a
    bx, by = b
    cross = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
    if abs(cross) > eps:
        return False
    dot = (px - ax) * (px - bx) + (py - ay) * (py - by)
    return dot <= eps


def _polygon_edges(polygon: list[Point2D]) -> list[tuple[Point2D, Point2D]]:
    return [(polygon[idx], polygon[(idx + 1) % len(polygon)]) for idx in range(len(polygon))]


def _segments_intersect(p1: Point2D, p2: Point2D, q1: Point2D, q2: Point2D) -> bool:
    o1 = _orientation(p1, p2, q1)
    o2 = _orientation(p1, p2, q2)
    o3 = _orientation(q1, q2, p1)
    o4 = _orientation(q1, q2, p2)

    if o1 != o2 and o3 != o4:
        return True
    if o1 == 0 and _point_on_segment(q1, p1, p2):
        return True
    if o2 == 0 and _point_on_segment(q2, p1, p2):
        return True
    if o3 == 0 and _point_on_segment(p1, q1, q2):
        return True
    if o4 == 0 and _point_on_segment(p2, q1, q2):
        return True
    return False


def _orientation(a: Point2D, b: Point2D, c: Point2D, eps: float = 1e-12) -> int:
    value = (b[1] - a[1]) * (c[0] - b[0]) - (b[0] - a[0]) * (c[1] - b[1])
    if abs(value) <= eps:
        return 0
    return 1 if value > 0 else 2


def _dist2(a: Point2D, b: Point2D) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return dx * dx + dy * dy


def _ensure_orientation(loop: list[Point2D], *, ccw: bool) -> list[Point2D]:
    area = _signed_area(loop)
    if ccw and area < 0:
        return list(reversed(loop))
    if not ccw and area > 0:
        return list(reversed(loop))
    return list(loop)


def _signed_area(loop: list[Point2D]) -> float:
    area = 0.0
    size = len(loop)
    for idx in range(size):
        x1, y1 = loop[idx]
        x2, y2 = loop[(idx + 1) % size]
        area += (x1 * y2) - (x2 * y1)
    return 0.5 * area


def _cross(a: Point2D, b: Point2D, c: Point2D) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
