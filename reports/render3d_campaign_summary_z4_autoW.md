# Render3D Campaign Summary

## Protocol

- files: cube.pwmb, raven_skull-12-25-v3.pwmb, raven_skull_19_12.pwmb
- xy_stride: 4
- z_stride: 4
- bin_mode: index_strict
- threshold: 1

## Aggregate timings (ms)

| backend | decode | contours | triangulation | buffers | total |
|---|---:|---:|---:|---:|---:|
| python | 103493.606 | 187475.384 | 256753.704 | 4010.807 | 551733.501 |
| cpp_native | 74612.898 | 47370.173 | 172695.398 | 3291.093 | 297969.562 |
| cpp_opencv | 74531.962 | 45359.374 | 217163.840 | 3360.535 | 340415.711 |

## Speedups

- cpp_native_vs_python_total_x: 1.852x
- cpp_opencv_vs_python_total_x: 1.621x
- cpp_native_vs_opencv_total_x: 1.142x
- cpp_native_vs_opencv_contours_x: 0.958x
- cpp_native_vs_opencv_triangulation_x: 1.257x

## Functional deltas vs python

| file | native mesh Δmm2 | opencv mesh Δmm2 | native tri Δ | opencv tri Δ |
|---|---:|---:|---:|---:|
| cube.pwmb | 0.000000 | 0.000000 | 0 | 0 |
| raven_skull-12-25-v3.pwmb | 0.000000 | 0.000001 | 0 | 820 |
| raven_skull_19_12.pwmb | 0.000000 | -105.953284 | 0 | 5502 |

## Decision

- Default recommended: **native**
- Reason: best parity vs python and best overall runtime on measured corpus.
