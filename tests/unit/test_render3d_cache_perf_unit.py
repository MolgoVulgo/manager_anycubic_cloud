from __future__ import annotations

from pathlib import Path

from app_gui_qt.dialogs.pwmb3d_dialog import (
    _select_preview_xy_stride,
    _select_preview_xy_stride_for_complexity,
    _select_preview_z_stride,
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
    )

    build_data = build.as_log_data()
    gpu_data = gpu.as_log_data()
    assert build_data["layers_total"] == 10
    assert build_data["pool_kind"] == "threads"
    assert gpu_data["vbo_bytes_tri"] == 1000
    assert gpu_data["visible_layers_count"] == 12


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


def test_select_preview_z_stride_scales_for_heavy_complexity() -> None:
    assert _select_preview_z_stride(layer_count=398, width=5760, height=3600) == 1
    assert _select_preview_z_stride(layer_count=585, width=5760, height=3600) == 3
