# OpenCV Approx Campaign Summary

## Aggregate timings (ms)

| backend | decode | contours | triangulation | buffers | total |
|---|---:|---:|---:|---:|---:|
| python | 12860.423 | 39821.191 | 40004.858 | 0.002 | 92686.474 |
| cpp_native | 12824.472 | 5019.381 | 38644.202 | 0.002 | 56488.057 |
| cpp_opencv(simple) | 12850.080 | 5189.312 | 45536.105 | 0.003 | 63575.500 |
| cpp_opencv(tc89_l1) | 12758.290 | 36528.566 | 23669.073 | 3546.786 | 76502.715 |
| cpp_opencv(tc89_kcos) | 12453.341 | 36040.055 | 19040.327 | 3344.033 | 70877.756 |

## Parity vs python

| opencv approx | files | mesh_area_abs_sum | contour_area_abs_sum | tri_abs_sum | score |
|---|---:|---:|---:|---:|---:|
| simple | 3 | 39.306489 | 0.000000 | 6036 | 6429.064890 |
| tc89_l1 | 3 | 50912.844984 | 51815.315574 | 132884 | 1056534.974432 |
| tc89_kcos | 3 | 41087.472966 | 42448.518599 | 193325 | 943787.878452 |

## Recommendation

- Recommended OpenCV approx: **simple**
- Decision basis: `min(delta_vs_python.score), tie-break on total_ms`
