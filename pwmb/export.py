from __future__ import annotations

from pathlib import Path
import struct
import zlib

from pwmb.container import decode_layer
from pwmb.types import PwmbDocument


def export_layers_to_png(
    document: PwmbDocument,
    out_dir: str | Path,
    threshold: int | None = None,
) -> None:
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)

    width = document.width
    height = document.height
    pixel_count = width * height
    if pixel_count <= 0:
        raise ValueError("PWMB document has invalid dimensions")

    digits = max(5, len(str(len(document.layers))))
    for layer_index, _layer in enumerate(document.layers):
        try:
            decoded = decode_layer(document, layer_index, threshold=threshold)
        except Exception:
            decoded = [0] * pixel_count
        output = target / f"layer_{layer_index:0{digits}d}.png"
        _write_grayscale_png(output, width=width, height=height, pixels=decoded)


def _write_grayscale_png(path: Path, *, width: int, height: int, pixels: list[int]) -> None:
    expected = width * height
    if len(pixels) != expected:
        raise ValueError(f"Invalid pixel payload length: expected={expected} got={len(pixels)}")
    if width <= 0 or height <= 0:
        raise ValueError("Invalid PNG dimensions")

    scanlines = bytearray()
    for row in range(height):
        start = row * width
        end = start + width
        scanlines.append(0)  # filter method 0
        scanlines.extend(int(value) & 0xFF for value in pixels[start:end])

    compressed = zlib.compress(bytes(scanlines), level=9)
    with path.open("wb") as handle:
        handle.write(b"\x89PNG\r\n\x1a\n")
        _write_png_chunk(
            handle,
            b"IHDR",
            struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0),
        )
        _write_png_chunk(handle, b"IDAT", compressed)
        _write_png_chunk(handle, b"IEND", b"")


def _write_png_chunk(handle, chunk_type: bytes, payload: bytes) -> None:
    handle.write(struct.pack(">I", len(payload)))
    handle.write(chunk_type)
    handle.write(payload)
    crc = zlib.crc32(chunk_type)
    crc = zlib.crc32(payload, crc)
    handle.write(struct.pack(">I", crc & 0xFFFFFFFF))
