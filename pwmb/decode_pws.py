from __future__ import annotations

from collections.abc import Sequence
from enum import Enum


class PwsConvention(str, Enum):
    C0 = "C0"
    C1 = "C1"


class PwsDecodeError(ValueError):
    pass


def decode_pws_layer(
    blob: bytes,
    width: int,
    height: int,
    anti_aliasing: int,
    convention: PwsConvention | None = None,
    lut: Sequence[int] | None = None,
) -> list[int]:
    _ = (blob, width, height, anti_aliasing, convention, lut)
    raise NotImplementedError("Phase 1 skeleton: implement in phase 3")

