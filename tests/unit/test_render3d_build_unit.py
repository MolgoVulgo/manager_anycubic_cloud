from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pytest

from accloud_core.logging_contract import JsonLineFormatter, operation_context
from pwmb_core.types import HeaderInfo, LayerDef, MachineInfo, PwmbDocument
from render3d_core.contours import PixelLayerLoops, build_contour_stack
from render3d_core.geometry_v2 import build_geometry_v2
from render3d_core.perf import BuildMetrics
from render3d_core.task_runner import CancellationToken, CancelledError
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


def _stack_area_mm2(stack: PwmbContourStack) -> float:
    total = 0.0
    for loops in stack.layers.values():
        outer = sum(abs(_polygon_area(loop)) for loop in loops.outer)
        holes = sum(abs(_polygon_area(loop)) for loop in loops.holes)
        total += max(0.0, outer - holes)
    return total


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
    monkeypatch.setattr("render3d_core.contours.decode_layer_index_mask", lambda *_args, **_kwargs: decoded)
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
    monkeypatch.setattr(
        "render3d_core.contours.decode_layer_index_mask",
        lambda *_args, **_kwargs: [0, 255, 255],
    )

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
    monkeypatch.setattr("render3d_core.contours.decode_layer_index_mask", _decode)
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
    monkeypatch.setattr("render3d_core.contours.decode_layer_index_mask", _decode)
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
    monkeypatch.setattr("render3d_core.contours.decode_layer_index_mask", lambda *_args, **_kwargs: decoded)

    stack_full = build_contour_stack(document, threshold=1, binarization_mode="index_strict", xy_stride=1)
    stack_down = build_contour_stack(document, threshold=1, binarization_mode="index_strict", xy_stride=2)

    area_full = abs(_polygon_area(stack_full.layers[0].outer[0]))
    area_down = abs(_polygon_area(stack_down.layers[0].outer[0]))
    assert area_down == pytest.approx(area_full, rel=1e-6)


def test_build_contour_stack_accepts_custom_pixel_extractor(monkeypatch: pytest.MonkeyPatch) -> None:
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
    monkeypatch.setattr("render3d_core.contours.decode_layer_index_mask", lambda *_args, **_kwargs: decoded)

    calls = {"count": 0}

    def _pixel_extractor(mask: np.ndarray) -> PixelLayerLoops:
        calls["count"] += 1
        assert mask.shape == (4, 4)
        return PixelLayerLoops(
            outer=[[(0, 0), (4, 0), (4, 4), (0, 4)]],
            holes=[],
        )

    stack = build_contour_stack(
        document,
        threshold=1,
        binarization_mode="index_strict",
        pixel_extractor=_pixel_extractor,
    )

    assert calls["count"] == 1
    assert 0 in stack.layers
    assert len(stack.layers[0].outer) == 1
    assert len(stack.layers[0].holes) == 0


def test_build_contour_stack_reuses_persistent_decode_reader(monkeypatch: pytest.MonkeyPatch) -> None:
    document = _make_document(width=2, height=2, layers=3)
    decoded = np.asarray([255, 255, 255, 255], dtype=np.uint8)
    reader = object()
    seen_readers: list[object | None] = []

    class _ReaderContext:
        def __enter__(self):
            return reader

        def __exit__(self, _exc_type, _exc, _tb):
            return None

    def _decode(_document, _layer_index: int, **kwargs):
        seen_readers.append(kwargs.get("reader"))
        return decoded

    monkeypatch.setattr("render3d_core.contours.open_layer_blob_reader", lambda _document: _ReaderContext())
    monkeypatch.setattr("render3d_core.contours.decode_layer", _decode)
    monkeypatch.setattr("render3d_core.contours.decode_layer_index_mask", _decode)

    stack = build_contour_stack(document, threshold=1, binarization_mode="index_strict")

    assert sorted(stack.layers.keys()) == [0, 1, 2]
    assert seen_readers == [reader, reader, reader]


def test_build_contour_stack_decodes_sampled_layers_by_position(monkeypatch: pytest.MonkeyPatch) -> None:
    document = _make_document(width=2, height=2, layers=3)
    document.layers = [
        LayerDef(index=0, data_address=0, data_length=8),
        LayerDef(index=10, data_address=8, data_length=8),
        LayerDef(index=20, data_address=16, data_length=8),
    ]
    decoded = np.asarray([255, 255, 255, 255], dtype=np.uint8)
    seen_positions: list[int] = []

    def _decode(_document, layer_index: int, **_kwargs):
        seen_positions.append(int(layer_index))
        return decoded

    monkeypatch.setattr("render3d_core.contours.decode_layer", _decode)
    monkeypatch.setattr("render3d_core.contours.decode_layer_index_mask", _decode)
    stack = build_contour_stack(document, threshold=1, binarization_mode="index_strict")

    assert seen_positions == [0, 1, 2]
    assert sorted(stack.layers.keys()) == [0, 10, 20]


