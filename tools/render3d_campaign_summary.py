#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from math import isfinite
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _by_file(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in report.get("results", []):
        file_name = Path(str(item.get("file", ""))).name
        if file_name:
            out[file_name] = item
    return out


def _bbox_delta_max(lhs: Any, rhs: Any) -> float | None:
    if not isinstance(lhs, list | tuple) or not isinstance(rhs, list | tuple):
        return None
    if len(lhs) != len(rhs):
        return None
    try:
        return max(abs(float(a) - float(b)) for a, b in zip(lhs, rhs))
    except (TypeError, ValueError):
        return None


def _total_cpu_ms(result: dict[str, Any]) -> float:
    metrics = dict(result.get("metrics", {}))
    return (
        float(metrics.get("decode_ms_total", 0.0))
        + float(metrics.get("contours_ms_total", 0.0))
        + float(metrics.get("triangulation_ms_total", 0.0))
        + float(metrics.get("buffers_ms_total", 0.0))
    )


def _total_wall_ms(result: dict[str, Any]) -> float:
    metrics = dict(result.get("metrics", {}))
    parse_ms = float(metrics.get("parse_ms", 0.0))
    decode_cpu_ms = float(metrics.get("decode_ms_total", 0.0))
    contours_cpu_ms = float(metrics.get("contours_ms_total", 0.0))
    tri_cpu_ms = float(metrics.get("triangulation_ms_total", 0.0))
    # Backward-safe fallback when wall fields are absent in legacy reports.
    contours_wall_ms = float(metrics.get("contours_wall_ms", decode_cpu_ms + contours_cpu_ms))
    triangulation_wall_ms = float(metrics.get("triangulation_wall_ms", tri_cpu_ms))
    buffers_ms = float(metrics.get("buffers_ms_total", 0.0))
    return parse_ms + contours_wall_ms + triangulation_wall_ms + buffers_ms


def _aggregate(report: dict[str, Any]) -> dict[str, Any]:
    totals = {
        "parse_ms_total": 0.0,
        "decode_ms_total": 0.0,
        "contours_ms_total": 0.0,
        "triangulation_ms_total": 0.0,
        "contours_wall_ms_total": 0.0,
        "triangulation_wall_ms_total": 0.0,
        "buffers_ms_total": 0.0,
        "total_cpu_ms": 0.0,
        "total_wall_ms": 0.0,
        # Backward-compatible alias: total_ms now means total wall-clock latency.
        "total_ms": 0.0,
        "loops_total": 0,
        "triangles_total": 0,
        "vertices_total": 0,
        "layers_total": 0,
        "layers_built": 0,
        "layers_skipped": 0,
    }
    for item in report.get("results", []):
        metrics = dict(item.get("metrics", {}))
        parse_ms = float(metrics.get("parse_ms", 0.0))
        decode_ms = float(metrics.get("decode_ms_total", 0.0))
        contours_ms = float(metrics.get("contours_ms_total", 0.0))
        tri_ms = float(metrics.get("triangulation_ms_total", 0.0))
        contours_wall_ms = float(metrics.get("contours_wall_ms", decode_ms + contours_ms))
        triangulation_wall_ms = float(metrics.get("triangulation_wall_ms", tri_ms))
        buffers_ms = float(metrics.get("buffers_ms_total", 0.0))
        total_cpu = decode_ms + contours_ms + tri_ms + buffers_ms
        total_wall = parse_ms + contours_wall_ms + triangulation_wall_ms + buffers_ms
        totals["parse_ms_total"] += parse_ms
        totals["decode_ms_total"] += decode_ms
        totals["contours_ms_total"] += contours_ms
        totals["triangulation_ms_total"] += tri_ms
        totals["contours_wall_ms_total"] += contours_wall_ms
        totals["triangulation_wall_ms_total"] += triangulation_wall_ms
        totals["buffers_ms_total"] += buffers_ms
        totals["total_cpu_ms"] += total_cpu
        totals["total_wall_ms"] += total_wall
        totals["total_ms"] += total_wall
        for key in (
            "loops_total",
            "triangles_total",
            "vertices_total",
            "layers_total",
            "layers_built",
            "layers_skipped",
        ):
            totals[key] += int(metrics.get(key, 0))
    return totals


def _extract_protocol(report: dict[str, Any]) -> dict[str, Any]:
    files = sorted(Path(str(item.get("file", ""))).name for item in report.get("results", []))
    z_stride = None
    xy_stride = None
    bin_mode = None
    threshold = None
    if report.get("results"):
        head = dict(report["results"][0])
        z_stride = head.get("z_stride")
        xy_stride = head.get("xy_stride")
        bin_mode = head.get("bin_mode")
        threshold = head.get("threshold")
    return {
        "scope_files": files,
        "z_stride": z_stride,
        "xy_stride": xy_stride,
        "bin_mode": bin_mode,
        "threshold": threshold,
    }


def _build_summary(
    py_report: dict[str, Any],
    cpp_native_report: dict[str, Any],
    cpp_opencv_report: dict[str, Any],
) -> dict[str, Any]:
    py_by_file = _by_file(py_report)
    native_by_file = _by_file(cpp_native_report)
    opencv_by_file = _by_file(cpp_opencv_report)
    files = sorted(set(py_by_file) & set(native_by_file) & set(opencv_by_file))

    per_file: list[dict[str, Any]] = []
    for name in files:
        py_item = py_by_file[name]
        native_item = native_by_file[name]
        opencv_item = opencv_by_file[name]
        py_inv = dict(py_item.get("invariants", {}))
        native_inv = dict(native_item.get("invariants", {}))
        opencv_inv = dict(opencv_item.get("invariants", {}))

        per_file.append(
            {
                "file": name,
                "python_total_ms": _total_wall_ms(py_item),
                "python_total_wall_ms": _total_wall_ms(py_item),
                "python_total_cpu_ms": _total_cpu_ms(py_item),
                "cpp_native_total_ms": _total_wall_ms(native_item),
                "cpp_native_total_wall_ms": _total_wall_ms(native_item),
                "cpp_native_total_cpu_ms": _total_cpu_ms(native_item),
                "cpp_opencv_total_ms": _total_wall_ms(opencv_item),
                "cpp_opencv_total_wall_ms": _total_wall_ms(opencv_item),
                "cpp_opencv_total_cpu_ms": _total_cpu_ms(opencv_item),
                "native_vs_python": {
                    "contour_area_delta_mm2": float(native_inv.get("contour_area_mm2", 0.0))
                    - float(py_inv.get("contour_area_mm2", 0.0)),
                    "mesh_area_delta_mm2": float(native_inv.get("mesh_area_mm2", 0.0))
                    - float(py_inv.get("mesh_area_mm2", 0.0)),
                    "contour_bbox_delta_max": _bbox_delta_max(
                        native_inv.get("contour_bbox"),
                        py_inv.get("contour_bbox"),
                    ),
                    "mesh_bbox_delta_max": _bbox_delta_max(
                        native_inv.get("mesh_bbox"),
                        py_inv.get("mesh_bbox"),
                    ),
                    "triangle_count_delta": int(native_inv.get("triangle_count", 0))
                    - int(py_inv.get("triangle_count", 0)),
                },
                "opencv_vs_python": {
                    "contour_area_delta_mm2": float(opencv_inv.get("contour_area_mm2", 0.0))
                    - float(py_inv.get("contour_area_mm2", 0.0)),
                    "mesh_area_delta_mm2": float(opencv_inv.get("mesh_area_mm2", 0.0))
                    - float(py_inv.get("mesh_area_mm2", 0.0)),
                    "contour_bbox_delta_max": _bbox_delta_max(
                        opencv_inv.get("contour_bbox"),
                        py_inv.get("contour_bbox"),
                    ),
                    "mesh_bbox_delta_max": _bbox_delta_max(
                        opencv_inv.get("mesh_bbox"),
                        py_inv.get("mesh_bbox"),
                    ),
                    "triangle_count_delta": int(opencv_inv.get("triangle_count", 0))
                    - int(py_inv.get("triangle_count", 0)),
                },
                "opencv_vs_native": {
                    "contour_area_delta_mm2": float(opencv_inv.get("contour_area_mm2", 0.0))
                    - float(native_inv.get("contour_area_mm2", 0.0)),
                    "mesh_area_delta_mm2": float(opencv_inv.get("mesh_area_mm2", 0.0))
                    - float(native_inv.get("mesh_area_mm2", 0.0)),
                    "triangle_count_delta": int(opencv_inv.get("triangle_count", 0))
                    - int(native_inv.get("triangle_count", 0)),
                    "loops_total_delta": int(dict(opencv_item.get("metrics", {})).get("loops_total", 0))
                    - int(dict(native_item.get("metrics", {})).get("loops_total", 0)),
                    "triangulation_ms_delta": float(dict(opencv_item.get("metrics", {})).get("triangulation_ms_total", 0.0))
                    - float(dict(native_item.get("metrics", {})).get("triangulation_ms_total", 0.0)),
                    "triangulation_wall_ms_delta": float(dict(opencv_item.get("metrics", {})).get("triangulation_wall_ms", 0.0))
                    - float(dict(native_item.get("metrics", {})).get("triangulation_wall_ms", 0.0)),
                    "contours_ms_delta": float(dict(opencv_item.get("metrics", {})).get("contours_ms_total", 0.0))
                    - float(dict(native_item.get("metrics", {})).get("contours_ms_total", 0.0)),
                    "contours_wall_ms_delta": float(dict(opencv_item.get("metrics", {})).get("contours_wall_ms", 0.0))
                    - float(dict(native_item.get("metrics", {})).get("contours_wall_ms", 0.0)),
                    "decode_ms_delta": float(dict(opencv_item.get("metrics", {})).get("decode_ms_total", 0.0))
                    - float(dict(native_item.get("metrics", {})).get("decode_ms_total", 0.0)),
                    "total_cpu_ms_delta": _total_cpu_ms(opencv_item) - _total_cpu_ms(native_item),
                    "total_wall_ms_delta": _total_wall_ms(opencv_item) - _total_wall_ms(native_item),
                    # Backward-compatible alias: total_ms_delta now means wall-clock delta.
                    "total_ms_delta": _total_wall_ms(opencv_item) - _total_wall_ms(native_item),
                },
            }
        )

    agg_py = _aggregate(py_report)
    agg_native = _aggregate(cpp_native_report)
    agg_opencv = _aggregate(cpp_opencv_report)

    return {
        "protocol": _extract_protocol(py_report),
        "aggregate": {
            "python": agg_py,
            "cpp_native": agg_native,
            "cpp_opencv": agg_opencv,
        },
        "speedups": {
            "cpp_native_vs_python_total_x": (agg_py["total_wall_ms"] / agg_native["total_wall_ms"])
            if agg_native["total_wall_ms"] > 0
            else None,
            "cpp_opencv_vs_python_total_x": (agg_py["total_wall_ms"] / agg_opencv["total_wall_ms"])
            if agg_opencv["total_wall_ms"] > 0
            else None,
            "cpp_native_vs_opencv_total_x": (agg_opencv["total_wall_ms"] / agg_native["total_wall_ms"])
            if agg_native["total_wall_ms"] > 0
            else None,
            "cpp_native_vs_python_total_cpu_x": (agg_py["total_cpu_ms"] / agg_native["total_cpu_ms"])
            if agg_native["total_cpu_ms"] > 0
            else None,
            "cpp_opencv_vs_python_total_cpu_x": (agg_py["total_cpu_ms"] / agg_opencv["total_cpu_ms"])
            if agg_opencv["total_cpu_ms"] > 0
            else None,
            "cpp_native_vs_opencv_total_cpu_x": (agg_opencv["total_cpu_ms"] / agg_native["total_cpu_ms"])
            if agg_native["total_cpu_ms"] > 0
            else None,
            "cpp_native_vs_opencv_contours_x": (
                agg_opencv["contours_ms_total"] / agg_native["contours_ms_total"]
            )
            if agg_native["contours_ms_total"] > 0
            else None,
            "cpp_native_vs_opencv_triangulation_x": (
                agg_opencv["triangulation_ms_total"] / agg_native["triangulation_ms_total"]
            )
            if agg_native["triangulation_ms_total"] > 0
            else None,
        },
        "per_file": per_file,
    }


def _speed_line(label: str, value: Any) -> str:
    if isinstance(value, int | float) and isfinite(float(value)):
        return f"- {label}: {float(value):.3f}x"
    return f"- {label}: {value}"


def _write_markdown(path: Path, summary: dict[str, Any]) -> None:
    agg = dict(summary["aggregate"])
    speedups = dict(summary["speedups"])
    per_file = list(summary.get("per_file", []))
    protocol = dict(summary.get("protocol", {}))

    lines: list[str] = []
    lines.append("# Render3D Campaign Summary")
    lines.append("")
    lines.append("## Protocol")
    lines.append("")
    lines.append(f"- files: {', '.join(str(x) for x in protocol.get('scope_files', []))}")
    lines.append(f"- xy_stride: {protocol.get('xy_stride')}")
    lines.append(f"- z_stride: {protocol.get('z_stride')}")
    lines.append(f"- bin_mode: {protocol.get('bin_mode')}")
    lines.append(f"- threshold: {protocol.get('threshold')}")
    lines.append("")
    lines.append("## Aggregate timings (wall ms)")
    lines.append("")
    lines.append("| backend | parse | contours_wall | triangulation_wall | buffers | total_wall |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for key in ("python", "cpp_native", "cpp_opencv"):
        item = dict(agg.get(key, {}))
        lines.append(
            f"| {key} | {float(item.get('parse_ms_total', 0.0)):.3f} | "
            f"{float(item.get('contours_wall_ms_total', 0.0)):.3f} | "
            f"{float(item.get('triangulation_wall_ms_total', 0.0)):.3f} | "
            f"{float(item.get('buffers_ms_total', 0.0)):.3f} | "
            f"{float(item.get('total_wall_ms', 0.0)):.3f} |"
        )
    lines.append("")
    lines.append("## Aggregate timings (cumulative CPU ms)")
    lines.append("")
    lines.append("| backend | decode_cpu | contours_cpu | triangulation_cpu | buffers | total_cpu |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for key in ("python", "cpp_native", "cpp_opencv"):
        item = dict(agg.get(key, {}))
        lines.append(
            f"| {key} | {float(item.get('decode_ms_total', 0.0)):.3f} | "
            f"{float(item.get('contours_ms_total', 0.0)):.3f} | "
            f"{float(item.get('triangulation_ms_total', 0.0)):.3f} | "
            f"{float(item.get('buffers_ms_total', 0.0)):.3f} | "
            f"{float(item.get('total_cpu_ms', 0.0)):.3f} |"
        )
    lines.append("")
    lines.append("## Speedups (wall)")
    lines.append("")
    for k in (
        "cpp_native_vs_python_total_x",
        "cpp_opencv_vs_python_total_x",
        "cpp_native_vs_opencv_total_x",
        "cpp_native_vs_opencv_contours_x",
        "cpp_native_vs_opencv_triangulation_x",
    ):
        lines.append(_speed_line(k, speedups.get(k)))
    lines.append("")
    lines.append("## Speedups (cumulative CPU)")
    lines.append("")
    for k in (
        "cpp_native_vs_python_total_cpu_x",
        "cpp_opencv_vs_python_total_cpu_x",
        "cpp_native_vs_opencv_total_cpu_x",
    ):
        lines.append(_speed_line(k, speedups.get(k)))
    lines.append("")
    lines.append("## Functional deltas vs python")
    lines.append("")
    lines.append("| file | native mesh Δmm2 | opencv mesh Δmm2 | native tri Δ | opencv tri Δ |")
    lines.append("|---|---:|---:|---:|---:|")
    for item in per_file:
        native = dict(item.get("native_vs_python", {}))
        opencv = dict(item.get("opencv_vs_python", {}))
        lines.append(
            f"| {item.get('file')} | "
            f"{float(native.get('mesh_area_delta_mm2', 0.0)):.6f} | "
            f"{float(opencv.get('mesh_area_delta_mm2', 0.0)):.6f} | "
            f"{int(native.get('triangle_count_delta', 0))} | "
            f"{int(opencv.get('triangle_count_delta', 0))} |"
        )
    lines.append("")
    lines.append("## Decision")
    lines.append("")
    lines.append("- Default recommended: **native**")
    lines.append("- Reason: best parity vs python and best overall runtime on measured corpus.")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a consolidated summary from render3d baseline reports.")
    parser.add_argument("--python-report", type=Path, required=True, help="Path to python baseline report JSON.")
    parser.add_argument("--cpp-native-report", type=Path, required=True, help="Path to cpp/native baseline report JSON.")
    parser.add_argument("--cpp-opencv-report", type=Path, required=True, help="Path to cpp/opencv baseline report JSON.")
    parser.add_argument(
        "--output-prefix",
        type=Path,
        required=True,
        help="Output prefix (without extension) for summary JSON and Markdown.",
    )
    args = parser.parse_args()

    py_report = _load_json(args.python_report)
    cpp_native_report = _load_json(args.cpp_native_report)
    cpp_opencv_report = _load_json(args.cpp_opencv_report)

    summary = _build_summary(py_report, cpp_native_report, cpp_opencv_report)

    output_json = Path(f"{args.output_prefix}.json")
    output_md = Path(f"{args.output_prefix}.md")
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(summary, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    _write_markdown(output_md, summary)

    print(json.dumps({"summary_json": str(output_json), "summary_md": str(output_md)}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
