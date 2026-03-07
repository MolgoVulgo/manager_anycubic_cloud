#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from render3d_core.measurement_protocol import (
    diagnose_phase_bottleneck,
    evaluate_measurement_gate,
    parse_pidstat_output,
    parse_perf_top_output,
    parse_ps_threads_output,
    parse_vmstat_output,
)


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _clip(raw: str, *, limit: int = 16_000) -> str:
    text = str(raw or "")
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[truncated {len(text) - limit} chars]"


def _run_capture(cmd: list[str], *, timeout_s: float | None = None) -> dict[str, Any]:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        return {
            "cmd": cmd,
            "returncode": int(completed.returncode),
            "stdout": _clip(completed.stdout),
            "stderr": _clip(completed.stderr),
            "elapsed_s": round(time.monotonic() - started, 3),
            "timed_out": False,
        }
    except OSError as exc:
        return {
            "cmd": cmd,
            "returncode": None,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
            "elapsed_s": round(time.monotonic() - started, 3),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else str(exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else str(exc.stderr or "")
        return {
            "cmd": cmd,
            "returncode": None,
            "stdout": _clip(stdout),
            "stderr": _clip(stderr),
            "elapsed_s": round(time.monotonic() - started, 3),
            "timed_out": True,
        }


def _filter_parallel_env() -> dict[str, str]:
    prefixes = ("OMP", "OPENBLAS", "MKL", "NUMEXPR", "TBB", "OPENCV", "KMP", "GOMP")
    selected: dict[str, str] = {}
    for key in sorted(os.environ):
        if key.startswith(prefixes) or key.startswith("RENDER3D_"):
            selected[key] = str(os.environ[key])
    return selected


def _read_proc_status_subset(pid: int) -> dict[str, str]:
    path = Path(f"/proc/{pid}/status")
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            if key in {"Threads", "Cpus_allowed_list"}:
                out[key] = value.strip()
    except OSError:
        return {}
    return out


def _read_perf_sysctl() -> dict[str, Any]:
    out: dict[str, Any] = {}
    paranoid = Path("/proc/sys/kernel/perf_event_paranoid")
    kptr = Path("/proc/sys/kernel/kptr_restrict")
    try:
        if paranoid.exists():
            out["perf_event_paranoid"] = int(paranoid.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        out["perf_event_paranoid"] = None
    try:
        if kptr.exists():
            out["kptr_restrict"] = int(kptr.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        out["kptr_restrict"] = None
    return out


def _read_cv2_probe() -> dict[str, Any]:
    probe = _run_capture(
        [
            sys.executable,
            "-c",
            "import cv2; print('opencv threads:', cv2.getNumThreads()); print('opencv cpus:', cv2.getNumberOfCPUs())",
        ]
    )
    payload: dict[str, Any] = {
        "ok": probe["returncode"] == 0,
        "stdout": probe["stdout"],
        "stderr": probe["stderr"],
    }
    if probe["returncode"] != 0:
        return payload
    threads: int | None = None
    cpus: int | None = None
    for line in str(probe["stdout"]).splitlines():
        text = line.strip().lower()
        if text.startswith("opencv threads:"):
            try:
                threads = int(text.split(":", 1)[1].strip())
            except ValueError:
                threads = None
        if text.startswith("opencv cpus:"):
            try:
                cpus = int(text.split(":", 1)[1].strip())
            except ValueError:
                cpus = None
    payload["threads"] = threads
    payload["cpus"] = cpus
    return payload


def _read_native_module_info() -> dict[str, Any]:
    probe = _run_capture(
        [
            sys.executable,
            "-c",
            (
                "import pwmb_geom; print('pwmb_geom_file=' + str(pwmb_geom.__file__)); "
                "import pwmb_geom._pwmb_geom as m; print('_pwmb_geom_file=' + str(m.__file__))"
            ),
        ]
    )
    payload: dict[str, Any] = {
        "probe": probe,
        "module_path": None,
        "ldd_filtered": [],
    }
    if probe.get("returncode") != 0:
        return payload
    module_path: str | None = None
    for line in str(probe.get("stdout", "")).splitlines():
        text = line.strip()
        if text.startswith("_pwmb_geom_file="):
            module_path = text.split("=", 1)[1].strip()
            break
    payload["module_path"] = module_path
    if not module_path:
        return payload

    ldd_raw = _run_capture(["ldd", module_path])
    filtered: list[str] = []
    pattern = re.compile(r"gomp|omp|tbb|pthread", re.IGNORECASE)
    for line in str(ldd_raw.get("stdout", "")).splitlines():
        if pattern.search(line):
            filtered.append(line.strip())
    payload["ldd"] = ldd_raw
    payload["ldd_filtered"] = filtered
    return payload


def _find_baseline_pid_by_output(output_path: Path) -> int | None:
    try:
        ps = subprocess.run(
            ["ps", "-eww", "-o", "pid=,args="],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    needle = str(output_path)
    if ps.returncode != 0:
        return None
    for line in str(ps.stdout).splitlines():
        raw = line.strip()
        if not raw:
            continue
        parts = raw.split(maxsplit=1)
        if len(parts) != 2:
            continue
        pid_raw, args = parts
        if "tools/render3d_baseline.py" not in args:
            continue
        if "--output" not in args:
            continue
        if needle not in args:
            continue
        try:
            return int(pid_raw)
        except ValueError:
            continue
    return None


def _collect_phase_snapshot(
    *,
    pid: int,
    vmstat_seconds: int,
    pidstat_seconds: int,
    perf_seconds: int,
    gate_max_si: float,
    gate_max_so: float,
    gate_max_majflt_s: float,
    workers_hint: int,
) -> dict[str, Any]:
    affinity = _run_capture(["taskset", "-pc", str(pid)])
    status = _read_proc_status_subset(pid)
    top_threads = _run_capture(["ps", "-L", "-p", str(pid), "-o", "pid,tid,psr,pcpu,comm", "--sort=-pcpu"])
    vmstat_raw = _run_capture(["vmstat", "1", str(max(1, int(vmstat_seconds)))])
    pidstat_raw = _run_capture(["pidstat", "-r", "-u", "-p", str(pid), "1", str(max(1, int(pidstat_seconds)))])
    perf_raw: dict[str, Any] | None = None
    if shutil.which("perf") is not None:
        perf_raw = _run_capture(["perf", "top", "-p", str(pid)], timeout_s=float(max(1, int(perf_seconds))))

    vmstat_stats = parse_vmstat_output(str(vmstat_raw.get("stdout", "")))
    pidstat_stats = parse_pidstat_output(str(pidstat_raw.get("stdout", "")))
    thread_stats = parse_ps_threads_output(str(top_threads.get("stdout", "")))
    perf_stats = parse_perf_top_output(
        str(dict(perf_raw or {}).get("stdout", "")),
        str(dict(perf_raw or {}).get("stderr", "")),
    )
    gate = evaluate_measurement_gate(
        vmstat_stats,
        pidstat_stats,
        max_si=float(gate_max_si),
        max_so=float(gate_max_so),
        max_majflt_s=float(gate_max_majflt_s),
    )
    diagnosis = diagnose_phase_bottleneck(
        gate=gate,
        vmstat_stats=vmstat_stats,
        pidstat_stats=pidstat_stats,
        thread_stats=thread_stats,
        perf_stats=perf_stats,
        workers_hint=max(1, int(workers_hint)),
    )

    top_text = str(top_threads.get("stdout", ""))
    top_lines = top_text.splitlines()
    top_threads["stdout"] = "\n".join(top_lines[:20])

    return {
        "captured_at": _now_iso(),
        "pid": int(pid),
        "affinity": affinity,
        "proc_status_subset": status,
        "top_threads": top_threads,
        "top_threads_parsed": thread_stats.as_dict(),
        "vmstat": {
            "raw": vmstat_raw,
            "parsed": vmstat_stats.as_dict(),
        },
        "pidstat": {
            "raw": pidstat_raw,
            "parsed": pidstat_stats.as_dict(),
        },
        "perf_top": perf_raw,
        "perf_top_parsed": perf_stats.as_dict(),
        "env_parallel": _filter_parallel_env(),
        "cv2_probe": _read_cv2_probe(),
        "native_module_info": _read_native_module_info(),
        "gate": gate,
        "diagnosis": diagnosis,
    }


def _summary_extract(summary_json: Path) -> dict[str, Any] | None:
    if not summary_json.exists():
        return None
    try:
        payload = json.loads(summary_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    aggregate = dict(payload.get("aggregate", {}))
    native = dict(aggregate.get("cpp_native", {}))
    opencv = dict(aggregate.get("cpp_opencv", {}))
    speedups = dict(payload.get("speedups", {}))
    reports_dir = summary_json.parent
    native_report = reports_dir / "render3d_campaign_cpp_native_z1_xy1.json"
    opencv_report = reports_dir / "render3d_campaign_cpp_opencv_z1_xy1.json"
    native_workers_effective = None
    opencv_workers_effective = None
    try:
        if native_report.exists():
            native_payload = json.loads(native_report.read_text(encoding="utf-8"))
            native_workers_effective = native_payload.get("workers_effective")
    except (OSError, json.JSONDecodeError):
        native_workers_effective = None
    try:
        if opencv_report.exists():
            opencv_payload = json.loads(opencv_report.read_text(encoding="utf-8"))
            opencv_workers_effective = opencv_payload.get("workers_effective")
    except (OSError, json.JSONDecodeError):
        opencv_workers_effective = None
    return {
        "summary_json": str(summary_json),
        "workers_effective": {
            "cpp_native": native_workers_effective,
            "cpp_opencv": opencv_workers_effective,
        },
        "cpp_native_total_wall_ms": native.get("total_wall_ms"),
        "cpp_opencv_total_wall_ms": opencv.get("total_wall_ms"),
        "cpp_native_total_cpu_ms": native.get("total_cpu_ms"),
        "cpp_opencv_total_cpu_ms": opencv.get("total_cpu_ms"),
        "cpp_native_contours_wall_ms_total": native.get("contours_wall_ms_total"),
        "cpp_opencv_contours_wall_ms_total": opencv.get("contours_wall_ms_total"),
        "cpp_native_triangulation_wall_ms_total": native.get("triangulation_wall_ms_total"),
        "cpp_opencv_triangulation_wall_ms_total": opencv.get("triangulation_wall_ms_total"),
        "speedups": speedups,
    }


def _consolidate_run_diagnosis(phases_payload: dict[str, Any]) -> dict[str, Any]:
    per_phase: dict[str, dict[str, Any]] = {}
    categories: list[str] = []
    confidences: list[float] = []
    evidence: list[str] = []

    for phase_name in ("cpp_native", "cpp_opencv"):
        phase = dict(phases_payload.get(phase_name, {}))
        diagnosis = dict(phase.get("diagnosis", {}))
        category = str(diagnosis.get("category", "inconclusive"))
        confidence = float(diagnosis.get("confidence", 0.0) or 0.0)
        phase_evidence = [str(item) for item in list(diagnosis.get("evidence", []))]
        per_phase[phase_name] = {
            "category": category,
            "confidence": confidence,
            "evidence": phase_evidence,
        }
        categories.append(category)
        confidences.append(confidence)
        for item in phase_evidence:
            evidence.append(f"{phase_name}:{item}")

    category = "inconclusive"
    if any(value == "memory_pressure" for value in categories):
        category = "memory_pressure"
    else:
        non_inconclusive = [value for value in categories if value != "inconclusive"]
        unique_non_inconclusive = sorted(set(non_inconclusive))
        if len(unique_non_inconclusive) == 1 and non_inconclusive:
            category = unique_non_inconclusive[0]
        elif len(unique_non_inconclusive) > 1:
            category = "mixed_signals"
        else:
            category = "inconclusive"

    avg_confidence = 0.0
    if confidences:
        avg_confidence = float(sum(confidences)) / float(len(confidences))
    diagnostic_gate_pass = category not in {"inconclusive", "mixed_signals"}
    return {
        "category": category,
        "confidence": round(avg_confidence, 3),
        "diagnostic_gate_pass": diagnostic_gate_pass,
        "per_phase": per_phase,
        "evidence": evidence[:32],
    }


def _extract_run_resource_summary(phases_payload: dict[str, Any]) -> dict[str, Any]:
    cpu_values: list[float] = []
    idle_values: list[float] = []
    si_values: list[float] = []
    so_values: list[float] = []
    majflt_values: list[float] = []

    for phase_name in ("cpp_native", "cpp_opencv"):
        phase = dict(phases_payload.get(phase_name, {}))
        pidstat = dict(phase.get("pidstat_parsed", {}))
        vmstat = dict(phase.get("vmstat_parsed", {}))
        avg_cpu = pidstat.get("avg_cpu")
        avg_majflt = pidstat.get("avg_majflt_s")
        avg_idle = vmstat.get("avg_id")
        max_si = vmstat.get("max_si")
        max_so = vmstat.get("max_so")

        if isinstance(avg_cpu, int | float):
            cpu_values.append(float(avg_cpu))
        if isinstance(avg_idle, int | float):
            idle_values.append(float(avg_idle))
        if isinstance(max_si, int | float):
            si_values.append(float(max_si))
        if isinstance(max_so, int | float):
            so_values.append(float(max_so))
        if isinstance(avg_majflt, int | float):
            majflt_values.append(float(avg_majflt))

    def _mean(values: list[float]) -> float | None:
        if not values:
            return None
        return float(sum(values)) / float(len(values))

    def _max(values: list[float]) -> float | None:
        if not values:
            return None
        return float(max(values))

    return {
        "avg_process_cpu_percent": _mean(cpu_values),
        "avg_machine_idle_percent": _mean(idle_values),
        "max_vmstat_si": _max(si_values),
        "max_vmstat_so": _max(so_values),
        "avg_pidstat_majflt_s": _mean(majflt_values),
    }


def _write_markdown(report: dict[str, Any], path: Path) -> None:
    lines: list[str] = []
    lines.append("# Measurement Protocol Report")
    lines.append("")
    lines.append(f"- started_at: {report.get('started_at')}")
    lines.append(f"- ended_at: {report.get('ended_at')}")
    lines.append(f"- runs_requested: {report.get('runs_requested')}")
    lines.append(f"- strict_gates: {report.get('strict_gates')}")
    lines.append("")
    lines.append("## Preflight")
    lines.append("")
    preflight = dict(report.get("preflight", {}))
    tools = dict(preflight.get("tools", {}))
    lines.append(f"- tools: {tools}")
    lines.append(f"- perf_sysctl: {preflight.get('perf_sysctl')}")
    lines.append("")
    lines.append("## Runs")
    lines.append("")
    lines.append("| run | rc | gate | diag | cpu% | idle% | max si/so | native wall ms | opencv wall ms |")
    lines.append("|---:|---:|:---:|:---|---:|---:|---:|---:|---:|")
    for run in report.get("runs", []):
        idx = int(run.get("run_index", 0))
        rc = run.get("campaign_returncode")
        gate = bool(run.get("gate_pass"))
        diagnosis = dict(run.get("diagnosis", {}))
        resource = dict(run.get("resource_summary", {}))
        summary = dict(run.get("summary", {}))
        cpu_text = resource.get("avg_process_cpu_percent")
        idle_text = resource.get("avg_machine_idle_percent")
        si_text = resource.get("max_vmstat_si")
        so_text = resource.get("max_vmstat_so")
        cpu_cell = f"{float(cpu_text):.3f}" if isinstance(cpu_text, int | float) else "-"
        idle_cell = f"{float(idle_text):.3f}" if isinstance(idle_text, int | float) else "-"
        si_so = "-"
        if isinstance(si_text, int | float) and isinstance(so_text, int | float):
            si_so = f"{float(si_text):.3f}/{float(so_text):.3f}"
        lines.append(
            "| "
            + f"{idx} | {rc} | {'PASS' if gate else 'FAIL'} | {diagnosis.get('category', '-')} | "
            + f"{cpu_cell} | {idle_cell} | {si_so} | "
            + f"{summary.get('cpp_native_total_wall_ms', '-')} | {summary.get('cpp_opencv_total_wall_ms', '-')} |"
        )
    lines.append("")
    lines.append("## Gate Failures")
    lines.append("")
    for run in report.get("runs", []):
        if bool(run.get("gate_pass")):
            continue
        idx = int(run.get("run_index", 0))
        lines.append(f"- run {idx}:")
        run_reasons = list(run.get("gate_reasons", []))
        if run_reasons:
            for reason in run_reasons:
                lines.append(f"  - {reason}")
    lines.append("")
    lines.append("## Comparable Runs")
    lines.append("")
    comparable = list(report.get("comparable_run_indices", []))
    lines.append(f"- comparable_run_indices: {comparable}")
    lines.append(f"- comparable_runs_count: {len(comparable)}")
    diag_comparable = list(report.get("diagnostic_comparable_run_indices", []))
    lines.append(f"- diagnostic_comparable_run_indices: {diag_comparable}")
    lines.append(f"- diagnostic_comparable_runs_count: {len(diag_comparable)}")
    lines.append("")
    lines.append("## Phase 2 Diagnostic")
    lines.append("")
    for run in report.get("runs", []):
        idx = int(run.get("run_index", 0))
        diagnosis = dict(run.get("diagnosis", {}))
        lines.append(
            f"- run {idx}: category={diagnosis.get('category')} "
            f"(confidence={diagnosis.get('confidence')}, pass={diagnosis.get('diagnostic_gate_pass')})"
        )
        per_phase = dict(diagnosis.get("per_phase", {}))
        for phase_name in ("cpp_native", "cpp_opencv"):
            phase_diag = dict(per_phase.get(phase_name, {}))
            lines.append(
                f"  - {phase_name}: {phase_diag.get('category')} "
                f"(confidence={phase_diag.get('confidence')}) evidence={phase_diag.get('evidence', [])}"
            )
    lines.append("")
    lines.append("## Output Paths")
    lines.append("")
    lines.append(f"- report_json: {report.get('report_json')}")
    lines.append(f"- report_md: {report.get('report_md')}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run render3d campaign(s) with standardized measurement capture and quality gates.",
    )
    parser.add_argument("--campaign-script", default="tools/run_campaign_z1_xy1.sh", help="Campaign shell script.")
    parser.add_argument("--corpus-dir", default="pwmb_files", help="PWMB corpus path passed to campaign script.")
    parser.add_argument("--reports-root", default="reports/measure_protocol", help="Root directory for run artifacts.")
    parser.add_argument("--workers", type=int, default=None, help="Workers passed to campaign script.")
    parser.add_argument(
        "--parallel-policy",
        default=None,
        choices=["python_fanout", "cpp_internal", "auto"],
        help="Parallel policy passed to campaign script.",
    )
    parser.add_argument("--runs", type=int, default=3, help="Number of complete campaign runs.")
    parser.add_argument(
        "--sample-delay-s",
        type=float,
        default=5.0,
        help="Seconds to wait after phase process is detected before capturing a snapshot.",
    )
    parser.add_argument("--vmstat-seconds", type=int, default=3, help="vmstat capture window.")
    parser.add_argument("--pidstat-seconds", type=int, default=3, help="pidstat capture window.")
    parser.add_argument("--perf-seconds", type=int, default=3, help="perf top timeout window.")
    parser.add_argument("--gate-max-si", type=float, default=0.0, help="Gate threshold for vmstat si max.")
    parser.add_argument("--gate-max-so", type=float, default=0.0, help="Gate threshold for vmstat so max.")
    parser.add_argument(
        "--gate-max-majflt-s",
        type=float,
        default=0.0,
        help="Gate threshold for pidstat average majflt/s.",
    )
    parser.add_argument("--strict-gates", action="store_true", help="Exit non-zero if any run fails measurement gates.")
    parser.add_argument(
        "--phase-detect-timeout-s",
        type=float,
        default=180.0,
        help="Max wait for each phase process detection during a run.",
    )
    parser.add_argument("--output-prefix", type=Path, default=None, help="Output prefix (without extension) for report.")
    args = parser.parse_args()

    runs = max(1, int(args.runs))
    repo_root = Path(__file__).resolve().parents[1]
    campaign_script = Path(str(args.campaign_script)).resolve()
    if not campaign_script.exists():
        raise SystemExit(f"campaign script not found: {campaign_script}")

    reports_root = Path(str(args.reports_root)).expanduser().resolve()
    reports_root.mkdir(parents=True, exist_ok=True)
    if args.output_prefix is None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_prefix = reports_root / f"measurement_protocol_{stamp}"
    else:
        output_prefix = Path(args.output_prefix).expanduser().resolve()
        output_prefix.parent.mkdir(parents=True, exist_ok=True)

    preflight = {
        "tools": {
            "taskset": shutil.which("taskset") is not None,
            "ps": shutil.which("ps") is not None,
            "vmstat": shutil.which("vmstat") is not None,
            "pidstat": shutil.which("pidstat") is not None,
            "perf": shutil.which("perf") is not None,
        },
        "perf_sysctl": _read_perf_sysctl(),
        "cpu_count": int(os.cpu_count() or 1),
        "python": sys.executable,
    }

    report: dict[str, Any] = {
        "started_at": _now_iso(),
        "runs_requested": runs,
        "strict_gates": bool(args.strict_gates),
        "config": {
            "campaign_script": str(campaign_script),
            "corpus_dir": str(Path(str(args.corpus_dir)).resolve()),
            "reports_root": str(reports_root),
            "workers": int(args.workers) if args.workers is not None else None,
            "parallel_policy": str(args.parallel_policy) if args.parallel_policy is not None else None,
            "sample_delay_s": float(args.sample_delay_s),
            "vmstat_seconds": int(args.vmstat_seconds),
            "pidstat_seconds": int(args.pidstat_seconds),
            "perf_seconds": int(args.perf_seconds),
            "gate_max_si": float(args.gate_max_si),
            "gate_max_so": float(args.gate_max_so),
            "gate_max_majflt_s": float(args.gate_max_majflt_s),
            "phase_detect_timeout_s": float(args.phase_detect_timeout_s),
        },
        "preflight": preflight,
        "runs": [],
    }

    comparable_runs: list[int] = []
    diagnostic_comparable_runs: list[int] = []
    workers_hint = int(args.workers) if args.workers is not None else int(preflight.get("cpu_count", 1))

    for run_idx in range(1, runs + 1):
        run_reports_dir = reports_root / f"run_{run_idx:02d}"
        run_reports_dir.mkdir(parents=True, exist_ok=True)
        log_path = run_reports_dir / "campaign.log"

        cmd = [str(campaign_script), str(Path(str(args.corpus_dir)).resolve()), str(run_reports_dir)]
        if args.workers is not None:
            cmd.append(str(int(args.workers)))
        if args.parallel_policy is not None:
            cmd.append(str(args.parallel_policy))
        phase_order = ("cpp_native", "cpp_opencv")
        phase_expected_outputs = {
            "cpp_native": run_reports_dir / "render3d_campaign_cpp_native_z1_xy1.json",
            "cpp_opencv": run_reports_dir / "render3d_campaign_cpp_opencv_z1_xy1.json",
        }
        phase_state: dict[str, dict[str, Any]] = {}
        for idx, name in enumerate(phase_order):
            is_activated = idx == 0
            phase_state[name] = {
                "first_seen_at_mono": None,
                "pid": None,
                "captured": False,
                "capture": None,
                "activated": is_activated,
                "detect_timed_out": False,
                "detect_deadline_mono": (
                    time.monotonic() + float(args.phase_detect_timeout_s) if is_activated else None
                ),
            }

        started_at = _now_iso()
        with log_path.open("w", encoding="utf-8") as log_fh:
            log_fh.write(f"[measure] started_at={started_at}\n")
            log_fh.write(f"[measure] command={' '.join(cmd)}\n")
            log_fh.flush()
            proc = subprocess.Popen(
                cmd,
                cwd=str(repo_root),
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                text=True,
            )

            while True:
                rc = proc.poll()
                now_mono = time.monotonic()
                for idx, phase_name in enumerate(phase_order):
                    state = phase_state[phase_name]
                    if bool(state.get("activated")):
                        continue
                    prev_phase = phase_order[idx - 1]
                    prev_state = phase_state[prev_phase]
                    prev_report_exists = phase_expected_outputs[prev_phase].exists()
                    if bool(prev_state.get("detect_timed_out")) or prev_report_exists:
                        state["activated"] = True
                        state["detect_deadline_mono"] = now_mono + float(args.phase_detect_timeout_s)
                        log_fh.write(f"[measure] activate phase={phase_name}\n")
                        log_fh.flush()

                for phase_name in phase_order:
                    output_path = phase_expected_outputs[phase_name]
                    state = phase_state[phase_name]
                    if bool(state["captured"]):
                        continue
                    if not bool(state.get("activated")):
                        continue
                    found_pid = _find_baseline_pid_by_output(output_path)
                    if found_pid is not None:
                        if state["pid"] != int(found_pid):
                            state["pid"] = int(found_pid)
                            state["first_seen_at_mono"] = now_mono
                        seen_at = state["first_seen_at_mono"]
                        if seen_at is not None and (now_mono - float(seen_at)) >= float(args.sample_delay_s):
                            snapshot = _collect_phase_snapshot(
                                pid=int(found_pid),
                                vmstat_seconds=int(args.vmstat_seconds),
                                pidstat_seconds=int(args.pidstat_seconds),
                                perf_seconds=int(args.perf_seconds),
                                gate_max_si=float(args.gate_max_si),
                                gate_max_so=float(args.gate_max_so),
                                gate_max_majflt_s=float(args.gate_max_majflt_s),
                                workers_hint=max(1, int(workers_hint)),
                            )
                            state["captured"] = True
                            state["capture"] = snapshot
                            log_fh.write(f"[measure] captured phase={phase_name} pid={found_pid}\n")
                            log_fh.flush()
                    else:
                        detect_deadline = state.get("detect_deadline_mono")
                        if isinstance(detect_deadline, int | float) and now_mono > float(detect_deadline):
                            state["detect_deadline_mono"] = None
                            state["detect_timed_out"] = True
                            log_fh.write(f"[measure] detect_timeout phase={phase_name}\n")
                            log_fh.flush()

                if rc is not None:
                    break
                time.sleep(1.0)

            campaign_rc = int(proc.wait())
            log_fh.write(f"[measure] campaign_returncode={campaign_rc}\n")
            log_fh.flush()

        phases_payload: dict[str, Any] = {}
        gate_reasons: list[str] = []
        for phase_name in ("cpp_native", "cpp_opencv"):
            state = phase_state[phase_name]
            capture = state.get("capture")
            if capture is None:
                phases_payload[phase_name] = {
                    "captured": False,
                    "pid": state.get("pid"),
                    "gate": {"pass": False, "reasons": ["phase_not_captured"]},
                }
                gate_reasons.append(f"{phase_name}:phase_not_captured")
                continue
            phases_payload[phase_name] = {
                "captured": True,
                "pid": capture.get("pid"),
                "captured_at": capture.get("captured_at"),
                "proc_status_subset": capture.get("proc_status_subset"),
                "gate": dict(capture.get("gate", {})),
                "diagnosis": dict(capture.get("diagnosis", {})),
                "vmstat_parsed": dict(dict(capture.get("vmstat", {})).get("parsed", {})),
                "pidstat_parsed": dict(dict(capture.get("pidstat", {})).get("parsed", {})),
                "snapshot": capture,
            }
            if not bool(dict(capture.get("gate", {})).get("pass", False)):
                reasons = list(dict(capture.get("gate", {})).get("reasons", []))
                joined = ",".join(str(x) for x in reasons) if reasons else "gate_failed"
                gate_reasons.append(f"{phase_name}:{joined}")

        summary = _summary_extract(run_reports_dir / "render3d_campaign_summary_z1_xy1.json")
        run_diagnosis = _consolidate_run_diagnosis(phases_payload)
        resource_summary = _extract_run_resource_summary(phases_payload)
        run_payload = {
            "run_index": run_idx,
            "started_at": started_at,
            "ended_at": _now_iso(),
            "campaign_command": cmd,
            "campaign_returncode": campaign_rc,
            "campaign_log": str(log_path),
            "reports_dir": str(run_reports_dir),
            "phases": phases_payload,
            "summary": summary,
            "resource_summary": resource_summary,
            "gate_pass": campaign_rc == 0 and len(gate_reasons) == 0,
            "gate_reasons": gate_reasons,
            "diagnosis": run_diagnosis,
            "diagnostic_gate_pass": bool(run_diagnosis.get("diagnostic_gate_pass")),
        }
        report["runs"].append(run_payload)
        if bool(run_payload["gate_pass"]):
            comparable_runs.append(run_idx)
        if bool(run_payload.get("diagnostic_gate_pass")):
            diagnostic_comparable_runs.append(run_idx)

    report["ended_at"] = _now_iso()
    report["comparable_run_indices"] = comparable_runs
    report["diagnostic_comparable_run_indices"] = diagnostic_comparable_runs
    report["report_json"] = str(output_prefix.with_suffix(".json"))
    report["report_md"] = str(output_prefix.with_suffix(".md"))

    output_json = output_prefix.with_suffix(".json")
    output_md = output_prefix.with_suffix(".md")
    output_json.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    _write_markdown(report, output_md)

    print(json.dumps({"report_json": str(output_json), "report_md": str(output_md)}, ensure_ascii=True))

    if bool(args.strict_gates):
        any_failed = any(not bool(run.get("gate_pass", False)) for run in report.get("runs", []))
        if any_failed:
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
