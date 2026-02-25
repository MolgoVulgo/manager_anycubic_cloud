#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pwmb_core import read_pwmb_document
from render3d_core import BuildMetrics, build_geometry_pipeline, compute_file_signature, resolve_geometry_backend
from render3d_core.invariants import build_invariant_snapshot
from render3d_core.types import PwmbContourStack


def _collect_pwmb_files(entries: list[str], *, recursive: bool) -> list[Path]:
    selected: list[Path] = []
    seen: set[Path] = set()
    for raw in entries:
        path = Path(raw).expanduser().resolve()
        if path.is_file():
            if path.suffix.lower() == ".pwmb" and path not in seen:
                seen.add(path)
                selected.append(path)
            continue
        if not path.is_dir():
            continue
        pattern = "**/*.pwmb" if recursive else "*.pwmb"
        for candidate in sorted(path.glob(pattern)):
            normalized = candidate.resolve()
            if normalized in seen:
                continue
            seen.add(normalized)
            selected.append(normalized)
    return selected


def _loops_summary(stack: PwmbContourStack) -> dict[str, int]:
    layers = len(stack.layers)
    outer = 0
    holes = 0
    for loops in stack.layers.values():
        outer += len(loops.outer)
        holes += len(loops.holes)
    return {"layers": layers, "outer_loops": outer, "hole_loops": holes}


def _bbox_delta(lhs: tuple[float, ...] | None, rhs: tuple[float, ...] | None) -> list[float] | None:
    if lhs is None or rhs is None:
        return None
    if len(lhs) != len(rhs):
        return None
    return [float(a - b) for a, b in zip(lhs, rhs)]


def _compare_case(
    path: Path,
    *,
    threshold: int,
    bin_mode: str,
    xy_stride: int,
    z_stride: int,
    max_layers: int | None,
    max_vertices: int | None,
    max_xy_stride: int,
    area_tol: float,
) -> dict[str, Any]:
    signature = compute_file_signature(path)
    document = read_pwmb_document(path)

    py_backend = resolve_geometry_backend(preferred="python")
    cpp_backend = resolve_geometry_backend(preferred="cpp")
    if cpp_backend.name != "cpp":
        raise RuntimeError("cpp backend unavailable (pwmb_geom not importable)")

    py_metrics = BuildMetrics(pool_kind="threads", workers=1)
    cpp_metrics = BuildMetrics(pool_kind="threads", workers=1)

    py_result = build_geometry_pipeline(
        document,
        threshold=threshold,
        bin_mode=bin_mode,
        xy_stride=xy_stride,
        z_stride=max(1, int(z_stride)),
        max_layers=max_layers,
        max_vertices=max_vertices,
        max_xy_stride=max_xy_stride,
        file_signature=signature,
        backend=py_backend,
        cache=None,
        metrics=py_metrics,
    )
    cpp_result = build_geometry_pipeline(
        document,
        threshold=threshold,
        bin_mode=bin_mode,
        xy_stride=xy_stride,
        z_stride=max(1, int(z_stride)),
        max_layers=max_layers,
        max_vertices=max_vertices,
        max_xy_stride=max_xy_stride,
        file_signature=signature,
        backend=cpp_backend,
        cache=None,
        metrics=cpp_metrics,
    )

    py_invariants = build_invariant_snapshot(py_result.contour_stack, py_result.geometry)
    cpp_invariants = build_invariant_snapshot(cpp_result.contour_stack, cpp_result.geometry)
    py_loops = _loops_summary(py_result.contour_stack)
    cpp_loops = _loops_summary(cpp_result.contour_stack)

    contour_area_delta = cpp_invariants.contour_area_mm2 - py_invariants.contour_area_mm2
    mesh_area_delta = cpp_invariants.mesh_area_mm2 - py_invariants.mesh_area_mm2
    passes = abs(contour_area_delta) <= area_tol and abs(mesh_area_delta) <= area_tol

    return {
        "file": str(path),
        "signature": signature,
        "threshold": threshold,
        "bin_mode": bin_mode,
        "xy_stride": xy_stride,
        "z_stride": max(1, int(z_stride)),
        "max_layers": max_layers,
        "max_vertices": max_vertices,
        "max_xy_stride": max_xy_stride,
        "pass": passes,
        "python": {
            "metrics": py_metrics.as_log_data(),
            "invariants": py_invariants.as_dict(),
            "loops": py_loops,
        },
        "cpp": {
            "metrics": cpp_metrics.as_log_data(),
            "invariants": cpp_invariants.as_dict(),
            "loops": cpp_loops,
        },
        "delta": {
            "contour_area_mm2": contour_area_delta,
            "mesh_area_mm2": mesh_area_delta,
            "contour_bbox": _bbox_delta(cpp_invariants.contour_bbox, py_invariants.contour_bbox),
            "mesh_bbox": _bbox_delta(cpp_invariants.mesh_bbox, py_invariants.mesh_bbox),
            "loops": {
                "layers": cpp_loops["layers"] - py_loops["layers"],
                "outer_loops": cpp_loops["outer_loops"] - py_loops["outer_loops"],
                "hole_loops": cpp_loops["hole_loops"] - py_loops["hole_loops"],
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare render3d python backend vs cpp backend.")
    parser.add_argument("inputs", nargs="+", help="PWMB file(s) or directory(ies).")
    parser.add_argument("--recursive", action="store_true", help="Recurse into directories.")
    parser.add_argument("--threshold", type=int, default=1, help="Binarization threshold [0..255].")
    parser.add_argument(
        "--bin-mode",
        default="index_strict",
        choices=["index_strict", "threshold"],
        help="Binarization mode.",
    )
    parser.add_argument("--xy-stride", type=int, default=1, help="XY stride.")
    parser.add_argument("--z-stride", type=int, default=1, help="Layer sampling stride on Z.")
    parser.add_argument("--max-layers", type=int, default=None, help="Optional layer budget.")
    parser.add_argument("--max-vertices", type=int, default=None, help="Optional vertex budget.")
    parser.add_argument("--max-xy-stride", type=int, default=1, help="Geometry simplification stride.")
    parser.add_argument("--area-tol", type=float, default=1e-3, help="Absolute tolerance for area deltas.")
    parser.add_argument("--output", type=Path, default=None, help="Write JSON report to this path.")
    args = parser.parse_args()

    files = _collect_pwmb_files(args.inputs, recursive=bool(args.recursive))
    report: dict[str, Any] = {
        "files_total": len(files),
        "results": [],
        "errors": [],
    }
    for path in files:
        try:
            result = _compare_case(
                path,
                threshold=max(0, min(255, int(args.threshold))),
                bin_mode=str(args.bin_mode),
                xy_stride=max(1, int(args.xy_stride)),
                z_stride=max(1, int(args.z_stride)),
                max_layers=max(1, int(args.max_layers)) if args.max_layers is not None else None,
                max_vertices=max(1, int(args.max_vertices)) if args.max_vertices is not None else None,
                max_xy_stride=max(1, int(args.max_xy_stride)),
                area_tol=max(0.0, float(args.area_tol)),
            )
            report["results"].append(result)
        except Exception as exc:
            report["errors"].append({"file": str(path), "error": f"{type(exc).__name__}: {exc}"})

    payload = json.dumps(report, indent=2, ensure_ascii=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
