# Render3D Campaign Summary

## Protocol

- files: cube.pwmb, raven_skull-12-25-v3.pwmb, raven_skull_19_12.pwmb
- xy_stride: 4
- z_stride: 4
- bin_mode: index_strict
- threshold: 1

## Aggregate timings (ms)

| backend | decode | contours | triangulation | total |
|---|---:|---:|---:|---:|
| python | 15748.559 | 57322.977 | 54883.625 | 127955.161 |
| cpp_native | 16511.030 | 8786.636 | 31951.332 | 57248.998 |
| cpp_opencv | 16411.908 | 6634.616 | 39525.197 | 62571.721 |

## Speedups

- cpp_native_vs_python_total_x: 2.235x
- cpp_opencv_vs_python_total_x: 2.045x
- cpp_native_vs_opencv_total_x: 1.093x
- cpp_native_vs_opencv_contours_x: 0.755x
- cpp_native_vs_opencv_triangulation_x: 1.237x

## Functional deltas vs python

| file | native mesh Δmm2 | opencv mesh Δmm2 | native tri Δ | opencv tri Δ |
|---|---:|---:|---:|---:|
| cube.pwmb | 0.000000 | 0.000000 | 0 | 0 |
| raven_skull-12-25-v3.pwmb | 0.000000 | 0.000000 | 0 | 1238 |
| raven_skull_19_12.pwmb | 0.000000 | -39.306489 | 0 | 4798 |

## Decision

- Default recommended: **native**
- Reason: best parity vs python and best overall runtime on measured corpus.
