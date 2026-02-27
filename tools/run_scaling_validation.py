#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
import subprocess
import sys
from typing import Any


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _parse_workers_list(raw: str) -> list[int]:
    values: list[int] = []
    for part in str(raw).split(","):
        token = part.strip()
        if not token:
            continue
        try:
            parsed = int(token)
        except ValueError:
            continue
        if parsed > 0:
            values.append(parsed)
    unique = sorted(set(values))
    if not unique:
        raise ValueError("workers list is empty")
    return unique


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return float(sum(values)) / float(len(values))


def _std(values: list[float]) -> float | None:
    if len(values) <= 1:
        return 0.0 if values else None
    avg = _mean(values)
    if avg is None:
        return None
    variance = sum((float(value) - avg) ** 2 for value in values) / float(len(values))
    return math.sqrt(variance)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_row_from_measure_report(report: dict[str, Any], *, workers: int) -> dict[str, Any]:
    comparable_indices = set(int(x) for x in list(report.get("comparable_run_indices", [])))
    runs = list(report.get("runs", []))
    selected_runs = [run for run in runs if int(run.get("run_index", 0)) in comparable_indices]

    native_wall_values: list[float] = []
    opencv_wall_values: list[float] = []
    native_cpu_values: list[float] = []
    opencv_cpu_values: list[float] = []
    process_cpu_values: list[float] = []
    idle_values: list[float] = []
    si_values: list[float] = []
    so_values: list[float] = []
    majflt_values: list[float] = []

    for run in selected_runs:
        summary = dict(run.get("summary", {}))
        resource = dict(run.get("resource_summary", {}))

        n_wall = summary.get("cpp_native_total_wall_ms")
        o_wall = summary.get("cpp_opencv_total_wall_ms")
        n_cpu = summary.get("cpp_native_total_cpu_ms")
        o_cpu = summary.get("cpp_opencv_total_cpu_ms")
        process_cpu = resource.get("avg_process_cpu_percent")
        idle = resource.get("avg_machine_idle_percent")
        max_si = resource.get("max_vmstat_si")
        max_so = resource.get("max_vmstat_so")
        avg_majflt = resource.get("avg_pidstat_majflt_s")

        if isinstance(n_wall, int | float):
            native_wall_values.append(float(n_wall))
        if isinstance(o_wall, int | float):
            opencv_wall_values.append(float(o_wall))
        if isinstance(n_cpu, int | float):
            native_cpu_values.append(float(n_cpu))
        if isinstance(o_cpu, int | float):
            opencv_cpu_values.append(float(o_cpu))
        if isinstance(process_cpu, int | float):
            process_cpu_values.append(float(process_cpu))
        if isinstance(idle, int | float):
            idle_values.append(float(idle))
        if isinstance(max_si, int | float):
            si_values.append(float(max_si))
        if isinstance(max_so, int | float):
            so_values.append(float(max_so))
        if isinstance(avg_majflt, int | float):
            majflt_values.append(float(avg_majflt))

    native_wall_mean = _mean(native_wall_values)
    opencv_wall_mean = _mean(opencv_wall_values)
    best_backend = None
    best_wall_mean = None
    if native_wall_mean is not None and opencv_wall_mean is not None:
        if native_wall_mean <= opencv_wall_mean:
            best_backend = "cpp_native"
            best_wall_mean = native_wall_mean
        else:
            best_backend = "cpp_opencv"
            best_wall_mean = opencv_wall_mean

    return {
        "workers": int(workers),
        "runs_total": len(runs),
        "runs_comparable": len(selected_runs),
        "native_wall_ms_mean": native_wall_mean,
        "native_wall_ms_std": _std(native_wall_values),
        "opencv_wall_ms_mean": opencv_wall_mean,
        "opencv_wall_ms_std": _std(opencv_wall_values),
        "native_cpu_ms_mean": _mean(native_cpu_values),
        "opencv_cpu_ms_mean": _mean(opencv_cpu_values),
        "process_cpu_percent_mean": _mean(process_cpu_values),
        "process_cpu_percent_std": _std(process_cpu_values),
        "idle_percent_mean": _mean(idle_values),
        "idle_percent_std": _std(idle_values),
        "max_si_mean": _mean(si_values),
        "max_so_mean": _mean(so_values),
        "avg_majflt_s_mean": _mean(majflt_values),
        "best_backend_by_wall": best_backend,
        "best_wall_ms_mean": best_wall_mean,
        "measure_report_path": report.get("report_json"),
    }


