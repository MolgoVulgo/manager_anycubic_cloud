from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pytest

from accloud_core.logging_contract import JsonLineFormatter, operation_context
from pwmb_core.types import HeaderInfo, LayerDef, MachineInfo, PwmbDocument
from render3d_core.contours import build_contour_stack
from render3d_core.geometry_v2 import build_geometry_v2
from render3d_core.perf import BuildMetrics
from render3d_core.types import LayerLoops, PwmbContourStack


def _make_document(*, width: int, height: int, layers: int = 1) -> PwmbDocument:
    return PwmbDocument(
        path=Path("synthetic.pwmb"),
        version=516,
        file_size=0,
        header=HeaderInfo(
            pixel_size_um=100.0,
            layer_height_mm=0.05,
            anti_aliasing=1,
            resolution_x=width,
            resolution_y=height,
        ),
        machine=MachineInfo(machine_name="synthetic", layer_image_format="pw0Img"),
        layers=[LayerDef(index=idx, data_address=0, data_length=8) for idx in range(layers)],
    )


def _polygon_area(points: list[tuple[float, float]]) -> float:
    area = 0.0
    size = len(points)
    for idx in range(size):
        x1, y1 = points[idx]
        x2, y2 = points[(idx + 1) % size]
        area += (x1 * y2) - (x2 * y1)
    return 0.5 * area


def _triangles_area(vertices: list[tuple[float, float, float, float]]) -> float:
    area = 0.0
    for idx in range(0, len(vertices), 3):
        ax, ay, _az, _al = vertices[idx]
        bx, by, _bz, _bl = vertices[idx + 1]
        cx, cy, _cz, _cl = vertices[idx + 2]
        area += abs(((bx - ax) * (cy - ay) - (by - ay) * (cx - ax)) * 0.5)
    return area


class _CaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))


def test_build_contour_stack_detects_outer_and_hole(monkeypatch: pytest.MonkeyPatch) -> None:
    document = _make_document(width=5, height=5, layers=1)
    # Ring shape: one outer loop and one hole.
    decoded = [
        255, 255, 255, 255, 255,
        255,   0,   0,   0, 255,
        255,   0,   0,   0, 255,
        255,   0,   0,   0, 255,
        255, 255, 255, 255, 255,
    ]

    monkeypatch.setattr("render3d_core.contours.decode_layer", lambda *_args, **_kwargs: decoded)
    stack = build_contour_stack(document, threshold=128, binarization_mode="index_strict")

    assert 0 in stack.layers
    loops = stack.layers[0]
    assert len(loops.outer) == 1
    assert len(loops.holes) == 1
    assert abs(_polygon_area(loops.outer[0])) > abs(_polygon_area(loops.holes[0])) > 0.0


def test_build_contour_stack_threshold_mode_is_distinct(monkeypatch: pytest.MonkeyPatch) -> None:
    document = _make_document(width=3, height=1, layers=1)
    decoded = [0, 120, 200]
    monkeypatch.setattr("render3d_core.contours.decode_layer", lambda *_args, **_kwargs: decoded)

    threshold_stack = build_contour_stack(document, threshold=128, binarization_mode="threshold")
    index_stack = build_contour_stack(document, threshold=128, binarization_mode="index_strict")

    threshold_area = sum(abs(_polygon_area(loop)) for loop in threshold_stack.layers[0].outer)
    index_area = sum(abs(_polygon_area(loop)) for loop in index_stack.layers[0].outer)
    assert index_area > threshold_area


def test_build_contour_stack_reports_decode_failure_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    document = _make_document(width=2, height=2, layers=5)
    decoded = np.asarray([255, 255, 255, 255], dtype=np.uint8)

    def _decode(_document, layer_index: int, **_kwargs):
        if layer_index in {1, 3}:
            raise ValueError(f"bad layer {layer_index}")
        return decoded

    monkeypatch.setattr("render3d_core.contours.decode_layer", _decode)
    handler = _CaptureHandler()
    handler.setFormatter(JsonLineFormatter())
    root = logging.getLogger()
    old_handlers = list(root.handlers)
    old_level = root.level
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    try:
        _ = build_contour_stack(document, threshold=1, binarization_mode="index_strict")
    finally:
        root.handlers = old_handlers
        root.setLevel(old_level)

    payloads = [json.loads(line) for line in handler.lines]
    events = [str(item.get("event", "")) for item in payloads]
    assert "pwmb.contours_decode_fail_summary" in events
    summary = next(item for item in payloads if item.get("event") == "pwmb.contours_decode_fail_summary")
    assert summary["data"]["render3d"]["layers_decode_failed"] == 2
    assert summary["data"]["render3d"]["fail_fast"] is False


