from __future__ import annotations

from collections.abc import Sequence

from pwmb.lut import map_color_index_to_intensity


class Pw0DecodeError(ValueError):
    pass


def decode_pw0_layer(blob: bytes, width: int, height: int, lut: Sequence[int] | None = None) -> list[int]:
    if width <= 0 or height <= 0:
        raise Pw0DecodeError("Invalid PW0 dimensions")

    pixel_count = width * height
    if pixel_count <= 0:
        raise Pw0DecodeError("Invalid PW0 pixel count")

    out = bytearray(pixel_count)
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
            raise Pw0DecodeError(f"Invalid PW0 run length 0 at word {word_index}")

        remaining = pixel_count - pixel_pos
        applied = min(run_len, remaining)
        if applied <= 0:
            continue

        intensity = map_color_index_to_intensity(color_index, lut=lut)
        out[pixel_pos : pixel_pos + applied] = bytes([intensity]) * applied
        pixel_pos += applied

    if pixel_pos != pixel_count:
        raise Pw0DecodeError(
            f"PW0 layer ended before full frame decode: decoded={pixel_pos} expected={pixel_count}"
        )

    return list(out)
