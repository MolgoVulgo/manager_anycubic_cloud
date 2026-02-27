# Measurement Protocol Report

- started_at: 2026-02-26T22:41:52+01:00
- ended_at: 2026-02-26T22:42:20+01:00
- runs_requested: 1
- strict_gates: False

## Preflight

- tools: {'taskset': True, 'ps': True, 'vmstat': True, 'pidstat': True, 'perf': True}
- perf_sysctl: {'perf_event_paranoid': 2, 'kptr_restrict': 0}

## Runs

| run | rc | gate | diag | cpu% | idle% | max si/so | native wall ms | opencv wall ms |
|---:|---:|:---:|:---|---:|---:|---:|---:|---:|
| 1 | 0 | FAIL | memory_pressure | 295.610 | 92.000 | 48.000/90.000 | 12706.864 | 14405.071000000002 |

## Gate Failures

- run 1:
  - cpp_native:vmstat_max_si=48.000>0.000,vmstat_max_so=90.000>0.000
  - cpp_opencv:vmstat_max_si=48.000>0.000,vmstat_max_so=90.000>0.000

## Comparable Runs

- comparable_run_indices: []
- comparable_runs_count: 0
- diagnostic_comparable_run_indices: [1]
- diagnostic_comparable_runs_count: 1

## Phase 2 Diagnostic

- run 1: category=memory_pressure (confidence=1.0, pass=True)
  - cpp_native: memory_pressure (confidence=1.0) evidence=['vmstat_max_si=48.000>0.000', 'vmstat_max_so=90.000>0.000', 'low_process_cpu=178.220', 'hot_threads=1', 'dominance_ratio=1.000']
  - cpp_opencv: memory_pressure (confidence=1.0) evidence=['vmstat_max_si=48.000>0.000', 'vmstat_max_so=90.000>0.000', 'hot_threads=1', 'dominance_ratio=1.000']

## Output Paths

- report_json: /home/kaj/Develop/python/manager_anycubic_cloud/reports/scaling_validation/accelerated_cube_20260226_224124/workers_16/measurement_protocol.json
- report_md: /home/kaj/Develop/python/manager_anycubic_cloud/reports/scaling_validation/accelerated_cube_20260226_224124/workers_16/measurement_protocol.md
