from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any


@dataclass(slots=True)
class VmstatStats:
    samples: int = 0
    max_si: float = 0.0
    max_so: float = 0.0
    avg_si: float = 0.0
    avg_so: float = 0.0
    avg_id: float = 0.0
    min_id: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PidstatStats:
    avg_cpu: float | None = None
    avg_usr: float | None = None
    avg_system: float | None = None
    avg_minflt_s: float | None = None
    avg_majflt_s: float | None = None
    avg_rss_kb: int | None = None
    avg_mem_percent: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ThreadActivityStats:
    samples: int = 0
    hot_threads: int = 0
    very_hot_threads: int = 0
    max_thread_pcpu: float = 0.0
    sum_thread_pcpu: float = 0.0
    dominance_ratio: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PerfHotspotStats:
    available: bool = False
    restricted: bool = False
    py_hot_hits: int = 0
    native_hot_hits: int = 0
    top_symbols: list[str] | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["top_symbols"] = list(self.top_symbols or [])
        return payload


def _safe_float(raw: str) -> float | None:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _safe_int(raw: str) -> int | None:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def parse_vmstat_output(output: str) -> VmstatStats:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    header: list[str] = []
    si_values: list[float] = []
    so_values: list[float] = []
    id_values: list[float] = []

    for line in lines:
        tokens = line.split()
        if "swpd" in tokens and "si" in tokens and "so" in tokens:
            header = tokens
            continue
        if not header or len(tokens) < len(header):
            continue
        if not re.fullmatch(r"-?\d+", tokens[0]):
            continue
        values: dict[str, float] = {}
        valid = True
        for key, raw in zip(header, tokens):
            parsed = _safe_float(raw)
            if parsed is None:
                valid = False
                break
            values[key] = parsed
        if not valid:
            continue
        if "si" not in values or "so" not in values:
            continue
        si_values.append(float(values["si"]))
        so_values.append(float(values["so"]))
        if "id" in values:
            id_values.append(float(values["id"]))

    if not si_values or not so_values:
        return VmstatStats()
    count = min(len(si_values), len(so_values))
    return VmstatStats(
        samples=count,
        max_si=max(si_values[:count]),
        max_so=max(so_values[:count]),
        avg_si=sum(si_values[:count]) / float(count),
        avg_so=sum(so_values[:count]) / float(count),
        avg_id=(sum(id_values[:count]) / float(count)) if id_values else 0.0,
        min_id=min(id_values[:count]) if id_values else 0.0,
    )


def parse_pidstat_output(output: str) -> PidstatStats:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    stats = PidstatStats()

    for idx, line in enumerate(lines[:-1]):
        if not line.startswith("Average:"):
            continue
        if "%usr" in line and "%CPU" in line:
            values = lines[idx + 1].split()
            if len(values) >= 8 and values[0] == "Average:":
                stats.avg_usr = _safe_float(values[3])
                stats.avg_system = _safe_float(values[4])
                stats.avg_cpu = _safe_float(values[7])
        if "minflt/s" in line and "majflt/s" in line:
            values = lines[idx + 1].split()
            if len(values) >= 8 and values[0] == "Average:":
                stats.avg_minflt_s = _safe_float(values[3])
                stats.avg_majflt_s = _safe_float(values[4])
                stats.avg_rss_kb = _safe_int(values[6])
                stats.avg_mem_percent = _safe_float(values[7])

    return stats


def parse_ps_threads_output(output: str, *, hot_threshold: float = 10.0, very_hot_threshold: float = 50.0) -> ThreadActivityStats:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    values: list[float] = []
    for line in lines:
        # Expected data line: PID TID PSR %CPU COMMAND
        if line.lower().startswith("pid "):
            continue
        tokens = line.split()
        if len(tokens) < 5:
            continue
        if not re.fullmatch(r"\d+", tokens[0]):
            continue
        pcpu = _safe_float(tokens[3])
        if pcpu is None:
            continue
        values.append(float(pcpu))
    if not values:
        return ThreadActivityStats()
    total = float(sum(values))
    max_pcpu = float(max(values))
    dominance: float | None = None
    if total > 0.0:
        dominance = max_pcpu / total
    return ThreadActivityStats(
        samples=len(values),
        hot_threads=sum(1 for value in values if value >= float(hot_threshold)),
        very_hot_threads=sum(1 for value in values if value >= float(very_hot_threshold)),
        max_thread_pcpu=max_pcpu,
        sum_thread_pcpu=total,
        dominance_ratio=dominance,
    )


def parse_perf_top_output(stdout: str, stderr: str = "") -> PerfHotspotStats:
    text = f"{stdout}\n{stderr}".strip()
    if not text:
        return PerfHotspotStats()
    lowered = text.lower()
    restricted = "perf_event_paranoid" in lowered or "access to performance monitoring" in lowered

    py_patterns = (
        r"\bPyEval_[A-Za-z0-9_]+\b",
        r"\btake_gil\b",
        r"\bceval\b",
        r"\b_Py[A-Za-z0-9_]+\b",
    )
    native_patterns = (
        r"\bpwmb[_A-Za-z0-9]*\b",
        r"\btriangulate[_A-Za-z0-9]*\b",
        r"\bcontour[_A-Za-z0-9]*\b",
        r"\bopencv[_A-Za-z0-9]*\b",
        r"\btbb[_A-Za-z0-9]*\b",
    )
    py_hits = 0
    for pattern in py_patterns:
        py_hits += len(re.findall(pattern, text))
    native_hits = 0
    for pattern in native_patterns:
        native_hits += len(re.findall(pattern, lowered))

    top_symbols: list[str] = []
    for line in text.splitlines():
        clean = line.strip()
        if not clean or "%" not in clean:
            continue
        if "[.]" in clean:
            symbol = clean.split("[.]", 1)[1].strip()
            if symbol and symbol not in top_symbols:
                top_symbols.append(symbol)
                if len(top_symbols) >= 8:
                    break

    return PerfHotspotStats(
        available=True,
        restricted=restricted,
        py_hot_hits=int(py_hits),
        native_hot_hits=int(native_hits),
        top_symbols=top_symbols,
    )


