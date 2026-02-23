from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

import numpy as np

from pwmb_core import decode_layer
from pwmb_core.types import PwmbDocument
from render3d_core.types import LayerLoops, PwmbContourStack


PointI = tuple[int, int]
PointF = tuple[float, float]


def build_contour_stack(
    document: PwmbDocument,
    threshold: int,
    binarization_mode: str = "index_strict",
) -> PwmbContourStack:
    if document.width <= 0 or document.height <= 0:
        raise ValueError("PWMB document has invalid resolution")
    if binarization_mode not in {"index_strict", "threshold"}:
        raise ValueError(f"Unsupported binarization mode: {binarization_mode}")

    pitch_x_mm = _safe_pitch_xy(document.header.pixel_size_um)
    pitch_y_mm = _safe_pitch_xy(document.header.pixel_size_um)
    pitch_z_mm = _safe_pitch_z(document.header.layer_height_mm)
    stack = PwmbContourStack(
        pitch_x_mm=pitch_x_mm,
        pitch_y_mm=pitch_y_mm,
        pitch_z_mm=pitch_z_mm,
    )

    for layer in document.layers:
        try:
            decoded = decode_layer(document, layer.index, threshold=None)
        except Exception:
            # Per-layer errors should not break the whole build.
            continue
        if len(decoded) != document.pixel_count:
            continue

        mask = _build_mask(
            values=decoded,
            width=document.width,
            height=document.height,
            threshold=threshold,
            mode=binarization_mode,
        )
        if not bool(mask.any()):
            continue

        loops_px = _extract_loops(mask)
        classified = _classify_loops(loops_px)
        if not classified.outer and not classified.holes:
            continue

        world_outer = [
            _pixel_loop_to_world(
                loop,
                width=document.width,
                height=document.height,
                pitch_x_mm=pitch_x_mm,
                pitch_y_mm=pitch_y_mm,
            )
            for loop in classified.outer
        ]
        world_holes = [
            _pixel_loop_to_world(
                loop,
                width=document.width,
                height=document.height,
                pitch_x_mm=pitch_x_mm,
                pitch_y_mm=pitch_y_mm,
            )
            for loop in classified.holes
        ]
        stack.layers[layer.index] = LayerLoops(
            outer=[loop for loop in world_outer if len(loop) >= 3],
            holes=[loop for loop in world_holes if len(loop) >= 3],
        )

    return stack


def _safe_pitch_xy(pixel_size_um: float) -> float:
    if pixel_size_um > 0:
        return float(pixel_size_um) / 1000.0
    return 0.05


def _safe_pitch_z(layer_height_mm: float) -> float:
    if layer_height_mm > 0:
        return float(layer_height_mm)
    return 0.05


def _build_mask(
    *,
    values: list[int],
    width: int,
    height: int,
    threshold: int,
    mode: str,
) -> np.ndarray:
    arr = np.asarray(values, dtype=np.uint8).reshape((height, width))
    if mode == "threshold":
        limit = max(0, min(255, int(threshold)))
        return arr >= limit
    # "index_strict": best effort from decoded intensity semantics.
    return arr != 0


def _extract_loops(mask: np.ndarray) -> list[list[PointI]]:
    edges: dict[tuple[PointI, PointI], tuple[PointI, PointI]] = {}
    ys, xs = np.nonzero(mask)
    for y_raw, x_raw in zip(ys.tolist(), xs.tolist()):
        x = int(x_raw)
        y = int(y_raw)
        for edge in (
            ((x, y), (x + 1, y)),
            ((x + 1, y), (x + 1, y + 1)),
            ((x + 1, y + 1), (x, y + 1)),
            ((x, y + 1), (x, y)),
        ):
            key = _undirected_edge_key(edge[0], edge[1])
            if key in edges:
                del edges[key]
            else:
                edges[key] = edge

    outgoing: dict[PointI, list[PointI]] = defaultdict(list)
    for start, end in edges.values():
        outgoing[start].append(end)

    used: set[tuple[PointI, PointI]] = set()
    loops: list[list[PointI]] = []
    for start, targets in outgoing.items():
        for target in targets:
            edge = (start, target)
            if edge in used:
                continue
            loop = _trace_loop(edge=edge, outgoing=outgoing, used=used)
            if len(loop) < 3:
                continue
            simplified = _simplify_collinear(loop)
            if len(simplified) >= 3 and abs(_signed_area(simplified)) > 0.0:
                loops.append(simplified)
    return loops


