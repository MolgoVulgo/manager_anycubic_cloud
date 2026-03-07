# Render3D Campaign Summary

## Protocol

- files: cube.pwmb
- xy_stride: 1
- z_stride: 1
- bin_mode: index_strict
- threshold: 1

## Aggregate timings (wall ms)

| backend | parse | contours_wall | triangulation_wall | buffers | total_wall |
|---|---:|---:|---:|---:|---:|
| cpp_native | 0.678 | 12696.569 | 9.575 | 0.042 | 12706.864 |
| cpp_opencv | 0.646 | 14395.239 | 9.164 | 0.022 | 14405.071 |

## Aggregate timings (cumulative CPU ms)

| backend | decode_cpu | contours_cpu | triangulation_cpu | buffers | total_cpu |
|---|---:|---:|---:|---:|---:|
| cpp_native | 113281.287 | 56378.060 | 4.156 | 0.042 | 169663.545 |
| cpp_opencv | 117786.534 | 74606.438 | 4.211 | 0.022 | 192397.205 |

## Speedups

- cpp_native_vs_opencv_total_x: 1.134x
- cpp_native_vs_opencv_total_cpu_x: 1.134x
- cpp_native_vs_opencv_contours_x: 1.323x
- cpp_native_vs_opencv_triangulation_x: 1.013x

## Functional deltas (opencv vs native)

| file | mesh Δmm2 | contour Δmm2 | tri Δ |
|---|---:|---:|---:|
| cube.pwmb | 0.000000 | 0.000000 | 0 |

## Decision

- Default recommended: **native**
- Reason: best aggregate runtime while keeping parity checks within tolerance.