def _trend_nonincreasing(values: list[float]) -> bool:
    for idx in range(1, len(values)):
        if values[idx] > values[idx - 1]:
            return False
    return True


def _trend_nondecreasing(values: list[float]) -> bool:
    for idx in range(1, len(values)):
        if values[idx] < values[idx - 1]:
            return False
    return True


def _build_validation(row_items: list[dict[str, Any]], *, gate_max_si: float, gate_max_so: float, gate_max_majflt_s: float) -> dict[str, Any]:
    comparable_rows = [row for row in row_items if int(row.get("runs_comparable", 0)) > 0]
    comparable_rows = sorted(comparable_rows, key=lambda item: int(item.get("workers", 0)))

    best_wall_values = [float(row["best_wall_ms_mean"]) for row in comparable_rows if isinstance(row.get("best_wall_ms_mean"), int | float)]
    process_cpu_values = [float(row["process_cpu_percent_mean"]) for row in comparable_rows if isinstance(row.get("process_cpu_percent_mean"), int | float)]
    idle_values = [float(row["idle_percent_mean"]) for row in comparable_rows if isinstance(row.get("idle_percent_mean"), int | float)]

    wall_nonincreasing = len(best_wall_values) >= 2 and _trend_nonincreasing(best_wall_values)
    cpu_nondecreasing = len(process_cpu_values) >= 2 and _trend_nondecreasing(process_cpu_values)
    idle_nonincreasing = len(idle_values) >= 2 and _trend_nonincreasing(idle_values)

    paging_rows_ok = True
    paging_reasons: list[str] = []
    for row in comparable_rows:
        workers = int(row.get("workers", 0))
        max_si = row.get("max_si_mean")
        max_so = row.get("max_so_mean")
        avg_majflt = row.get("avg_majflt_s_mean")
        if isinstance(max_si, int | float) and float(max_si) > float(gate_max_si):
            paging_rows_ok = False
            paging_reasons.append(f"w{workers}: max_si_mean={float(max_si):.3f}>{float(gate_max_si):.3f}")
        if isinstance(max_so, int | float) and float(max_so) > float(gate_max_so):
            paging_rows_ok = False
            paging_reasons.append(f"w{workers}: max_so_mean={float(max_so):.3f}>{float(gate_max_so):.3f}")
        if isinstance(avg_majflt, int | float) and float(avg_majflt) > float(gate_max_majflt_s):
            paging_rows_ok = False
            paging_reasons.append(
                f"w{workers}: avg_majflt_s_mean={float(avg_majflt):.3f}>{float(gate_max_majflt_s):.3f}"
            )

    overall_pass = wall_nonincreasing and cpu_nondecreasing and idle_nonincreasing and paging_rows_ok
    return {
        "comparable_workers": [int(row.get("workers", 0)) for row in comparable_rows],
        "wall_nonincreasing": wall_nonincreasing,
        "cpu_nondecreasing": cpu_nondecreasing,
        "idle_nonincreasing": idle_nonincreasing,
        "paging_ok": paging_rows_ok,
        "paging_reasons": paging_reasons,
        "overall_pass": overall_pass,
    }


