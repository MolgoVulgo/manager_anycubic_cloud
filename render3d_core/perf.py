from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class BuildMetrics:
    parse_ms: float = 0.0
    decode_ms_total: float = 0.0
    decode_mb_s: float = 0.0
    contours_ms_total: float = 0.0
    triangulation_ms_total: float = 0.0
    buffers_ms_total: float = 0.0
    layers_total: int = 0
    layers_built: int = 0
    layers_skipped: int = 0
    loops_total: int = 0
    vertices_total: int = 0
    triangles_total: int = 0
    pool_kind: str = "threads"
    workers: int = 1

    def as_log_data(self) -> dict[str, object]:
        return {
            "parse_ms": round(self.parse_ms, 3),
            "decode_ms_total": round(self.decode_ms_total, 3),
            "decode_mb_s": round(self.decode_mb_s, 3),
            "contours_ms_total": round(self.contours_ms_total, 3),
            "triangulation_ms_total": round(self.triangulation_ms_total, 3),
            "buffers_ms_total": round(self.buffers_ms_total, 3),
            "layers_total": int(self.layers_total),
            "layers_built": int(self.layers_built),
            "layers_skipped": int(self.layers_skipped),
            "loops_total": int(self.loops_total),
            "vertices_total": int(self.vertices_total),
            "triangles_total": int(self.triangles_total),
            "pool_kind": self.pool_kind,
            "workers": int(self.workers),
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
        }
