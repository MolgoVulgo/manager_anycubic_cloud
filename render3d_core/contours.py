from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import logging
from time import perf_counter
from typing import Callable

import numpy as np

from accloud_core.logging_contract import emit_event, get_op_id
from pwmb_core import decode_layer
from pwmb_core.types import PwmbDocument
from render3d_core.perf import BuildMetrics
from render3d_core.types import LayerLoops, PwmbContourStack


PointI = tuple[int, int]
PointF = tuple[float, float]
LOGGER_CONTOURS = logging.getLogger("pwmb.contours")
LOGGER_BUILD = logging.getLogger("render3d.build")
_MAX_DECODE_FAILURES = 96
_MIN_LAYERS_FOR_FAILFAST = 24
_MAX_DECODE_FAILURE_RATIO = 0.70
_DECODE_FAILURE_SAMPLE_LIMIT = 8


@dataclass(slots=True)
class PixelLayerLoops:
    outer: list[list[PointI]]
    holes: list[list[PointI]]


def build_contour_stack(
    document: PwmbDocument,
    threshold: int,
    binarization_mode: str = "index_strict",
    *,
    xy_stride: int = 1,
    metrics: BuildMetrics | None = None,
    pixel_extractor: Callable[[np.ndarray], PixelLayerLoops] | None = None,
) -> PwmbContourStack:
    op_id = get_op_id()
    emit_event(
        LOGGER_BUILD,
        logging.INFO,
        event="build.stage_start",
        msg="Contour extraction stage started",
        component="render3d.build",
        op_id=op_id,
        data={"render3d": {"stage": "mask", "layers_total": len(document.layers)}},
    )
    try:
        if document.width <= 0 or document.height <= 0:
            raise ValueError("PWMB document has invalid resolution")
        if binarization_mode not in {"index_strict", "threshold"}:
            raise ValueError(f"Unsupported binarization mode: {binarization_mode}")
        xy_step = max(1, int(xy_stride))

        pitch_x_mm = _safe_pitch_xy(document.header.pixel_size_um) * float(xy_step)
        pitch_y_mm = _safe_pitch_xy(document.header.pixel_size_um) * float(xy_step)
        pitch_z_mm = _safe_pitch_z(document.header.layer_height_mm)
        mask_width = max(1, (document.width + (xy_step - 1)) // xy_step)
        mask_height = max(1, (document.height + (xy_step - 1)) // xy_step)
        stack = PwmbContourStack(
            pitch_x_mm=pitch_x_mm,
            pitch_y_mm=pitch_y_mm,
            pitch_z_mm=pitch_z_mm,
        )
        if metrics is not None:
            metrics.layers_total = len(document.layers)

        total_outer = 0
        total_holes = 0
        decoded_bytes = 0
        layers_processed = 0
        decode_failures = 0
        decode_failure_samples: list[dict[str, object]] = []
        fail_fast = False
        active_pixel_extractor = pixel_extractor or _extract_layer_loops
        for layer_position, layer in enumerate(document.layers):
            layers_processed += 1
            decode_start = perf_counter()
            try:
                decoded = decode_layer(
                    document,
                    layer_position,
                    threshold=None,
                    strict=False,
                    as_array=True,
                )
            except Exception as exc:
                if metrics is not None:
                    metrics.decode_ms_total += (perf_counter() - decode_start) * 1000.0
                    metrics.layers_skipped += 1
                decode_failures += 1
                if len(decode_failure_samples) < _DECODE_FAILURE_SAMPLE_LIMIT:
                    decode_failure_samples.append(
                        {
                            "layer_index": int(layer.index),
                            "error_type": type(exc).__name__,
                            "error_message": str(exc),
                        }
                    )
                if _should_abort_decode_failures(
                    layers_processed=layers_processed,
                    decode_failures=decode_failures,
                ):
                    fail_fast = True
                    break
                continue
            decode_ms = (perf_counter() - decode_start) * 1000.0
            if metrics is not None:
                metrics.decode_ms_total += decode_ms
                decoded_bytes += max(0, int(layer.data_length))
            decoded_arr = decoded if isinstance(decoded, np.ndarray) else np.asarray(decoded, dtype=np.uint8)
            if int(decoded_arr.size) != document.pixel_count:
                if metrics is not None:
                    metrics.layers_skipped += 1
                continue

            contour_start = perf_counter()
            mask = _build_mask(
                values=decoded_arr,
                width=document.width,
                height=document.height,
                threshold=threshold,
                mode=binarization_mode,
                xy_stride=xy_step,
            )
            if not bool(mask.any()):
                if metrics is not None:
                    metrics.contours_ms_total += (perf_counter() - contour_start) * 1000.0
                    metrics.layers_skipped += 1
                continue

            pixel_loops = active_pixel_extractor(mask)
            if not pixel_loops.outer and not pixel_loops.holes:
                if metrics is not None:
                    metrics.contours_ms_total += (perf_counter() - contour_start) * 1000.0
                    metrics.layers_skipped += 1
                continue

            world_outer = [
                _pixel_loop_to_world(
                    loop,
                    width=mask_width,
                    height=mask_height,
                    pitch_x_mm=pitch_x_mm,
                    pitch_y_mm=pitch_y_mm,
                )
                for loop in pixel_loops.outer
            ]
            world_holes = [
                _pixel_loop_to_world(
                    loop,
                    width=mask_width,
                    height=mask_height,
                    pitch_x_mm=pitch_x_mm,
                    pitch_y_mm=pitch_y_mm,
                )
                for loop in pixel_loops.holes
            ]
            layer_loops = LayerLoops(
                outer=[loop for loop in world_outer if len(loop) >= 3],
                holes=[loop for loop in world_holes if len(loop) >= 3],
            )
            if not layer_loops.outer and not layer_loops.holes:
                if metrics is not None:
                    metrics.contours_ms_total += (perf_counter() - contour_start) * 1000.0
                    metrics.layers_skipped += 1
                continue
            stack.layers[layer.index] = layer_loops
            total_outer += len(layer_loops.outer)
            total_holes += len(layer_loops.holes)
            if metrics is not None:
                metrics.contours_ms_total += (perf_counter() - contour_start) * 1000.0
                metrics.layers_built += 1
                metrics.loops_total += len(layer_loops.outer) + len(layer_loops.holes)

        if metrics is not None and metrics.decode_ms_total > 0.0:
            metrics.decode_mb_s = (
                (float(decoded_bytes) / (1024.0 * 1024.0))
                / (metrics.decode_ms_total / 1000.0)
            )

        if decode_failures > 0:
            emit_event(
                LOGGER_CONTOURS,
                logging.WARNING,
                event="pwmb.contours_decode_fail_summary",
                msg=(
                    "Contour extraction stopped early after repeated decode failures"
                    if fail_fast
                    else "Contour extraction completed with decode failures"
                ),
                component="pwmb.contours",
                op_id=op_id,
                data={
                    "pwmb": {"W": document.width, "H": document.height},
                    "render3d": {
                        "layers_processed": layers_processed,
                        "layers_decode_failed": decode_failures,
                        "fail_fast": fail_fast,
                        "xy_stride": xy_step,
                        "failure_samples": decode_failure_samples,
                    },
                },
            )

        emit_event(
            LOGGER_CONTOURS,
            logging.INFO,
            event="pwmb.contours_ok",
            msg="Contour extraction completed",
            component="pwmb.contours",
            op_id=op_id,
            data={
                "pwmb": {"W": document.width, "H": document.height},
                "render3d": {
                    "stage": "loops",
                    "layers_visible": len(stack.layers),
                    "outer_loops": total_outer,
                    "hole_loops": total_holes,
                    "xy_stride": xy_step,
                    "fail_fast": fail_fast,
                },
            },
        )
        emit_event(
            LOGGER_BUILD,
            logging.INFO,
            event="build.stage_done",
            msg="Contour extraction stage completed",
            component="render3d.build",
            op_id=op_id,
            data={
                "render3d": {
                    "stage": "loops",
                    "layers_visible": len(stack.layers),
                    "xy_stride": xy_step,
                    "fail_fast": fail_fast,
                }
            },
        )
        return stack
    except Exception as exc:
        emit_event(
            LOGGER_BUILD,
            logging.ERROR,
            event="build.stage_fail",
            msg="Contour extraction stage failed",
            component="render3d.build",
            op_id=op_id,
            data={"render3d": {"stage": "mask"}},
            error={"type": type(exc).__name__, "message": str(exc)},
        )
        raise


def _extract_layer_loops(mask: np.ndarray) -> PixelLayerLoops:
    classified = _classify_loops(_extract_loops(mask))
    return PixelLayerLoops(outer=classified.outer, holes=classified.holes)


def _safe_pitch_xy(pixel_size_um: float) -> float:
    if pixel_size_um > 0:
        return float(pixel_size_um) / 1000.0
    return 0.05


def _safe_pitch_z(layer_height_mm: float) -> float:
    if layer_height_mm > 0:
        return float(layer_height_mm)
    return 0.05


def _should_abort_decode_failures(*, layers_processed: int, decode_failures: int) -> bool:
    if decode_failures <= 0:
        return False
    if decode_failures >= _MAX_DECODE_FAILURES:
        return True
    if layers_processed < _MIN_LAYERS_FOR_FAILFAST:
        return False
    return (float(decode_failures) / float(layers_processed)) >= _MAX_DECODE_FAILURE_RATIO


def _build_mask(
    *,
    values: list[int] | np.ndarray,
    width: int,
    height: int,
    threshold: int,
    mode: str,
    xy_stride: int = 1,
) -> np.ndarray:
    arr = values if isinstance(values, np.ndarray) else np.asarray(values, dtype=np.uint8)
    arr = arr.reshape((height, width))
    step = max(1, int(xy_stride))
    if step > 1:
        arr = arr[::step, ::step]
    if mode == "threshold":
        limit = max(0, min(255, int(threshold)))
        return arr >= limit
    # "index_strict": best effort from decoded intensity semantics.
    return arr != 0


def _undirected_edge_key(a: PointI, b: PointI) -> tuple[PointI, PointI]:
    if a <= b:
        return (a, b)
    return (b, a)


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

    outgoing: dict[PointI, list[PointI]] = {}
    for start, end in edges.values():
        outgoing.setdefault(start, []).append(end)

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
