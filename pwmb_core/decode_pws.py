from __future__ import annotations

from collections.abc import Sequence
from enum import Enum
from typing import NamedTuple

import numpy as np


class PwsConvention(str, Enum):
    C0 = "C0"
    C1 = "C1"


class PwsDecodeError(ValueError):
    pass


class _DryRunResult(NamedTuple):
    valid: bool
    consumed: int
    residual: int
    clamp_count: int
    convention: PwsConvention
    reason: str


def select_pws_convention(blob: bytes, width: int, height: int, anti_aliasing: int) -> PwsConvention:
    if width <= 0 or height <= 0:
        raise PwsDecodeError("Invalid PWS dimensions")
    if anti_aliasing <= 0:
        raise PwsDecodeError("Invalid PWS anti-aliasing")

    c0 = _dry_run(blob, width, height, anti_aliasing, PwsConvention.C0)
    c1 = _dry_run(blob, width, height, anti_aliasing, PwsConvention.C1)

    candidates = [result for result in (c0, c1) if result.valid]
    if not candidates:
        raise PwsDecodeError(f"Unable to select PWS convention (C0={c0.reason}, C1={c1.reason})")

    best = min(
        candidates,
        key=lambda item: (
            item.clamp_count,
            item.residual,
            0 if item.convention is PwsConvention.C1 else 1,
        ),
    )
    return best.convention


def decode_pws_layer(
    blob: bytes,
    width: int,
    height: int,
    anti_aliasing: int,
    convention: PwsConvention | None = None,
    lut: Sequence[int] | None = None,
) -> list[int]:
    _ = lut
    if width <= 0 or height <= 0:
        raise PwsDecodeError("Invalid PWS dimensions")
    if anti_aliasing <= 0:
        raise PwsDecodeError("Invalid PWS anti-aliasing")

    selected = convention or select_pws_convention(blob, width, height, anti_aliasing)
    pixel_count = width * height
    if pixel_count <= 0:
        raise PwsDecodeError("Invalid PWS pixel count")

    counts = np.zeros(pixel_count, dtype=np.uint16)
    cursor = 0
    offset = 1 if selected is PwsConvention.C1 else 0

    for _pass in range(anti_aliasing):
        pixel = 0
        while pixel < pixel_count:
            if cursor >= len(blob):
                raise PwsDecodeError("PWS layer ended before full frame decode")
            token = blob[cursor]
            cursor += 1
            reps = token & 0x7F
            run_len = reps + offset
            if run_len <= 0:
                raise PwsDecodeError("PWS run length is zero")

            remaining = pixel_count - pixel
            if run_len > remaining:
                run_len = remaining

            if (token & 0x80) != 0 and run_len > 0:
                counts[pixel : pixel + run_len] += 1
            pixel += run_len

    projection = np.rint((255.0 * counts.astype(np.float64)) / float(anti_aliasing))
    return projection.astype(np.uint8).tolist()


def _dry_run(blob: bytes, width: int, height: int, anti_aliasing: int, convention: PwsConvention) -> _DryRunResult:
    pixel_count = width * height
    cursor = 0
    clamp_count = 0
    offset = 1 if convention is PwsConvention.C1 else 0

    for _pass in range(anti_aliasing):
        pixel = 0
        while pixel < pixel_count:
            if cursor >= len(blob):
                return _DryRunResult(
                    valid=False,
                    consumed=cursor,
                    residual=0,
                    clamp_count=clamp_count,
                    convention=convention,
                    reason="premature_end",
                )
            token = blob[cursor]
            cursor += 1
            reps = token & 0x7F
            run_len = reps + offset
            if run_len <= 0:
                return _DryRunResult(
                    valid=False,
                    consumed=cursor,
                    residual=0,
                    clamp_count=clamp_count,
                    convention=convention,
                    reason="run_len_zero",
                )
            remaining = pixel_count - pixel
            if run_len > remaining:
                run_len = remaining
                clamp_count += 1
            pixel += run_len

    return _DryRunResult(
        valid=True,
        consumed=cursor,
        residual=max(0, len(blob) - cursor),
        clamp_count=clamp_count,
        convention=convention,
        reason="ok",
    )
