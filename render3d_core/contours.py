from __future__ import annotations

from pwmb_core.types import PwmbDocument
from render3d_core.types import PwmbContourStack


def build_contour_stack(
    document: PwmbDocument,
    threshold: int,
    binarization_mode: str = "index_strict",
) -> PwmbContourStack:
    _ = (document, threshold, binarization_mode)
    raise NotImplementedError("Phase 1 skeleton: implement in phase 3")

