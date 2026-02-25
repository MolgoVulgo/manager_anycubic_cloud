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
| python | 15748.559 | 57322.977 | 54883.625 | 0.004 | 127955.165 |
| cpp_native | 12669.262 | 4910.567 | 26823.838 | 4341.874 | 48745.541 |
| cpp_opencv | 12561.101 | 5064.046 | 32794.720 | 3944.575 | 54364.442 |

## Speedups

- cpp_native_vs_python_total_x: 2.625x
- cpp_opencv_vs_python_total_x: 2.354x
- cpp_native_vs_opencv_total_x: 1.115x
- cpp_native_vs_opencv_contours_x: 1.031x
- cpp_native_vs_opencv_triangulation_x: 1.223x

## Functional deltas vs python

| file | native mesh Δmm2 | opencv mesh Δmm2 | native tri Δ | opencv tri Δ |
|---|---:|---:|---:|---:|
| cube.pwmb | 0.000507 | 0.000507 | 0 | 0 |
| raven_skull-12-25-v3.pwmb | 0.006753 | 0.006753 | 0 | 1238 |
| raven_skull_19_12.pwmb | -0.002629 | -39.309117 | 0 | 4798 |

## Decision

- Default recommended: **native**
- Reason: best parity vs python and best overall runtime on measured corpus.
