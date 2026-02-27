#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
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


def _aggregate(report: dict[str, Any]) -> dict[str, float]:
    totals = {
        "decode_ms_total": 0.0,
        "contours_ms_total": 0.0,
        "triangulation_ms_total": 0.0,
        "buffers_ms_total": 0.0,
        "total_ms": 0.0,
    }
    for item in report.get("results", []):
        metrics = dict(item.get("metrics", {}))
        decode = float(metrics.get("decode_ms_total", 0.0))
        contours = float(metrics.get("contours_ms_total", 0.0))
        tri = float(metrics.get("triangulation_ms_total", 0.0))
        buffers = float(metrics.get("buffers_ms_total", 0.0))
        totals["decode_ms_total"] += decode
        totals["contours_ms_total"] += contours
        totals["triangulation_ms_total"] += tri
        totals["buffers_ms_total"] += buffers
        totals["total_ms"] += decode + contours + tri + buffers
    return totals


def _variant_label(report: dict[str, Any], fallback: str) -> str:
    for item in report.get("results", []):
        value = item.get("cpp_opencv_approx_effective")
        if isinstance(value, str) and value.strip():
            return value.strip()
        value_req = item.get("cpp_opencv_approx_requested")
        if isinstance(value_req, str) and value_req.strip():
            return value_req.strip()
    return fallback