def diagnose_phase_bottleneck(
    *,
    gate: dict[str, Any],
    vmstat_stats: VmstatStats,
    pidstat_stats: PidstatStats,
    thread_stats: ThreadActivityStats,
    perf_stats: PerfHotspotStats | None,
    workers_hint: int,
) -> dict[str, Any]:
    scores = {
        "memory_pressure": 0.0,
        "gil_or_python_overhead": 0.0,
        "native_serial_or_underutilized": 0.0,
    }
    evidence: list[str] = []

    if not bool(gate.get("pass", True)):
        for reason in list(gate.get("reasons", [])):
            text = str(reason)
            if text.startswith("vmstat_max_si") or text.startswith("vmstat_max_so") or text.startswith("pidstat_avg_majflt_s"):
                scores["memory_pressure"] += 3.0
                evidence.append(text)

    avg_cpu = pidstat_stats.avg_cpu
    low_cpu = avg_cpu is not None and float(avg_cpu) <= max(200.0, float(max(1, workers_hint)) * 25.0)
    if low_cpu:
        scores["gil_or_python_overhead"] += 1.0
        scores["native_serial_or_underutilized"] += 1.0
        evidence.append(f"low_process_cpu={float(avg_cpu):.3f}")

    if thread_stats.samples > 0:
        if thread_stats.hot_threads <= 2:
            scores["gil_or_python_overhead"] += 1.0
            scores["native_serial_or_underutilized"] += 1.0
            evidence.append(f"hot_threads={thread_stats.hot_threads}")
        if thread_stats.dominance_ratio is not None and float(thread_stats.dominance_ratio) >= 0.7:
            scores["gil_or_python_overhead"] += 1.0
            scores["native_serial_or_underutilized"] += 1.0
            evidence.append(f"dominance_ratio={float(thread_stats.dominance_ratio):.3f}")

    if perf_stats is not None:
        if perf_stats.restricted:
            evidence.append("perf_restricted")
        if perf_stats.py_hot_hits > 0:
            scores["gil_or_python_overhead"] += 2.0 + float(perf_stats.py_hot_hits)
            evidence.append(f"perf_py_hot_hits={perf_stats.py_hot_hits}")
        if perf_stats.native_hot_hits > 0:
            scores["native_serial_or_underutilized"] += 1.0 + float(perf_stats.native_hot_hits)
            evidence.append(f"perf_native_hot_hits={perf_stats.native_hot_hits}")
        if perf_stats.py_hot_hits > perf_stats.native_hot_hits:
            scores["gil_or_python_overhead"] += 1.0
        elif perf_stats.native_hot_hits > perf_stats.py_hot_hits:
            scores["native_serial_or_underutilized"] += 1.0

    winner = "inconclusive"
    confidence = 0.0
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    if ranked and ranked[0][1] > 0.0:
        first_name, first_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0.0
        if first_score >= second_score + 1.0:
            winner = str(first_name)
            confidence = round(min(1.0, 0.25 * float(first_score - second_score) + 0.35), 3)
        else:
            winner = "inconclusive"
            confidence = 0.25

    return {
        "category": winner,
        "confidence": confidence,
        "scores": {name: round(float(value), 3) for name, value in scores.items()},
        "evidence": evidence[:20],
    }


def evaluate_measurement_gate(
    vmstat_stats: VmstatStats,
    pidstat_stats: PidstatStats,
    *,
    max_si: float,
    max_so: float,
    max_majflt_s: float,
) -> dict[str, Any]:
    reasons: list[str] = []
    if vmstat_stats.samples <= 0:
        reasons.append("vmstat_missing")
    else:
        if float(vmstat_stats.max_si) > float(max_si):
            reasons.append(f"vmstat_max_si={vmstat_stats.max_si:.3f}>{float(max_si):.3f}")
        if float(vmstat_stats.max_so) > float(max_so):
            reasons.append(f"vmstat_max_so={vmstat_stats.max_so:.3f}>{float(max_so):.3f}")

    if pidstat_stats.avg_majflt_s is None:
        reasons.append("pidstat_avg_majflt_missing")
    elif float(pidstat_stats.avg_majflt_s) > float(max_majflt_s):
        reasons.append(f"pidstat_avg_majflt_s={float(pidstat_stats.avg_majflt_s):.3f}>{float(max_majflt_s):.3f}")

    return {
        "pass": len(reasons) == 0,
        "reasons": reasons,
        "thresholds": {
            "max_si": float(max_si),
            "max_so": float(max_so),
            "max_majflt_s": float(max_majflt_s),
        },
    }
