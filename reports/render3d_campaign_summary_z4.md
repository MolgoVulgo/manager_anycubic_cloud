# Render3D Campaign Summary (z_stride=4)

## Aggregate timings (ms)

| backend | decode | contours | triangulation | total |
|---|---:|---:|---:|---:|
| python | 12860.423 | 39821.191 | 40004.858 | 92686.472 |
| cpp_native | 12824.472 | 5019.381 | 38644.202 | 56488.055 |
| cpp_opencv | 12850.080 | 5189.312 | 45536.105 | 63575.497 |

## Speedups

- cpp_native_vs_python_total_x: 1.641x
- cpp_opencv_vs_python_total_x: 1.458x
- cpp_native_vs_opencv_total_x: 1.125x
- cpp_native_vs_opencv_contours_x: 1.034x
- cpp_native_vs_opencv_triangulation_x: 1.178x

## Functional deltas vs python

| file | native mesh Δmm2 | opencv mesh Δmm2 | native tri Δ | opencv tri Δ |
|---|---:|---:|---:|---:|
| cube.pwmb | 0.000000 | 0.000000 | 0 | 0 |
| raven_skull-12-25-v3.pwmb | 0.000000 | 0.000000 | 0 | 1238 |
| raven_skull_19_12.pwmb | 0.000000 | -39.306489 | 0 | 4798 |

## Decision

- Default recommended: **native**
- Reason: exact parity vs python on this corpus; opencv shows non-zero mesh/triangle drift and slower total time.