def _write_markdown(summary: dict[str, Any], path: Path) -> None:
    rows = list(summary.get("rows", []))
    validation = dict(summary.get("validation", {}))
    lines: list[str] = []
    lines.append("# Scaling Validation Summary")
    lines.append("")
    lines.append(f"- generated_at: {summary.get('generated_at')}")
    lines.append(f"- parallel_policy: {summary.get('parallel_policy')}")
    lines.append(f"- workers_list: {summary.get('workers_list')}")
    lines.append(f"- runs_per_worker: {summary.get('runs_per_worker')}")
    lines.append("")
    lines.append("## Aggregates")
    lines.append("")
    lines.append(
        "| workers | comparable runs | best backend | best wall mean (ms) | cpu% mean | idle% mean | max si/so mean | majflt/s mean |"
    )
    lines.append("|---:|---:|:---|---:|---:|---:|---:|---:|")
    for row in rows:
        si = row.get("max_si_mean")
        so = row.get("max_so_mean")
        si_so = "-"
        if isinstance(si, int | float) and isinstance(so, int | float):
            si_so = f"{float(si):.3f}/{float(so):.3f}"
        best_wall = row.get("best_wall_ms_mean")
        cpu = row.get("process_cpu_percent_mean")
        idle = row.get("idle_percent_mean")
        majflt = row.get("avg_majflt_s_mean")
        best_backend = row.get("best_backend_by_wall") or "-"
        wall_cell = f"{float(best_wall):.3f}" if isinstance(best_wall, int | float) else "-"
        cpu_cell = f"{float(cpu):.3f}" if isinstance(cpu, int | float) else "-"
        idle_cell = f"{float(idle):.3f}" if isinstance(idle, int | float) else "-"
        majflt_cell = f"{float(majflt):.3f}" if isinstance(majflt, int | float) else "-"
        lines.append(
            "| "
            + f"{row.get('workers')} | {row.get('runs_comparable')} | {best_backend} | {wall_cell} | "
            + f"{cpu_cell} | {idle_cell} | {si_so} | {majflt_cell} |"
        )
    lines.append("")
    lines.append("## Validation")
    lines.append("")
    lines.append(f"- comparable_workers: {validation.get('comparable_workers', [])}")
    lines.append(f"- wall_nonincreasing: {validation.get('wall_nonincreasing')}")
    lines.append(f"- cpu_nondecreasing: {validation.get('cpu_nondecreasing')}")
    lines.append(f"- idle_nonincreasing: {validation.get('idle_nonincreasing')}")
    lines.append(f"- paging_ok: {validation.get('paging_ok')}")
    lines.append(f"- overall_pass: {validation.get('overall_pass')}")
    reasons = list(validation.get("paging_reasons", []))
    if reasons:
        lines.append("- paging_reasons:")
        for reason in reasons:
            lines.append(f"  - {reason}")
    lines.append("")
    lines.append("## Measure Reports")
    lines.append("")
    for row in rows:
        lines.append(f"- workers={row.get('workers')}: {row.get('measure_report_path')}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run final scaling validation matrix over workers configurations.")
    parser.add_argument("--campaign-script", default="tools/run_campaign_z1_xy1.sh", help="Campaign script path.")
    parser.add_argument("--corpus-dir", default="pwmb_files", help="PWMB corpus path.")
    parser.add_argument("--reports-root", default="reports/scaling_validation", help="Output root directory.")
    parser.add_argument("--workers-list", default="1,4,16,32", help="Comma separated workers list.")
    parser.add_argument("--runs-per-worker", type=int, default=3, help="Number of runs per workers setting.")
    parser.add_argument(
        "--parallel-policy",
        default="python_fanout",
        choices=["python_fanout", "cpp_internal", "auto"],
        help="Parallel policy forwarded to campaign runs.",
    )
    parser.add_argument("--sample-delay-s", type=float, default=5.0, help="Phase snapshot delay.")
    parser.add_argument("--vmstat-seconds", type=int, default=3, help="vmstat window seconds.")
    parser.add_argument("--pidstat-seconds", type=int, default=3, help="pidstat window seconds.")
    parser.add_argument("--perf-seconds", type=int, default=3, help="perf top timeout seconds.")
    parser.add_argument("--phase-detect-timeout-s", type=float, default=180.0, help="Phase detection timeout.")
    parser.add_argument("--gate-max-si", type=float, default=0.0, help="Gate threshold for vmstat si.")
    parser.add_argument("--gate-max-so", type=float, default=0.0, help="Gate threshold for vmstat so.")
    parser.add_argument("--gate-max-majflt-s", type=float, default=0.0, help="Gate threshold for avg majflt/s.")
    parser.add_argument("--strict-measure-gates", action="store_true", help="Forward strict mode to measure runs.")
    parser.add_argument("--output-prefix", type=Path, default=None, help="Output prefix for matrix summary.")
    args = parser.parse_args()

    workers_list = _parse_workers_list(args.workers_list)
    runs_per_worker = max(1, int(args.runs_per_worker))
    repo_root = Path(__file__).resolve().parents[1]
    reports_root = Path(str(args.reports_root)).expanduser().resolve()
    reports_root.mkdir(parents=True, exist_ok=True)

    if args.output_prefix is None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_prefix = reports_root / f"scaling_validation_{stamp}"
    else:
        output_prefix = Path(args.output_prefix).expanduser().resolve()
        output_prefix.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    run_commands: list[dict[str, Any]] = []
    for workers in workers_list:
        worker_root = reports_root / f"workers_{workers:02d}"
        worker_runs_root = worker_root / "runs"
        worker_runs_root.mkdir(parents=True, exist_ok=True)
        worker_output_prefix = worker_root / "measurement_protocol"
        cmd = [
            sys.executable,
            "tools/run_campaign_measure_protocol.py",
            "--campaign-script",
            str(Path(str(args.campaign_script)).resolve()),
            "--corpus-dir",
            str(Path(str(args.corpus_dir)).resolve()),
            "--reports-root",
            str(worker_runs_root),
            "--output-prefix",
            str(worker_output_prefix),
            "--runs",
            str(runs_per_worker),
            "--workers",
            str(int(workers)),
            "--parallel-policy",
            str(args.parallel_policy),
            "--sample-delay-s",
            str(float(args.sample_delay_s)),
            "--vmstat-seconds",
            str(int(args.vmstat_seconds)),
            "--pidstat-seconds",
            str(int(args.pidstat_seconds)),
            "--perf-seconds",
            str(int(args.perf_seconds)),
            "--phase-detect-timeout-s",
            str(float(args.phase_detect_timeout_s)),
            "--gate-max-si",
            str(float(args.gate_max_si)),
            "--gate-max-so",
            str(float(args.gate_max_so)),
            "--gate-max-majflt-s",
            str(float(args.gate_max_majflt_s)),
        ]
        if bool(args.strict_measure_gates):
            cmd.append("--strict-gates")

        completed = subprocess.run(cmd, cwd=str(repo_root), check=False, capture_output=True, text=True)
        run_commands.append(
            {
                "workers": int(workers),
                "cmd": cmd,
                "returncode": int(completed.returncode),
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
        )

        report_json_path = worker_output_prefix.with_suffix(".json")
        if not report_json_path.exists():
            rows.append(
                {
                    "workers": int(workers),
                    "runs_total": runs_per_worker,
                    "runs_comparable": 0,
                    "best_backend_by_wall": None,
                    "best_wall_ms_mean": None,
                    "process_cpu_percent_mean": None,
                    "idle_percent_mean": None,
                    "max_si_mean": None,
                    "max_so_mean": None,
                    "avg_majflt_s_mean": None,
                    "measure_report_path": None,
                    "error": "measure_report_missing",
                }
            )
            continue

        measure_report = _load_json(report_json_path)
        measure_report["report_json"] = str(report_json_path)
        rows.append(_extract_row_from_measure_report(measure_report, workers=int(workers)))

    rows = sorted(rows, key=lambda item: int(item.get("workers", 0)))
    validation = _build_validation(
        rows,
        gate_max_si=float(args.gate_max_si),
        gate_max_so=float(args.gate_max_so),
        gate_max_majflt_s=float(args.gate_max_majflt_s),
    )
    summary = {
        "generated_at": _now_iso(),
        "campaign_script": str(Path(str(args.campaign_script)).resolve()),
        "corpus_dir": str(Path(str(args.corpus_dir)).resolve()),
        "reports_root": str(reports_root),
        "parallel_policy": str(args.parallel_policy),
        "workers_list": workers_list,
        "runs_per_worker": runs_per_worker,
        "gate_thresholds": {
            "max_si": float(args.gate_max_si),
            "max_so": float(args.gate_max_so),
            "max_majflt_s": float(args.gate_max_majflt_s),
        },
        "rows": rows,
        "validation": validation,
        "run_commands": run_commands,
    }

    output_json = output_prefix.with_suffix(".json")
    output_md = output_prefix.with_suffix(".md")
    output_json.write_text(json.dumps(summary, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    _write_markdown(summary, output_md)
    print(json.dumps({"summary_json": str(output_json), "summary_md": str(output_md)}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
