from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class BuildMetrics:
    parse_ms: float = 0.0
    # Task cumulative time: sum of per-layer jobs (can exceed wall time in parallel mode).
    decode_ms_total: float = 0.0
    decode_mb_s: float = 0.0
    # Task cumulative time: sum of per-layer contour jobs.
    contours_ms_total: float = 0.0
    # Wall-clock time for full contour stage (decode + mask + loops + assemble).
    contours_wall_ms: float = 0.0
    # Task cumulative time: sum of per-layer triangulation jobs.
    triangulation_ms_total: float = 0.0
    # Wall-clock time for triangulation stage.
    triangulation_wall_ms: float = 0.0
    buffers_ms_total: float = 0.0
    layers_total: int = 0
    layers_built: int = 0
    layers_skipped: int = 0
    loops_total: int = 0
    vertices_total: int = 0
    triangles_total: int = 0
    pool_kind: str = "threads"
    workers: int = 1
    contours_workers_effective: int = 1
    triangulation_workers_effective: int = 1

    def as_log_data(self) -> dict[str, object]:
        contour_stage_parallelism = 0.0
        if self.contours_wall_ms > 0.0:
            contour_stage_parallelism = (self.decode_ms_total + self.contours_ms_total) / self.contours_wall_ms
        triangulation_parallelism = 0.0
        if self.triangulation_wall_ms > 0.0:
            triangulation_parallelism = self.triangulation_ms_total / self.triangulation_wall_ms
        return {
            "parse_ms": round(self.parse_ms, 3),
            "decode_ms_total": round(self.decode_ms_total, 3),
            "decode_mb_s": round(self.decode_mb_s, 3),
            "contours_ms_total": round(self.contours_ms_total, 3),
            "contours_wall_ms": round(self.contours_wall_ms, 3),
            "triangulation_ms_total": round(self.triangulation_ms_total, 3),
            "triangulation_wall_ms": round(self.triangulation_wall_ms, 3),
            "contour_stage_parallelism": round(contour_stage_parallelism, 3),
            "triangulation_parallelism": round(triangulation_parallelism, 3),
            "buffers_ms_total": round(self.buffers_ms_total, 3),
            "layers_total": int(self.layers_total),
            "layers_built": int(self.layers_built),
            "layers_skipped": int(self.layers_skipped),
            "loops_total": int(self.loops_total),
            "vertices_total": int(self.vertices_total),
            "triangles_total": int(self.triangles_total),
            "pool_kind": self.pool_kind,
            "workers": int(self.workers),
            "contours_workers_effective": int(self.contours_workers_effective),
            "triangulation_workers_effective": int(self.triangulation_workers_effective),
        }


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
    msaa_samples: int = 0
    line_width_px: float = 1.0
    point_size_px: float = 1.0
    fill_alpha_scale: float = 1.0

    def as_log_data(self) -> dict[str, object]:
        return {
            "upload_ms": round(self.upload_ms, 3),
            "draw_ms_tri": round(self.draw_ms_tri, 3),
            "draw_ms_line": round(self.draw_ms_line, 3),
            "draw_ms_point": round(self.draw_ms_point, 3),
            "vbo_bytes_tri": int(self.vbo_bytes_tri),
            "vbo_bytes_line": int(self.vbo_bytes_line),
            "vbo_bytes_point": int(self.vbo_bytes_point),
            "visible_layers_count": int(self.visible_layers_count),
            "msaa_samples": int(self.msaa_samples),
            "line_width_px": round(self.line_width_px, 3),
            "point_size_px": round(self.point_size_px, 3),
            "fill_alpha_scale": round(self.fill_alpha_scale, 3),
        }
