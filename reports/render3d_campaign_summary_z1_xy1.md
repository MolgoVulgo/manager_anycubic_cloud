# Render3D Campaign Summary

## Protocol

- files: cube.pwmb, raven_skull-12-25-v3.pwmb, raven_skull_19_12.pwmb
- xy_stride: 1
- z_stride: 1
- bin_mode: index_strict
- threshold: 1

## Aggregate timings (wall ms)

| backend | parse | contours_wall | triangulation_wall | buffers | total_wall |
|---|---:|---:|---:|---:|---:|
| cpp_native | 8.918 | 431935.202 | 764120.442 | 3279.385 | 1199343.947 |
| cpp_opencv | 7.223 | 320762.339 | 749774.701 | 3921.457 | 1074465.720 |

## Aggregate timings (cumulative CPU ms)

| backend | decode_cpu | contours_cpu | triangulation_cpu | buffers | total_cpu |
|---|---:|---:|---:|---:|---:|
| cpp_native | 12520447.287 | 567505.916 | 14365381.848 | 3279.385 | 27456614.436 |
| cpp_opencv | 9258858.514 | 401922.577 | 13461811.245 | 3921.457 | 23126513.793 |

## Speedups

- cpp_native_vs_opencv_total_x: 0.896x
- cpp_native_vs_opencv_total_cpu_x: 0.842x
- cpp_native_vs_opencv_contours_x: 0.708x
- cpp_native_vs_opencv_triangulation_x: 0.937x

## Functional deltas (opencv vs native)

| file | mesh Δmm2 | contour Δmm2 | tri Δ |
|---|---:|---:|---:|
| cube.pwmb | 0.000000 | 0.000000 | 0 |
| raven_skull-12-25-v3.pwmb | 0.000000 | 0.000000 | 5224 |
| raven_skull_19_12.pwmb | -27.229117 | 0.000000 | 9170 |

## Decision

- Default recommended: **opencv**
- Reason: best aggregate runtime while keeping parity checks within tolerance.
