from __future__ import annotations

from pathlib import Path

import pytest

from app_gui_qt.dialogs.pwmb3d_dialog import (
    _QUALITY_PRESETS,
    _RENDER_PALETTES,
    _camera_pose_for_orbit,
    _pan_center_for_drag,
    _quality_ratio_from_index,
    _select_preview_xy_stride_for_quality,
    _sample_layers_by_ratio,
    _select_preview_xy_stride,
    _select_preview_xy_stride_for_complexity,
    _select_preview_z_stride,
    _sort_layers_back_to_front,
    _resolve_viewer_fill_alpha_scale,
    _resolve_viewer_line_width_px,
    _resolve_viewer_msaa_samples,
    _resolve_viewer_point_size_px,
)
from pwmb_core.types import HeaderInfo, LayerDef, MachineInfo, PwmbDocument
from render3d_core.cache import compute_file_signature, make_cache_key
from render3d_core.perf import BuildMetrics, GpuMetrics


def _document(path: Path) -> PwmbDocument:
    return PwmbDocument(
        path=path,
        version=516,
        file_size=path.stat().st_size if path.exists() else 0,
        header=HeaderInfo(
            pixel_size_um=50.0,
            layer_height_mm=0.05,
            anti_aliasing=1,
            resolution_x=10,
            resolution_y=10,
        ),
        machine=MachineInfo(machine_name="M", layer_image_format="pw0Img"),
        layers=[LayerDef(index=0, data_address=0, data_length=0)],
        lut=[0, 17, 34, 51],
    )


def test_compute_file_signature_changes_on_content_update(tmp_path: Path) -> None:
    target = tmp_path / "sample.pwmb"
    target.write_bytes(b"abc")
    sig1 = compute_file_signature(target)
    target.write_bytes(b"abcd")
    sig2 = compute_file_signature(target)
    assert sig1 != sig2


def test_make_cache_key_reflects_invalidation_params(tmp_path: Path) -> None:
    target = tmp_path / "sample.pwmb"
    target.write_bytes(b"content")
    document = _document(target)

    key_a = make_cache_key(
        document,
        threshold=1,
        bin_mode="index_strict",
        xy_stride=1,
        z_stride=1,
        simplify_epsilon=0.0,
        max_layers=None,
        max_vertices=None,
        render_mode="fill",
        file_signature="sig",
    )
    key_b = make_cache_key(
        document,
        threshold=2,
        bin_mode="index_strict",
        xy_stride=1,
        z_stride=1,
        simplify_epsilon=0.0,
        max_layers=None,
        max_vertices=None,
        render_mode="fill",
        file_signature="sig",
    )
    key_c = make_cache_key(
        document,
        threshold=1,
        bin_mode="threshold",
        xy_stride=1,
        z_stride=1,
        simplify_epsilon=0.0,
        max_layers=None,
        max_vertices=None,
        render_mode="fill",
        file_signature="sig",
    )
    assert key_a != key_b
    assert key_a != key_c


def test_perf_metrics_export_log_dicts() -> None:
    build = BuildMetrics(
        parse_ms=1.2,
        decode_ms_total=3.4,
        decode_mb_s=12.3,
        contours_ms_total=5.6,
        triangulation_ms_total=7.8,
        layers_total=10,
        layers_built=8,
        layers_skipped=2,
        loops_total=40,
        vertices_total=100,
        triangles_total=25,
        pool_kind="threads",
        workers=4,
    )
    gpu = GpuMetrics(
        upload_ms=1.1,
        draw_ms_tri=2.2,
        draw_ms_line=3.3,
        draw_ms_point=4.4,
        vbo_bytes_tri=1000,
        vbo_bytes_line=2000,
        vbo_bytes_point=3000,
        visible_layers_count=12,
        msaa_samples=4,
        line_width_px=1.35,
        point_size_px=2.25,
        fill_alpha_scale=0.92,
    )

    build_data = build.as_log_data()
    gpu_data = gpu.as_log_data()
    assert build_data["layers_total"] == 10
    assert build_data["pool_kind"] == "threads"
    assert gpu_data["vbo_bytes_tri"] == 1000
    assert gpu_data["visible_layers_count"] == 12
    assert gpu_data["msaa_samples"] == 4


