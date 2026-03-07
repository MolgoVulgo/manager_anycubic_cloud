#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from pwmb_core import read_pwmb_document
from render3d_core.parallel_policy import RENDER3D_PARALLEL_POLICY_ENV, resolve_parallel_policy
from render3d_core import BuildMetrics, build_geometry_pipeline, compute_file_signature, resolve_geometry_backend
from render3d_core.invariants import build_invariant_snapshot
from render3d_core.types import PwmbContourStack


def _resolve_workers(raw_value: int | None) -> int:
    cpu_cap = max(1, int(os.cpu_count() or 1))
    if raw_value is None:
        return cpu_cap
    return max(1, min(int(raw_value), cpu_cap))


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


def _run_variant(
    *,
    document,
    signature: str,
    workers: int,
    threshold: int,
    bin_mode: str,
    xy_stride: int,
    z_stride: int,
    max_layers: int | None,
    max_vertices: int | None,
    max_xy_stride: int,
    contours_impl: str,
    opencv_approx: str,
    parallel_policy: str | None,
) -> dict[str, Any]:
    prev_impl = os.getenv("GEOM_CPP_CONTOURS_IMPL")
    prev_approx = os.getenv("GEOM_CPP_OPENCV_APPROX")
    prev_parallel_policy = os.getenv(RENDER3D_PARALLEL_POLICY_ENV)
    os.environ["GEOM_CPP_CONTOURS_IMPL"] = str(contours_impl)
    os.environ["GEOM_CPP_OPENCV_APPROX"] = str(opencv_approx)
    if parallel_policy is not None:
        os.environ[RENDER3D_PARALLEL_POLICY_ENV] = str(parallel_policy)
    try:
        backend = resolve_geometry_backend(preferred="cpp")
        effective_parallel_policy = str(resolve_parallel_policy())
        metrics = BuildMetrics(pool_kind="threads", workers=max(1, int(workers)))
        result = build_geometry_pipeline(
            document,
            threshold=threshold,
            bin_mode=bin_mode,
            xy_stride=xy_stride,
            z_stride=max(1, int(z_stride)),
            max_layers=max_layers,
            max_vertices=max_vertices,
            max_xy_stride=max_xy_stride,
            file_signature=signature,
            backend=backend,
            cache=None,
            metrics=metrics,
        )
        module = getattr(backend, "module", None)
        eff_impl = str(contours_impl)
        eff_approx = str(opencv_approx)
        getter = getattr(module, "current_contours_impl", None)
        if callable(getter):
            try:
                eff_impl = str(getter())
            except Exception:
                eff_impl = str(contours_impl)
        approx_getter = getattr(module, "current_opencv_approx", None)
        if callable(approx_getter):
            try:
                eff_approx = str(approx_getter())
            except Exception:
                eff_approx = str(opencv_approx)
        return {
            "metrics": metrics,
            "contour_stack": result.contour_stack,
            "geometry": result.geometry,
            "contours_impl_effective": eff_impl,
            "opencv_approx_effective": eff_approx,
            "parallel_policy_effective": effective_parallel_policy,
        }
    finally:
        if prev_impl is None:
            os.environ.pop("GEOM_CPP_CONTOURS_IMPL", None)
        else:
            os.environ["GEOM_CPP_CONTOURS_IMPL"] = prev_impl
        if prev_approx is None:
            os.environ.pop("GEOM_CPP_OPENCV_APPROX", None)
        else:
            os.environ["GEOM_CPP_OPENCV_APPROX"] = prev_approx
        if parallel_policy is not None:
            if prev_parallel_policy is None:
                os.environ.pop(RENDER3D_PARALLEL_POLICY_ENV, None)
            else:
                os.environ[RENDER3D_PARALLEL_POLICY_ENV] = prev_parallel_policy