def _build_variant_delta(
    *,
    base: dict[str, dict[str, Any]],
    variant: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    files = sorted(set(base.keys()) & set(variant.keys()))
    if not files:
        return {"files": 0, "mesh_area_abs_sum": None, "contour_area_abs_sum": None, "tri_abs_sum": None, "score": None}

    mesh_area_abs_sum = 0.0
    contour_area_abs_sum = 0.0
    tri_abs_sum = 0
    for name in files:
        base_inv = dict(base[name].get("invariants", {}))
        variant_inv = dict(variant[name].get("invariants", {}))
        mesh_area_abs_sum += abs(float(variant_inv.get("mesh_area_mm2", 0.0)) - float(base_inv.get("mesh_area_mm2", 0.0)))
        contour_area_abs_sum += abs(
            float(variant_inv.get("contour_area_mm2", 0.0)) - float(base_inv.get("contour_area_mm2", 0.0))
        )
        tri_abs_sum += abs(int(variant_inv.get("triangle_count", 0)) - int(base_inv.get("triangle_count", 0)))

    score = (mesh_area_abs_sum * 10.0) + (contour_area_abs_sum * 8.0) + float(tri_abs_sum)
    return {
        "files": len(files),
        "mesh_area_abs_sum": mesh_area_abs_sum,
        "contour_area_abs_sum": contour_area_abs_sum,
        "tri_abs_sum": tri_abs_sum,
        "score": score,
    }


def _build_summary(
    *,
    cpp_native_report: dict[str, Any],
    opencv_reports: list[dict[str, Any]],
    opencv_fallback_labels: list[str],
) -> dict[str, Any]:
    native_by = _by_file(cpp_native_report)
    native_agg = _aggregate(cpp_native_report)

    variants: list[dict[str, Any]] = []
    for idx, report in enumerate(opencv_reports):
        label = _variant_label(report, opencv_fallback_labels[idx])
        by_file = _by_file(report)
        agg = _aggregate(report)
        vs_native = _build_variant_delta(base=native_by, variant=by_file)
        variants.append(
            {
                "label": label,
                "aggregate": agg,
                "speedup_vs_cpp_native_total_x": (float(native_agg["total_ms"]) / agg["total_ms"])
                if agg["total_ms"] > 0
                else None,
                "delta_vs_cpp_native": vs_native,
            }
        )

    scored = []
    for variant in variants:
        delta = dict(variant.get("delta_vs_cpp_native", {}))
        score = delta.get("score")
        total_ms = float(dict(variant.get("aggregate", {})).get("total_ms", 0.0))
        if score is None:
            continue
        scored.append((float(score), total_ms, str(variant.get("label", "unknown"))))
    scored.sort(key=lambda item: (item[0], item[1], item[2]))
    recommended = scored[0][2] if scored else None

    return {
        "aggregate": {
            "cpp_native": native_agg,
            "opencv_variants": variants,
        },
        "recommended_opencv_approx": recommended,
        "decision_basis": "min(delta_vs_cpp_native.score), tie-break on total_ms",
    }


def _write_markdown(path: Path, summary: dict[str, Any]) -> None:
    agg = dict(summary.get("aggregate", {}))
    variants = list(agg.get("opencv_variants", []))
    native = dict(agg.get("cpp_native", {}))

    lines: list[str] = []
    lines.append("# OpenCV Approx Campaign Summary")
    lines.append("")
    lines.append("## Aggregate timings (ms)")
    lines.append("")
    lines.append("| backend | decode | contours | triangulation | buffers | total |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    lines.append(
        f"| cpp_native | {native.get('decode_ms_total', 0.0):.3f} | {native.get('contours_ms_total', 0.0):.3f} | "
        f"{native.get('triangulation_ms_total', 0.0):.3f} | {native.get('buffers_ms_total', 0.0):.3f} | {native.get('total_ms', 0.0):.3f} |"
    )
    for variant in variants:
        item = dict(variant.get("aggregate", {}))
        label = str(variant.get("label", "opencv"))
        lines.append(
            f"| cpp_opencv({label}) | {item.get('decode_ms_total', 0.0):.3f} | {item.get('contours_ms_total', 0.0):.3f} | "
            f"{item.get('triangulation_ms_total', 0.0):.3f} | {item.get('buffers_ms_total', 0.0):.3f} | {item.get('total_ms', 0.0):.3f} |"
        )
    lines.append("")
    lines.append("## Parity vs cpp_native")
    lines.append("")
    lines.append("| opencv approx | files | mesh_area_abs_sum | contour_area_abs_sum | tri_abs_sum | score |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for variant in variants:
        label = str(variant.get("label", "opencv"))
        delta = dict(variant.get("delta_vs_cpp_native", {}))
        lines.append(
            f"| {label} | {int(delta.get('files', 0))} | "
            f"{float(delta.get('mesh_area_abs_sum', 0.0)):.6f} | "
            f"{float(delta.get('contour_area_abs_sum', 0.0)):.6f} | "
            f"{int(delta.get('tri_abs_sum', 0))} | "
            f"{float(delta.get('score', 0.0)):.6f} |"
        )
    lines.append("")
    lines.append("## Recommendation")
    lines.append("")
    lines.append(f"- Recommended OpenCV approx: **{summary.get('recommended_opencv_approx')}**")
    lines.append(f"- Decision basis: `{summary.get('decision_basis')}`")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize OpenCV approximation campaigns.")
    parser.add_argument("--cpp-native-report", type=Path, required=True)
    parser.add_argument(
        "--cpp-opencv-report",
        action="append",
        required=True,
        help="Repeat for each opencv approximation report.",
    )
    parser.add_argument(
        "--opencv-label",
        action="append",
        required=True,
        help="Repeat labels in the same order as --cpp-opencv-report (e.g. simple, tc89_l1, tc89_kcos).",
    )
    parser.add_argument("--output-prefix", type=Path, required=True)
    args = parser.parse_args()

    if len(args.cpp_opencv_report) != len(args.opencv_label):
        raise SystemExit("--cpp-opencv-report and --opencv-label must have identical counts")

    cpp_native_report = _load_json(args.cpp_native_report)
    opencv_reports = [_load_json(Path(p)) for p in args.cpp_opencv_report]
    summary = _build_summary(
        cpp_native_report=cpp_native_report,
        opencv_reports=opencv_reports,
        opencv_fallback_labels=[str(x) for x in args.opencv_label],
    )

    output_json = Path(f"{args.output_prefix}.json")
    output_md = Path(f"{args.output_prefix}.md")
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(summary, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    _write_markdown(output_md, summary)

    print(json.dumps({"summary_json": str(output_json), "summary_md": str(output_md)}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