def test_select_preview_xy_stride_is_adaptive() -> None:
    assert _select_preview_xy_stride(width=800, height=600) == 1
    assert _select_preview_xy_stride(width=2200, height=1600) == 2
    assert _select_preview_xy_stride(width=3200, height=2100) == 3
    assert _select_preview_xy_stride(width=5760, height=3600) == 4


def test_select_preview_z_stride_limits_visible_layers() -> None:
    assert _select_preview_z_stride(layer_count=100) == 1
    assert _select_preview_z_stride(layer_count=600) == 1
    assert _select_preview_z_stride(layer_count=601) == 2
    assert _select_preview_z_stride(layer_count=1223) == 3


def test_select_preview_xy_stride_scales_for_heavy_complexity() -> None:
    assert _select_preview_xy_stride_for_complexity(width=5760, height=3600, layer_count=398) == 4
    assert _select_preview_xy_stride_for_complexity(width=5760, height=3600, layer_count=585) == 6


def test_select_preview_xy_stride_for_quality_forces_xy1_at_100_percent() -> None:
    assert (
        _select_preview_xy_stride_for_quality(
            width=5760,
            height=3600,
            layer_count=585,
            quality_ratio=1.0,
        )
        == 1
    )


def test_select_preview_xy_stride_for_quality_keeps_adaptive_stride_below_100_percent() -> None:
    assert (
        _select_preview_xy_stride_for_quality(
            width=5760,
            height=3600,
            layer_count=585,
            quality_ratio=0.66,
        )
        == 6
    )


def test_select_preview_z_stride_scales_for_heavy_complexity() -> None:
    assert _select_preview_z_stride(layer_count=398, width=5760, height=3600) == 1
    assert _select_preview_z_stride(layer_count=585, width=5760, height=3600) == 3


def test_sort_layers_back_to_front_changes_with_camera_orientation() -> None:
    layers = [0, 1, 2]
    layer_z = {0: 0.0, 1: 1.0, 2: 2.0}
    center = (0.0, 0.0, 1.0)

    front_view = _sort_layers_back_to_front(
        layer_ids=layers,
        layer_z=layer_z,
        center=center,
        distance=10.0,
        yaw_deg=0.0,
        pitch_deg=0.0,
    )
    back_view = _sort_layers_back_to_front(
        layer_ids=layers,
        layer_z=layer_z,
        center=center,
        distance=10.0,
        yaw_deg=180.0,
        pitch_deg=0.0,
    )

    assert front_view == [0, 1, 2]
    assert back_view == [2, 1, 0]


def test_sort_layers_back_to_front_stable_tie_break_on_layer_id() -> None:
    ordered = _sort_layers_back_to_front(
        layer_ids=[7, 2, 5],
        layer_z={7: 1.0, 2: 1.0, 5: 1.0},
        center=(0.0, 0.0, 1.0),
        distance=5.0,
        yaw_deg=0.0,
        pitch_deg=0.0,
    )
    assert ordered == [2, 5, 7]


def test_camera_pose_for_orbit_returns_normalized_forward_vector() -> None:
    _camera, forward = _camera_pose_for_orbit(
        center=(0.0, 0.0, 0.0),
        distance=3.5,
        yaw_deg=25.0,
        pitch_deg=-15.0,
    )
    norm = (forward[0] * forward[0] + forward[1] * forward[1] + forward[2] * forward[2]) ** 0.5
    assert norm == pytest.approx(1.0, rel=1e-6)


