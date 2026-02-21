from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class BuildMetrics:
    parse_ms: float = 0.0
    decode_ms_total: float = 0.0
    contours_ms_total: float = 0.0
    triangulation_ms_total: float = 0.0
    layers_total: int = 0
    layers_built: int = 0
    layers_skipped: int = 0
    loops_total: int = 0
    vertices_total: int = 0
    triangles_total: int = 0
    pool_kind: str = "threads"
    workers: int = 1


@dataclass(slots=True)
class GpuMetrics:
    upload_ms: float = 0.0
    draw_ms_tri: float = 0.0
    draw_ms_line: float = 0.0
    draw_ms_point: float = 0.0
    vbo_bytes_tri: int = 0
    vbo_bytes_line: int = 0
    vbo_bytes_point: int = 0
    visible_layers_count: int = 0

