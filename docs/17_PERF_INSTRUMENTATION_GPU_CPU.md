### CPU (build)
Mesures minimales :
- `parse_ms`
- `decode_ms_total`, `decode_mb_s`
- `contours_ms_total`
- `triangulation_ms_total`
- `layers_total`, `layers_built`, `layers_skipped`
- `loops_total`, `vertices_total`, `triangles_total`
- `pool_kind` : `threads|processes`, `workers`.

### GPU (frame)
- `upload_ms`
- `vbo_bytes_tri/line/point`
- `draw_ms` (tri/line/point)
- `visible_layers_count` (après stride/cutoff)

### Logs (format stable)
- `PWMB build stage=... percent=...`
- `PWMB geometry build_ms=... triangles=... lines=... points=...`
- `PWMB holes total=... assigned=... merged=... skipped=...`
- `PWMB draw mode=... visible_layers=...`

---

