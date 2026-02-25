from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

import numpy as np

from pwmb_core.lut import map_color_index_to_intensity


PW0_VARIANT_WORD16 = "word16"
PW0_VARIANT_BYTE_TOKEN = "byte_token"
Pw0Variant = Literal["word16", "byte_token"]


class Pw0DecodeError(ValueError):
    pass


def normalize_pw0_variant(variant: str | None) -> Pw0Variant:
    text = str(variant or PW0_VARIANT_WORD16).strip().lower()
    if text in {"word16", "word", "default"}:
        return PW0_VARIANT_WORD16
    if text in {"byte_token", "legacy", "byte"}:
        return PW0_VARIANT_BYTE_TOKEN
    raise Pw0DecodeError(f"Unsupported PW0 variant: {variant}")


def decode_pw0_layer(
    blob: bytes,
    width: int,
    height: int,
    lut: Sequence[int] | None = None,
    *,
    strict: bool = True,
    as_array: bool = False,
    variant: str = PW0_VARIANT_WORD16,
) -> list[int] | np.ndarray:
    if width <= 0 or height <= 0:
        raise Pw0DecodeError("Invalid PW0 dimensions")

    pixel_count = width * height
    if pixel_count <= 0:
        raise Pw0DecodeError("Invalid PW0 pixel count")

    selected = normalize_pw0_variant(variant)
    if selected == PW0_VARIANT_WORD16:
        out = _decode_word16(blob=blob, pixel_count=pixel_count, lut=lut, strict=strict)
    else:
        out = _decode_byte_token(blob=blob, pixel_count=pixel_count, lut=lut, strict=strict)

    if as_array:
        return out
    return out.tolist()


def _decode_word16(
    *,
    blob: bytes,
    pixel_count: int,
    lut: Sequence[int] | None,
    strict: bool,
) -> np.ndarray:
    out = np.zeros(pixel_count, dtype=np.uint8)
    pixel_pos = 0
    word_count = len(blob) // 2

    for word_index in range(word_count):
        if pixel_pos >= pixel_count:
            break

        offset = word_index * 2
        word = int.from_bytes(blob[offset : offset + 2], "big", signed=False)
        color_index = (word >> 12) & 0x0F
        run_len = word & 0x0FFF
        if run_len == 0:
            if strict:
                raise Pw0DecodeError(f"Invalid PW0 run length 0 at word {word_index}")
            continue

        remaining = pixel_count - pixel_pos
        applied = min(run_len, remaining)
        if applied <= 0:
            continue

        intensity = map_color_index_to_intensity(color_index, lut=lut)
        out[pixel_pos : pixel_pos + applied] = intensity
        pixel_pos += applied

    if pixel_pos != pixel_count and strict:
        raise Pw0DecodeError(
            f"PW0 layer ended before full frame decode: decoded={pixel_pos} expected={pixel_count}"
        )
    return out


def _decode_byte_token(
    *,
    blob: bytes,
    pixel_count: int,
    lut: Sequence[int] | None,
    strict: bool,
) -> np.ndarray:
    out = np.zeros(pixel_count, dtype=np.uint8)
    pixel_pos = 0
    idx = 0
    size = len(blob)

    while idx < size:
        if pixel_pos >= pixel_count:
            break
        token_index = idx
        token = blob[idx]
        idx += 1

        code = (token >> 4) & 0x0F
        repeat = token & 0x0F

        if code == 0x0:
            intensity = 0
            if idx >= size:
                if strict:
                    raise Pw0DecodeError(f"Invalid PW0 token at byte {token_index}: missing repeat low byte")
                repeat = pixel_count - pixel_pos
            else:
                repeat = (repeat << 8) + blob[idx]
                idx += 1
        elif code == 0xF:
            # Legacy PW0 stores full-white with 0xF extended-run tokens.
            intensity = 255
            if idx >= size:
                if strict:
                    raise Pw0DecodeError(f"Invalid PW0 token at byte {token_index}: missing repeat low byte")
                repeat = pixel_count - pixel_pos
            else:
                repeat = (repeat << 8) + blob[idx]
                idx += 1
        else:
            intensity = map_color_index_to_intensity(code, lut=lut)

        if repeat == 0:
            if strict:
                raise Pw0DecodeError(f"Invalid PW0 run length 0 at byte {token_index}")
            continue

        run_end = pixel_pos + int(repeat)
        if run_end > pixel_count:
            if strict:
                raise Pw0DecodeError(
                    f"PW0 token at byte {token_index} exceeds frame: run_end={run_end} expected={pixel_count}"
                )
            run_end = pixel_count
        if run_end <= pixel_pos:
            continue
        out[pixel_pos:run_end] = int(intensity) & 0xFF
        pixel_pos = run_end

    if pixel_pos != pixel_count and strict:
        raise Pw0DecodeError(
            f"PW0 layer ended before full frame decode: decoded={pixel_pos} expected={pixel_count}"
        )
    return out
