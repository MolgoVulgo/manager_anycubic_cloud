# Render3D Campaign Summary

## Protocol

- files: cube.pwmb, raven_skull-12-25-v3.pwmb, raven_skull_19_12.pwmb
- xy_stride: 4
- z_stride: 4
- bin_mode: index_strict
- threshold: 1

## Aggregate timings (wall ms)

| backend | parse | contours_wall | triangulation_wall | buffers | total_wall |
|---|---:|---:|---:|---:|---:|
| python | 3.025 | 74834.310 | 46942.439 | 4204.473 | 125984.247 |
| cpp_native | 3.547 | 35662.600 | 33818.396 | 3464.245 | 72948.788 |
| cpp_opencv | 3.149 | 33443.543 | 40770.743 | 3453.013 | 77670.448 |

## Aggregate timings (cumulative CPU ms)

| backend | decode_cpu | contours_cpu | triangulation_cpu | buffers | total_cpu |
|---|---:|---:|---:|---:|---:|
| python | 2093270.038 | 252070.534 | 1095210.993 | 4204.473 | 3444756.038 |
| cpp_native | 1060436.646 | 55102.093 | 632957.285 | 3464.245 | 1751960.269 |
| cpp_opencv | 996067.821 | 49472.757 | 819910.696 | 3453.013 | 1868904.287 |

## Speedups (wall)

- cpp_native_vs_python_total_x: 1.727x
- cpp_opencv_vs_python_total_x: 1.622x
- cpp_native_vs_opencv_total_x: 1.065x
- cpp_native_vs_opencv_contours_x: 0.898x
- cpp_native_vs_opencv_triangulation_x: 1.295x

## Speedups (cumulative CPU)

- cpp_native_vs_python_total_cpu_x: 1.966x
- cpp_opencv_vs_python_total_cpu_x: 1.843x
- cpp_native_vs_opencv_total_cpu_x: 1.067x

## Functional deltas vs python

| file | native mesh Δmm2 | opencv mesh Δmm2 | native tri Δ | opencv tri Δ |
|---|---:|---:|---:|---:|
| cube.pwmb | 0.000000 | 0.000000 | 0 | 0 |
| raven_skull-12-25-v3.pwmb | 0.000000 | 0.000001 | 0 | 820 |
| raven_skull_19_12.pwmb | 0.000000 | -105.953284 | 0 | 5502 |

## Decision

- Default recommended: **native**
- Reason: best parity vs python and best overall runtime on measured corpus.