def _trace_loop(
    *,
    edge: tuple[PointI, PointI],
    outgoing: dict[PointI, list[PointI]],
    used: set[tuple[PointI, PointI]],
) -> list[PointI]:
    start, end = edge
    points = [start]
    prev = start
    current = end
    used.add(edge)
    guard = 0
    while guard < 1_000_000:
        guard += 1
        points.append(current)
        if current == start:
            return points[:-1]

        next_candidates = [candidate for candidate in outgoing.get(current, []) if (current, candidate) not in used]
        if not next_candidates:
            return []
        next_point = _pick_next_point(prev=prev, current=current, candidates=next_candidates)
        used.add((current, next_point))
        prev, current = current, next_point
    return []


def _pick_next_point(*, prev: PointI, current: PointI, candidates: list[PointI]) -> PointI:
    if len(candidates) == 1:
        return candidates[0]

    in_dx = current[0] - prev[0]
    in_dy = current[1] - prev[1]

    def score(candidate: PointI) -> tuple[int, int, int]:
        out_dx = candidate[0] - current[0]
        out_dy = candidate[1] - current[1]
        # Prefer not to backtrack; then prefer right turn in image-space for stable loops.
        backtrack = 1 if (out_dx == -in_dx and out_dy == -in_dy) else 0
        turn = in_dx * out_dy - in_dy * out_dx
        direction_rank = _direction_rank(out_dx, out_dy)
        return (backtrack, -turn, direction_rank)

    return min(candidates, key=score)


def _direction_rank(dx: int, dy: int) -> int:
    if dx > 0 and dy == 0:
        return 0
    if dx == 0 and dy > 0:
        return 1
    if dx < 0 and dy == 0:
        return 2
    if dx == 0 and dy < 0:
        return 3
    return 4


def _simplify_collinear(loop: list[PointI]) -> list[PointI]:
    if len(loop) < 3:
        return loop

    points = list(loop)
    changed = True
    while changed and len(points) >= 3:
        changed = False
        simplified: list[PointI] = []
        size = len(points)
        for idx in range(size):
            prev = points[(idx - 1) % size]
            current = points[idx]
            nxt = points[(idx + 1) % size]
            if _is_collinear(prev, current, nxt):
                changed = True
                continue
            simplified.append(current)
        if len(simplified) < 3:
            return []
        points = simplified
    return points


def _is_collinear(a: PointI, b: PointI, c: PointI) -> bool:
    return (b[0] - a[0]) * (c[1] - b[1]) == (b[1] - a[1]) * (c[0] - b[0])


def _classify_loops(loops: Iterable[list[PointI]]) -> LayerLoops:
    loop_list = [loop for loop in loops if len(loop) >= 3 and abs(_signed_area(loop)) > 0.0]
    if not loop_list:
        return LayerLoops()

    areas = [_signed_area(loop) for loop in loop_list]
    major_idx = max(range(len(loop_list)), key=lambda idx: abs(areas[idx]))
    major_sign = 1.0 if areas[major_idx] >= 0.0 else -1.0

    outers: list[list[PointI]] = []
    holes: list[list[PointI]] = []
    for loop, area in zip(loop_list, areas):
        if (area >= 0.0 and major_sign > 0.0) or (area < 0.0 and major_sign < 0.0):
            outers.append(loop)
        else:
            holes.append(loop)
    return LayerLoops(outer=outers, holes=holes)


def _signed_area(loop: list[PointI]) -> float:
    area = 0.0
    size = len(loop)
    for idx in range(size):
        x1, y1 = loop[idx]
        x2, y2 = loop[(idx + 1) % size]
        area += float(x1 * y2 - x2 * y1)
    return 0.5 * area


def _pixel_loop_to_world(
    loop: list[PointI],
    *,
    width: int,
    height: int,
    pitch_x_mm: float,
    pitch_y_mm: float,
) -> list[PointF]:
    cx = float(width) * 0.5
    cy = float(height) * 0.5
    world: list[PointF] = []
    for x_raw, y_raw in loop:
        x = (float(x_raw) - cx) * pitch_x_mm
        y = (cy - float(y_raw)) * pitch_y_mm
        world.append((x, y))
    return world


def _undirected_edge_key(a: PointI, b: PointI) -> tuple[PointI, PointI]:
    if a <= b:
        return (a, b)
    return (b, a)
