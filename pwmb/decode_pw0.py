from __future__ import annotations

from collections.abc import Sequence


class Pw0DecodeError(ValueError):
    pass


def decode_pw0_layer(blob: bytes, width: int, height: int, lut: Sequence[int] | None = None) -> list[int]:
    _ = (blob, width, height, lut)
    raise NotImplementedError("Phase 1 skeleton: implement in phase 3")