def test_build_contour_stack_fail_fast_stops_after_many_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    document = _make_document(width=2, height=2, layers=80)
    metrics = BuildMetrics()

    def _decode(*_args, **_kwargs):
        raise ValueError("broken")

    monkeypatch.setattr("render3d_core.contours.decode_layer", _decode)
    stack = build_contour_stack(document, threshold=1, binarization_mode="index_strict", metrics=metrics)

    assert not stack.layers
    assert 0 < metrics.layers_skipped < metrics.layers_total


def test_build_contour_stack_xy_stride_preserves_world_size(monkeypatch: pytest.MonkeyPatch) -> None:
    document = _make_document(width=4, height=4, layers=1)
    decoded = np.asarray(
        [
            255, 255, 255, 255,
            255, 255, 255, 255,
            255, 255, 255, 255,
            255, 255, 255, 255,
        ],
        dtype=np.uint8,
    )
    monkeypatch.setattr("render3d_core.contours.decode_layer", lambda *_args, **_kwargs: decoded)

    stack_full = build_contour_stack(document, threshold=1, binarization_mode="index_strict", xy_stride=1)
    stack_down = build_contour_stack(document, threshold=1, binarization_mode="index_strict", xy_stride=2)

    area_full = abs(_polygon_area(stack_full.layers[0].outer[0]))
    area_down = abs(_polygon_area(stack_down.layers[0].outer[0]))
    assert area_down == pytest.approx(area_full, rel=1e-6)


def test_build_geometry_v2_generates_ranges_and_vertices() -> None:
    stack = PwmbContourStack(
        pitch_x_mm=0.1,
        pitch_y_mm=0.1,
        pitch_z_mm=0.05,
        layers={
            3: LayerLoops(
                outer=[[(-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)]],
                holes=[],
            )
        },
    )
    geometry = build_geometry_v2(stack)

    assert geometry.tri_range[3].count == 6
    assert geometry.line_range[3].count == 8
    assert geometry.point_range[3].count == 4
    assert len(geometry.triangle_vertices) == 6
    assert len(geometry.line_vertices) == 8
    assert len(geometry.point_vertices) == 4
    assert _triangles_area(geometry.triangle_vertices) == pytest.approx(4.0, rel=1e-6)
    assert all(vertex[2] == pytest.approx(0.0) for vertex in geometry.triangle_vertices)


def test_build_geometry_v2_hole_reduces_filled_area() -> None:
    stack = PwmbContourStack(
        pitch_x_mm=0.1,
        pitch_y_mm=0.1,
        pitch_z_mm=0.1,
        layers={
            0: LayerLoops(
                outer=[[(-2.0, -2.0), (2.0, -2.0), (2.0, 2.0), (-2.0, 2.0)]],
                holes=[[(-1.0, -1.0), (-1.0, 1.0), (1.0, 1.0), (1.0, -1.0)]],
            )
        },
    )
    geometry = build_geometry_v2(stack)
    area = _triangles_area(geometry.triangle_vertices)
    assert 10.0 < area < 14.0


def test_render3d_pipeline_emits_expected_logging_events(monkeypatch: pytest.MonkeyPatch) -> None:
    document = _make_document(width=4, height=4, layers=1)
    decoded = [
        255, 255, 255, 255,
        255, 255, 255, 255,
        255, 255, 255, 255,
        255, 255, 255, 255,
    ]
    monkeypatch.setattr("render3d_core.contours.decode_layer", lambda *_args, **_kwargs: decoded)

    handler = _CaptureHandler()
    handler.setFormatter(JsonLineFormatter())
    root = logging.getLogger()
    old_handlers = list(root.handlers)
    old_level = root.level
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    try:
        with operation_context("11111111-1111-1111-1111-111111111111"):
            stack = build_contour_stack(document, threshold=1, binarization_mode="index_strict")
            _ = build_geometry_v2(stack)
    finally:
        root.handlers = old_handlers
        root.setLevel(old_level)

    payloads = [json.loads(line) for line in handler.lines]
    events = {str(item.get("event", "")) for item in payloads}
    assert "pwmb.contours_ok" in events
    assert "build.stage_start" in events
    assert "build.stage_done" in events
    assert all(str(item.get("op_id", "")).strip() == "11111111-1111-1111-1111-111111111111" for item in payloads)
