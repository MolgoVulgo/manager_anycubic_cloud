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
| cpp_native | 0.635 | 9198.432 | 2.680 | 0.628 | 9202.375 |
| cpp_opencv | 0.594 | 11731.286 | 2.659 | 0.641 | 11735.180 |

## Aggregate timings (cumulative CPU ms)

| backend | decode_cpu | contours_cpu | triangulation_cpu | buffers | total_cpu |
|---|---:|---:|---:|---:|---:|
| cpp_native | 1226.666 | 7969.038 | 2.680 | 0.628 | 9199.012 |
| cpp_opencv | 1406.653 | 10265.489 | 2.659 | 0.641 | 11675.442 |

## Speedups

- cpp_native_vs_opencv_total_x: 1.275x
- cpp_native_vs_opencv_total_cpu_x: 1.269x
- cpp_native_vs_opencv_contours_x: 1.288x
- cpp_native_vs_opencv_triangulation_x: 0.992x

## Functional deltas (opencv vs native)

| file | mesh Δmm2 | contour Δmm2 | tri Δ |
|---|---:|---:|---:|
| cube.pwmb | 0.000000 | 0.000000 | 0 |

## Decision

- Default recommended: **native**
- Reason: best aggregate runtime while keeping parity checks within tolerance.
