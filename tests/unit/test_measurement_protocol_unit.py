from __future__ import annotations

from render3d_core.measurement_protocol import (
    PerfHotspotStats,
    PidstatStats,
    ThreadActivityStats,
    VmstatStats,
    diagnose_phase_bottleneck,
    evaluate_measurement_gate,
    parse_perf_top_output,
    parse_ps_threads_output,
    parse_pidstat_output,
    parse_vmstat_output,
)


def test_parse_vmstat_output_extracts_swap_metrics() -> None:
    raw = """\
procs -----------memory---------- ---swap-- -----io---- -system-- -------cpu-------
 r  b   swpd   free   buff  cache   si   so    bi    bo   in   cs us sy id wa st gu
 2  0 11784988 19167860 34388 2010692 67 130 2215   728 35543  16  7  1 92  0  0  0
 2  0 11784968 19112276 34396 2011296 4   0   388   144 86692 153128 12 3 85 0 0  0
 6  0 11784840 19236212 34396 2013228 64  0  1988     0 96327 177350 13 3 84 0 0  0
"""
    parsed = parse_vmstat_output(raw)
    assert parsed.samples == 3
    assert parsed.max_si == 67.0
    assert parsed.max_so == 130.0
    assert parsed.avg_si > 0.0
    assert parsed.avg_so > 0.0
    assert parsed.avg_id == 87.0
    assert parsed.min_id == 84.0


def test_parse_pidstat_output_extracts_average_sections() -> None:
    raw = """\
Linux 6.18.9-arch1-2 (host)  02/26/26    _x86_64_    (32 CPU)

16:48:19      UID       PID    %usr %system  %guest   %wait    %CPU   CPU  Command
16:48:20     1000    660473  144.00   26.00    0.00    0.00  170.00    24  python

16:48:19      UID       PID  minflt/s  majflt/s     VSZ     RSS   %MEM  Command
16:48:20     1000    660473  13227.00      3.00 5454060 2760604   8.43  python

Average:      UID       PID    %usr %system  %guest   %wait    %CPU   CPU  Command
Average:     1000    660473  139.33   23.67    0.00    0.00  163.00     -  python

Average:      UID       PID  minflt/s  majflt/s     VSZ     RSS   %MEM  Command
Average:     1000    660473   9961.33      2.00 5473857 2781479   8.49  python
"""
    parsed = parse_pidstat_output(raw)
    assert parsed.avg_usr == 139.33
    assert parsed.avg_system == 23.67
    assert parsed.avg_cpu == 163.0
    assert parsed.avg_minflt_s == 9961.33
    assert parsed.avg_majflt_s == 2.0
    assert parsed.avg_rss_kb == 2781479
    assert parsed.avg_mem_percent == 8.49


def test_evaluate_measurement_gate_passes_when_thresholds_are_respected() -> None:
    gate = evaluate_measurement_gate(
        VmstatStats(samples=3, max_si=0.0, max_so=0.0, avg_si=0.0, avg_so=0.0),
        PidstatStats(avg_majflt_s=0.0),
        max_si=0.0,
        max_so=0.0,
        max_majflt_s=0.0,
    )
    assert gate["pass"] is True
    assert gate["reasons"] == []


def test_evaluate_measurement_gate_fails_on_swap_and_faults() -> None:
    gate = evaluate_measurement_gate(
        VmstatStats(samples=3, max_si=2.0, max_so=5.0, avg_si=1.0, avg_so=2.0),
        PidstatStats(avg_majflt_s=1.0),
        max_si=0.0,
        max_so=0.0,
        max_majflt_s=0.0,
    )
    assert gate["pass"] is False
    assert any("vmstat_max_si" in reason for reason in gate["reasons"])
    assert any("vmstat_max_so" in reason for reason in gate["reasons"])
    assert any("pidstat_avg_majflt_s" in reason for reason in gate["reasons"])


def test_parse_ps_threads_output_extracts_activity() -> None:
    raw = """\
    PID     TID PSR %CPU COMMAND
 660473  660473  24  224 python
 660473  660474  10   12 python
 660473  660475  11    1 python
"""
    parsed = parse_ps_threads_output(raw)
    assert parsed.samples == 3
    assert parsed.hot_threads == 2
    assert parsed.very_hot_threads == 1
    assert parsed.max_thread_pcpu == 224.0
    assert parsed.sum_thread_pcpu == 237.0
    assert parsed.dominance_ratio is not None and parsed.dominance_ratio > 0.9


def test_parse_perf_top_output_extracts_python_hotspots() -> None:
    out = """\
  39.20%  python  libpython3.14.so  [.] PyEval_EvalFrameDefault
  11.00%  python  libpython3.14.so  [.] take_gil
"""
    parsed = parse_perf_top_output(out, "")
    assert parsed.available is True
    assert parsed.restricted is False
    assert parsed.py_hot_hits >= 2


def test_diagnose_phase_bottleneck_prefers_memory_when_gate_signals_swap() -> None:
    gate = {
        "pass": False,
        "reasons": ["vmstat_max_si=60.000>0.000", "vmstat_max_so=105.000>0.000"],
    }
    diagnosis = diagnose_phase_bottleneck(
        gate=gate,
        vmstat_stats=VmstatStats(samples=3, max_si=60.0, max_so=105.0, avg_si=10.0, avg_so=20.0),
        pidstat_stats=PidstatStats(avg_cpu=150.0, avg_majflt_s=0.0),
        thread_stats=ThreadActivityStats(samples=2, hot_threads=1, max_thread_pcpu=140.0, sum_thread_pcpu=150.0),
        perf_stats=PerfHotspotStats(available=False, restricted=True),
        workers_hint=32,
    )
    assert diagnosis["category"] == "memory_pressure"
    assert diagnosis["confidence"] > 0.0
