from __future__ import annotations

from pwmb.types import PwmbDocument
from pwmb3d.types import PwmbContourStack


def build_contour_stack(
    document: PwmbDocument,
    threshold: int,
    binarization_mode: str = "index_strict",
) -> PwmbContourStack:
    _ = (document, threshold, binarization_mode)
    raise NotImplementedError("Phase 1 skeleton: implement in phase 3")