def test_pan_center_for_drag_moves_center_with_right_drag() -> None:
    center = (0.0, 0.0, 0.0)
    moved_right = _pan_center_for_drag(
        center=center,
        distance=10.0,
        yaw_deg=0.0,
        pitch_deg=0.0,
        dx_px=20.0,
        dy_px=0.0,
    )
    moved_up = _pan_center_for_drag(
        center=center,
        distance=10.0,
        yaw_deg=0.0,
        pitch_deg=0.0,
        dx_px=0.0,
        dy_px=-20.0,
    )
    assert moved_right[0] < center[0]
    assert moved_up[1] < center[1]


def test_render_palette_presets_expose_expected_choices() -> None:
    assert len(_RENDER_PALETTES) == 6
    assert len({palette.label for palette in _RENDER_PALETTES}) == 6
    assert any(palette.label == "Light Gray Cyan" for palette in _RENDER_PALETTES)


def test_quality_presets_are_100_66_33() -> None:
    labels = [label for label, _ratio in _QUALITY_PRESETS]
    ratios = [ratio for _label, ratio in _QUALITY_PRESETS]
    assert labels == ["Qualite max (100%)", "Qualite intermediaire (66%)", "Qualite basse (33%)"]
    assert ratios == [1.0, 0.66, 0.33]
    assert _quality_ratio_from_index(0) == pytest.approx(1.0, rel=1e-6)
    assert _quality_ratio_from_index(1) == pytest.approx(0.66, rel=1e-6)
    assert _quality_ratio_from_index(2) == pytest.approx(0.33, rel=1e-6)


def test_sample_layers_by_ratio_keeps_expected_density() -> None:
    layers = list(range(12))
    full = _sample_layers_by_ratio(layers, 1.0)
    medium = _sample_layers_by_ratio(layers, 0.66)
    low = _sample_layers_by_ratio(layers, 0.33)
    assert len(full) == 12
    assert len(medium) == 8
    assert len(low) == 4


def test_viewer_gpu_style_env_resolution_and_clamp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RENDER3D_MSAA_SAMPLES", raising=False)
    monkeypatch.delenv("RENDER3D_LINE_WIDTH_PX", raising=False)
    monkeypatch.delenv("RENDER3D_POINT_SIZE_PX", raising=False)
    monkeypatch.delenv("RENDER3D_FILL_ALPHA_SCALE", raising=False)

    assert _resolve_viewer_msaa_samples() == 4
    assert _resolve_viewer_line_width_px() == pytest.approx(1.35, rel=1e-6)
    assert _resolve_viewer_point_size_px() == pytest.approx(2.25, rel=1e-6)
    assert _resolve_viewer_fill_alpha_scale() == pytest.approx(0.92, rel=1e-6)

    monkeypatch.setenv("RENDER3D_MSAA_SAMPLES", "12")
    monkeypatch.setenv("RENDER3D_LINE_WIDTH_PX", "10")
    monkeypatch.setenv("RENDER3D_POINT_SIZE_PX", "-3")
    monkeypatch.setenv("RENDER3D_FILL_ALPHA_SCALE", "0")
    assert _resolve_viewer_msaa_samples() == 8
    assert _resolve_viewer_line_width_px() == pytest.approx(4.0, rel=1e-6)
    assert _resolve_viewer_point_size_px() == pytest.approx(1.0, rel=1e-6)
    assert _resolve_viewer_fill_alpha_scale() == pytest.approx(0.25, rel=1e-6)

    monkeypatch.setenv("RENDER3D_MSAA_SAMPLES", "bad")
    monkeypatch.setenv("RENDER3D_LINE_WIDTH_PX", "bad")
    monkeypatch.setenv("RENDER3D_POINT_SIZE_PX", "bad")
    monkeypatch.setenv("RENDER3D_FILL_ALPHA_SCALE", "bad")
    assert _resolve_viewer_msaa_samples() == 4
    assert _resolve_viewer_line_width_px() == pytest.approx(1.35, rel=1e-6)
    assert _resolve_viewer_point_size_px() == pytest.approx(2.25, rel=1e-6)
    assert _resolve_viewer_fill_alpha_scale() == pytest.approx(0.92, rel=1e-6)