def _compare_case(
    path: Path,
    *,
    workers: int,
    threshold: int,
    bin_mode: str,
    xy_stride: int,
    z_stride: int,
    max_layers: int | None,
    max_vertices: int | None,
    max_xy_stride: int,
    area_tol: float,
    candidate_contours_impl: str,
    candidate_opencv_approx: str,
    parallel_policy: str | None,
) -> dict[str, Any]:
    signature = compute_file_signature(path)
    document = read_pwmb_document(path)

    baseline = _run_variant(
        document=document,
        signature=signature,
        workers=workers,
        threshold=threshold,
        bin_mode=bin_mode,
        xy_stride=xy_stride,
        z_stride=z_stride,
        max_layers=max_layers,
        max_vertices=max_vertices,
        max_xy_stride=max_xy_stride,
        contours_impl="native",
        opencv_approx="simple",
        parallel_policy=parallel_policy,
    )
    candidate = _run_variant(
        document=document,
        signature=signature,
        workers=workers,
        threshold=threshold,
        bin_mode=bin_mode,
        xy_stride=xy_stride,
        z_stride=z_stride,
        max_layers=max_layers,
        max_vertices=max_vertices,
        max_xy_stride=max_xy_stride,
        contours_impl=candidate_contours_impl,
        opencv_approx=candidate_opencv_approx,
        parallel_policy=parallel_policy,
    )

    baseline_inv = build_invariant_snapshot(baseline["contour_stack"], baseline["geometry"])
    candidate_inv = build_invariant_snapshot(candidate["contour_stack"], candidate["geometry"])
    baseline_loops = _loops_summary(baseline["contour_stack"])
    candidate_loops = _loops_summary(candidate["contour_stack"])

    contour_area_delta = candidate_inv.contour_area_mm2 - baseline_inv.contour_area_mm2
    mesh_area_delta = candidate_inv.mesh_area_mm2 - baseline_inv.mesh_area_mm2
    passes = abs(contour_area_delta) <= area_tol and abs(mesh_area_delta) <= area_tol

    return {
        "file": str(path),
        "signature": signature,
        "threshold": threshold,
        "bin_mode": bin_mode,
        "xy_stride": xy_stride,
        "z_stride": max(1, int(z_stride)),
        "workers": int(workers),
        "max_layers": max_layers,
        "max_vertices": max_vertices,
        "max_xy_stride": max_xy_stride,
        "candidate_contours_impl_requested": str(candidate_contours_impl),
        "candidate_opencv_approx_requested": str(candidate_opencv_approx),
        "parallel_policy_requested": str(parallel_policy) if parallel_policy is not None else None,
        "parallel_policy_effective": str(candidate.get("parallel_policy_effective")),
        "candidate_contours_impl_effective": str(candidate["contours_impl_effective"]),
        "candidate_opencv_approx_effective": str(candidate["opencv_approx_effective"]),
        "pass": passes,
        "cpp_native": {
            "metrics": baseline["metrics"].as_log_data(),
            "invariants": baseline_inv.as_dict(),
            "loops": baseline_loops,
        },
        "cpp_candidate": {
            "metrics": candidate["metrics"].as_log_data(),
            "invariants": candidate_inv.as_dict(),
            "loops": candidate_loops,
        },
        "delta": {
            "contour_area_mm2": contour_area_delta,
            "mesh_area_mm2": mesh_area_delta,
            "contour_bbox": _bbox_delta(candidate_inv.contour_bbox, baseline_inv.contour_bbox),
            "mesh_bbox": _bbox_delta(candidate_inv.mesh_bbox, baseline_inv.mesh_bbox),
            "loops": {
                "layers": candidate_loops["layers"] - baseline_loops["layers"],
                "outer_loops": candidate_loops["outer_loops"] - baseline_loops["outer_loops"],
                "hole_loops": candidate_loops["hole_loops"] - baseline_loops["hole_loops"],
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare render3d cpp native baseline vs cpp candidate variant.")
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
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Worker count for per-layer parallel stages (default: max available CPUs).",
    )
    parser.add_argument(
        "--candidate-contours-impl",
        default="opencv",
        choices=["native", "opencv", "auto"],
        help="Candidate C++ contour implementation selector.",
    )
    parser.add_argument(
        "--candidate-opencv-approx",
        default="simple",
        choices=["simple", "tc89_l1", "tc89_kcos"],
        help="Candidate OpenCV contour approximation mode.",
    )
    parser.add_argument(
        "--parallel-policy",
        default=None,
        choices=["python_fanout", "cpp_internal", "auto"],
        help="Parallel policy override (RENDER3D_PARALLEL_POLICY).",
    )
    parser.add_argument("--area-tol", type=float, default=1e-3, help="Absolute tolerance for area deltas.")
    parser.add_argument("--output", type=Path, default=None, help="Write JSON report to this path.")
    args = parser.parse_args()

    workers = _resolve_workers(args.workers)
    if args.parallel_policy is None:
        parallel_policy_effective = str(resolve_parallel_policy())
    else:
        requested_policy = str(args.parallel_policy).strip().lower()
        parallel_policy_effective = "python_fanout" if requested_policy in {"", "auto"} else requested_policy
    files = _collect_pwmb_files(args.inputs, recursive=bool(args.recursive))
    report: dict[str, Any] = {
        "workers_requested": int(args.workers) if args.workers is not None else None,
        "workers_effective": workers,
        "parallel_policy_requested": str(args.parallel_policy) if args.parallel_policy is not None else None,
        "parallel_policy_effective": parallel_policy_effective,
        "files_total": len(files),
        "results": [],
        "errors": [],
    }
    for path in files:
        try:
            result = _compare_case(
                path,
                workers=workers,
                threshold=max(0, min(255, int(args.threshold))),
                bin_mode=str(args.bin_mode),
                xy_stride=max(1, int(args.xy_stride)),
                z_stride=max(1, int(args.z_stride)),
                max_layers=max(1, int(args.max_layers)) if args.max_layers is not None else None,
                max_vertices=max(1, int(args.max_vertices)) if args.max_vertices is not None else None,
                max_xy_stride=max(1, int(args.max_xy_stride)),
                area_tol=max(0.0, float(args.area_tol)),
                candidate_contours_impl=str(args.candidate_contours_impl),
                candidate_opencv_approx=str(args.candidate_opencv_approx),
                parallel_policy=str(args.parallel_policy) if args.parallel_policy is not None else None,
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
