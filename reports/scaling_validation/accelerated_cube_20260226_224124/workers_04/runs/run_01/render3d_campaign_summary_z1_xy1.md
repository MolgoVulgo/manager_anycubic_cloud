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
| cpp_native | 0.679 | 12040.361 | 6.643 | 0.026 | 12047.709 |
| cpp_opencv | 1.215 | 13810.002 | 8.083 | 0.023 | 13819.323 |

## Aggregate timings (cumulative CPU ms)

| backend | decode_cpu | contours_cpu | triangulation_cpu | buffers | total_cpu |
|---|---:|---:|---:|---:|---:|
| cpp_native | 20861.977 | 26593.100 | 3.319 | 0.026 | 47458.422 |
| cpp_opencv | 22031.949 | 32798.489 | 3.780 | 0.023 | 54834.241 |

## Speedups

- cpp_native_vs_opencv_total_x: 1.147x
- cpp_native_vs_opencv_total_cpu_x: 1.155x
- cpp_native_vs_opencv_contours_x: 1.233x
- cpp_native_vs_opencv_triangulation_x: 1.139x

## Functional deltas (opencv vs native)

| file | mesh Δmm2 | contour Δmm2 | tri Δ |
|---|---:|---:|---:|
| cube.pwmb | 0.000000 | 0.000000 | 0 |

## Decision

- Default recommended: **native**
- Reason: best aggregate runtime while keeping parity checks within tolerance.