def test_build_contour_stack_honors_cancellation_token(monkeypatch: pytest.MonkeyPatch) -> None:
    document = _make_document(width=2, height=2, layers=3)
    decoded = np.asarray([255, 255, 255, 255], dtype=np.uint8)
    token = CancellationToken()
    decode_calls = {"count": 0}

    def _decode(_document, _layer_index: int, **_kwargs):
        decode_calls["count"] += 1
        token.cancel()
        return decoded

    monkeypatch.setattr("render3d_core.contours.decode_layer", _decode)
    monkeypatch.setattr("render3d_core.contours.decode_layer_index_mask", _decode)

    with pytest.raises(CancelledError):
        _ = build_contour_stack(
            document,
            threshold=1,
            binarization_mode="index_strict",
            cancel_token=token,
        )

    assert decode_calls["count"] == 1


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


def test_build_geometry_v2_contours_only_skips_triangles() -> None:
    stack = PwmbContourStack(
        pitch_x_mm=0.1,
        pitch_y_mm=0.1,
        pitch_z_mm=0.05,
        layers={
            0: LayerLoops(
                outer=[[(-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)]],
                holes=[],
            )
        },
    )
    geometry = build_geometry_v2(stack, include_fill=False)

    assert len(geometry.triangle_vertices) == 0
    assert geometry.tri_range[0].count == 0
    assert len(geometry.line_vertices) > 0
    assert len(geometry.point_vertices) > 0


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


def test_build_geometry_v2_non_axis_aligned_holes_preserve_area() -> None:
    stack = PwmbContourStack(
        pitch_x_mm=0.1,
        pitch_y_mm=0.1,
        pitch_z_mm=0.1,
        layers={
            0: LayerLoops(
                outer=[
                    [
                        (-3.0, 0.0),
                        (-1.0, -2.5),
                        (2.5, -2.0),
                        (4.5, 0.8),
                        (3.8, 3.5),
                        (1.2, 4.8),
                        (-2.4, 3.7),
                    ]
                ],
                holes=[
                    [(0.2, -0.9), (1.4, -0.2), (0.9, 1.0), (-0.1, 0.2)],
                    [(1.8, 1.1), (2.9, 1.7), (2.3, 2.8), (1.3, 2.1)],
                ],
            )
        },
    )

    geometry = build_geometry_v2(stack)
    area_mesh = _triangles_area(geometry.triangle_vertices)
    area_contour = _stack_area_mm2(stack)

    assert area_mesh == pytest.approx(area_contour, rel=1e-4)
    assert len(geometry.triangle_vertices) >= 6


def test_build_geometry_v2_materializes_contiguous_buffers_and_indices() -> None:
    stack = PwmbContourStack(
        pitch_x_mm=0.1,
        pitch_y_mm=0.1,
        pitch_z_mm=0.05,
        layers={
            2: LayerLoops(
                outer=[[(-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)]],
                holes=[],
            )
        },
    )
    metrics = BuildMetrics()
    geometry = build_geometry_v2(stack, metrics=metrics)

    assert isinstance(geometry.triangle_vertices, np.ndarray)
    assert isinstance(geometry.line_vertices, np.ndarray)
    assert isinstance(geometry.point_vertices, np.ndarray)
    assert geometry.triangle_vertices.dtype == np.float32
    assert geometry.line_vertices.dtype == np.float32
    assert geometry.point_vertices.dtype == np.float32
    assert geometry.triangle_vertices.flags["C_CONTIGUOUS"]
    assert geometry.line_vertices.flags["C_CONTIGUOUS"]
    assert geometry.point_vertices.flags["C_CONTIGUOUS"]
    assert geometry.triangle_indices is not None
    assert geometry.line_indices is not None
    assert geometry.point_indices is not None
    assert geometry.triangle_indices.dtype == np.uint32
    assert geometry.line_indices.dtype == np.uint32
    assert geometry.point_indices.dtype == np.uint32
    assert geometry.triangle_indices.shape[1] == 3
    assert geometry.line_indices.shape[1] == 2
    assert metrics.buffers_ms_total >= 0.0


def test_build_geometry_v2_honors_cancellation_token() -> None:
    stack = PwmbContourStack(
        pitch_x_mm=0.1,
        pitch_y_mm=0.1,
        pitch_z_mm=0.05,
        layers={
            0: LayerLoops(
                outer=[[(-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)]],
                holes=[],
            )
        },
    )
    token = CancellationToken()

    def _triangulator(*_args, **_kwargs):
        token.cancel()
        return []

    with pytest.raises(CancelledError):
        _ = build_geometry_v2(
            stack,
            triangulator=_triangulator,
            cancel_token=token,
        )


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
