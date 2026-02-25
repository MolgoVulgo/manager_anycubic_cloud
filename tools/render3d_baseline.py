#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter

from pwmb_core import read_pwmb_document
from render3d_core import BuildMetrics, build_geometry_pipeline, compute_file_signature, resolve_geometry_backend
from render3d_core.invariants import build_invariant_snapshot


def _select_preview_xy_stride(*, width: int, height: int) -> int:
    pixels = max(0, int(width)) * max(0, int(height))
    if pixels >= 24_000_000:
        return 6
    if pixels >= 12_000_000:
        return 4
    if pixels >= 6_000_000:
        return 3
    if pixels >= 2_500_000:
        return 2
    return 1


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


def _run_case(
    pwmb_path: Path,
    *,
    backend_name: str,
    threshold: int,
    bin_mode: str,
    xy_stride: int | None,
    z_stride: int,
    max_layers: int | None,
    max_vertices: int | None,
    max_xy_stride: int,
) -> dict[str, object]:
    metrics = BuildMetrics(pool_kind="threads", workers=1)
    parse_start = perf_counter()
    document = read_pwmb_document(pwmb_path)
    metrics.parse_ms = (perf_counter() - parse_start) * 1000.0

    backend = resolve_geometry_backend(preferred=backend_name)
    signature = compute_file_signature(pwmb_path)
    effective_xy_stride = xy_stride or _select_preview_xy_stride(width=document.width, height=document.height)
    build_result = build_geometry_pipeline(
        document,
        threshold=threshold,
        bin_mode=bin_mode,
        xy_stride=effective_xy_stride,
        z_stride=max(1, int(z_stride)),
        max_layers=max_layers,
        max_vertices=max_vertices,
        max_xy_stride=max_xy_stride,
        file_signature=signature,
        backend=backend,
        cache=None,
        metrics=metrics,
    )
    contour_stack = build_result.contour_stack
    geometry = build_result.geometry

    buffer_start = perf_counter()
    _ = (
        len(geometry.triangle_vertices) * 16
        + len(geometry.line_vertices) * 16
        + len(geometry.point_vertices) * 16
    )
    metrics.buffers_ms_total += (perf_counter() - buffer_start) * 1000.0

    invariants = build_invariant_snapshot(contour_stack, geometry)
    payload = {
        "file": str(pwmb_path),
        "file_signature": signature,
        "backend": build_result.backend_name,
        "threshold": int(threshold),
        "bin_mode": bin_mode,
        "xy_stride": int(effective_xy_stride),
        "z_stride": max(1, int(z_stride)),
        "max_layers": int(max_layers) if max_layers is not None else None,
        "max_vertices": int(max_vertices) if max_vertices is not None else None,
        "max_xy_stride": int(max_xy_stride),
        "metrics": metrics.as_log_data(),
        "invariants": invariants.as_dict(),
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Baseline render3d build metrics + geometric invariants for a PWMB corpus.",
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="PWMB file(s) or directory(ies).",
    )
    parser.add_argument("--recursive", action="store_true", help="Recurse into directories.")
    parser.add_argument("--backend", default="python", choices=["python", "cpp"], help="Geometry backend.")
    parser.add_argument("--threshold", type=int, default=1, help="Binarization threshold [0..255].")
    parser.add_argument(
        "--bin-mode",
        default="index_strict",
        choices=["index_strict", "threshold"],
        help="Binarization mode.",
    )
    parser.add_argument("--xy-stride", type=int, default=None, help="Force XY stride (default: auto profile).")
    parser.add_argument("--z-stride", type=int, default=1, help="Layer sampling stride on Z.")
    parser.add_argument("--max-layers", type=int, default=None, help="Optional layer budget.")
    parser.add_argument("--max-vertices", type=int, default=None, help="Optional vertex budget.")
    parser.add_argument("--max-xy-stride", type=int, default=1, help="Geometry simplification stride.")
    parser.add_argument("--output", type=Path, default=None, help="Write JSON report to this path.")
    args = parser.parse_args()

    files = _collect_pwmb_files(args.inputs, recursive=bool(args.recursive))
    report: dict[str, object] = {
        "backend_requested": args.backend,
        "files_total": len(files),
        "results": [],
        "errors": [],
    }
    if not files:
        report["errors"] = [{"input": entry, "error": "no_pwmb_found"} for entry in args.inputs]
    else:
        results: list[dict[str, object]] = []
        errors: list[dict[str, str]] = []
        for file_path in files:
            try:
                result = _run_case(
                    file_path,
                    backend_name=args.backend,
                    threshold=max(0, min(255, int(args.threshold))),
                    bin_mode=str(args.bin_mode),
                    xy_stride=max(1, int(args.xy_stride)) if args.xy_stride is not None else None,
                    z_stride=max(1, int(args.z_stride)),
                    max_layers=max(1, int(args.max_layers)) if args.max_layers is not None else None,
                    max_vertices=max(1, int(args.max_vertices)) if args.max_vertices is not None else None,
                    max_xy_stride=max(1, int(args.max_xy_stride)),
                )
            except Exception as exc:
                errors.append({"file": str(file_path), "error": f"{type(exc).__name__}: {exc}"})
                continue
            results.append(result)
        report["results"] = results
        report["errors"] = errors

    payload = json.dumps(report, indent=2, ensure_ascii=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
