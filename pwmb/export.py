from __future__ import annotations

from pathlib import Path

from pwmb.types import PwmbDocument


def export_layers_to_png(
    document: PwmbDocument,
    out_dir: str | Path,
    threshold: int | None = None,
) -> None:
    _ = (document, out_dir, threshold)
    raise NotImplementedError("Phase 1 skeleton: implement in phase 3")

