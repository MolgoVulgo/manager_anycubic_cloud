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
| cpp_native | 0.675 | 12926.803 | 8.622 | 0.021 | 12936.121 |
| cpp_opencv | 0.645 | 14473.090 | 7.982 | 0.037 | 14481.754 |

## Aggregate timings (cumulative CPU ms)

| backend | decode_cpu | contours_cpu | triangulation_cpu | buffers | total_cpu |
|---|---:|---:|---:|---:|---:|
| cpp_native | 253957.193 | 57793.080 | 4.181 | 0.021 | 311754.475 |
| cpp_opencv | 299390.369 | 47993.635 | 3.534 | 0.037 | 347387.575 |

## Speedups

- cpp_native_vs_opencv_total_x: 1.119x
- cpp_native_vs_opencv_total_cpu_x: 1.114x
- cpp_native_vs_opencv_contours_x: 0.830x
- cpp_native_vs_opencv_triangulation_x: 0.845x

## Functional deltas (opencv vs native)

| file | mesh Δmm2 | contour Δmm2 | tri Δ |
|---|---:|---:|---:|
| cube.pwmb | 0.000000 | 0.000000 | 0 |

## Decision

- Default recommended: **native**
- Reason: best aggregate runtime while keeping parity checks within tolerance.
