# Render3D C++-Only Campaign Summary

## Protocol

- files: cube.pwmb, raven_skull-12-25-v3.pwmb, raven_skull_19_12.pwmb
- xy_stride: 1
- z_stride: 1
- bin_mode: index_strict
- threshold: 1
- workers_effective: 32

## Aggregate timings (wall ms)

| backend | parse | contours_wall | triangulation_wall | buffers | total_wall |
|---|---:|---:|---:|---:|---:|
| cpp_native | 4.686 | 344656.111 | 561421.886 | 68780.537 | 974863.220 |
| cpp_opencv | 4.916 | 297369.306 | 665774.586 | 66965.383 | 1030114.191 |

## Speedups

- cpp_native_vs_opencv_total_wall_x: 1.057x
- cpp_native_vs_opencv_total_cpu_x: 1.053x
- cpp_native_vs_opencv_contours_cpu_x: 0.873x
- cpp_native_vs_opencv_triangulation_cpu_x: 1.191x

## Functional deltas (opencv vs native)

| file | mesh area delta mm2 | triangle delta |
|---|---:|---:|
| cube.pwmb | 0.000000 | 0 |
| raven_skull-12-25-v3.pwmb | 0.000000 | 5224 |
| raven_skull_19_12.pwmb | -27.229117 | 9170 |

## Decision

- Default recommended: **native**
- Reason: best wall-time and no functional drift vs native reference.
