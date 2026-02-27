# Scaling Validation Summary

- generated_at: 2026-02-26T22:42:49+01:00
- parallel_policy: python_fanout
- workers_list: [4, 16, 32]
- runs_per_worker: 1

## Aggregates

| workers | comparable runs | best backend | best wall mean (ms) | cpu% mean | idle% mean | max si/so mean | majflt/s mean |
|---:|---:|:---|---:|---:|---:|---:|---:|
| 4 | 0 | - | - | - | - | - | - |
| 16 | 0 | - | - | - | - | - | - |
| 32 | 0 | - | - | - | - | - | - |

## Validation

- comparable_workers: []
- wall_nonincreasing: False
- cpu_nondecreasing: False
- idle_nonincreasing: False
- paging_ok: True
- overall_pass: False

## Measure Reports

- workers=4: /home/kaj/Develop/python/manager_anycubic_cloud/reports/scaling_validation/accelerated_cube_20260226_224124/workers_04/measurement_protocol.json
- workers=16: /home/kaj/Develop/python/manager_anycubic_cloud/reports/scaling_validation/accelerated_cube_20260226_224124/workers_16/measurement_protocol.json
- workers=32: /home/kaj/Develop/python/manager_anycubic_cloud/reports/scaling_validation/accelerated_cube_20260226_224124/workers_32/measurement_protocol.json
