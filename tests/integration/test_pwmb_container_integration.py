from __future__ import annotations

import struct
from pathlib import Path

from pwmb_core.container import decode_layer, read_pwmb_document
from pwmb_core.export import export_layers_to_png


def _framed_table(name: str, payload: bytes) -> bytes:
    encoded_name = name.encode("ascii", errors="ignore")[:12]
    encoded_name = encoded_name + (b"\x00" * (12 - len(encoded_name)))
    return encoded_name + struct.pack("<I", len(payload)) + payload


def _align4(value: int) -> int:
    return (value + 3) & ~3


def _build_synthetic_pwmb(
    path: Path,
    *,
    layer_blob: bytes | None = None,
    non_zero_pixels: int = 3,
) -> None:
    table_count = 8

    header_payload = bytearray(52)
    struct.pack_into("<f", header_payload, 0, 50.0)
    struct.pack_into("<f", header_payload, 4, 0.05)
    struct.pack_into("<f", header_payload, 8, 2.5)
    struct.pack_into("<f", header_payload, 12, 20.0)
    struct.pack_into("<I", header_payload, 16, 4)
    struct.pack_into("<I", header_payload, 40, 4)
    struct.pack_into("<I", header_payload, 44, 2)
    struct.pack_into("<I", header_payload, 48, 2)

    machine_payload = bytearray(128)
    machine_payload[:15] = b"Photon Mono M7\x00"
    machine_payload[96:103] = b"pw0Img\x00"
    struct.pack_into("<I", machine_payload, 112, 8)

    layerdef_payload = bytearray(4 + 32)
    struct.pack_into("<I", layerdef_payload, 0, 1)  # layer count
    struct.pack_into("<f", layerdef_payload, 4 + 8, 2.5)
    struct.pack_into("<f", layerdef_payload, 4 + 20, 0.05)
    struct.pack_into("<I", layerdef_payload, 4 + 24, int(non_zero_pixels))

    lut_payload = struct.pack("<II", 1, 16) + bytes([0, 17, 34, 51, 68, 85, 102, 119, 136, 153, 170, 187, 204, 221, 238, 255]) + struct.pack("<I", 0)
    if layer_blob is None:
        layer_blob = bytes.fromhex("00011003")

    tables = [
        _framed_table("HEADER", bytes(header_payload)),
        _framed_table("SOFTWARE", b""),
        _framed_table("PREVIEW", b""),
        lut_payload,
        _framed_table("LAYERDEF", bytes(layerdef_payload)),
        _framed_table("EXTRA", b""),
        _framed_table("MACHINE", bytes(machine_payload)),
        layer_blob,
    ]

    filemark_size = 12 + 4 + 4 + (table_count * 4)
    content = bytearray(filemark_size)
    addresses: list[int] = []
    for table in tables:
        offset = _align4(len(content))
        if offset > len(content):
            content.extend(b"\x00" * (offset - len(content)))
        addresses.append(offset)
        content.extend(table)

    # Fill layer definition with absolute data pointer (table index 7).
    layerdef_addr = addresses[4]
    data_blob_addr = addresses[7]
    struct.pack_into("<I", content, layerdef_addr + 16 + 4, data_blob_addr)
    struct.pack_into("<I", content, layerdef_addr + 16 + 8, len(layer_blob))

    content[0:12] = b"ANYCUBIC" + (b"\x00" * 4)
    struct.pack_into("<I", content, 12, 516)
    struct.pack_into("<I", content, 16, table_count)
    for index, address in enumerate(addresses):
        struct.pack_into("<I", content, 20 + (index * 4), address)

    path.write_bytes(bytes(content))


def test_read_decode_and_export_synthetic_pwmb(tmp_path: Path) -> None:
    sample = tmp_path / "synthetic.pwmb"
    _build_synthetic_pwmb(sample)

    document = read_pwmb_document(sample)
    assert document.version == 516
    assert document.width == 2
    assert document.height == 2
    assert document.header.anti_aliasing == 4
    assert document.machine.layer_image_format == "pw0Img"
    assert len(document.layers) == 1
    assert document.lut[:2] == [0, 17]

    decoded = decode_layer(document, 0)
    assert decoded == [0, 17, 17, 17]

    out_dir = tmp_path / "layers"
    export_layers_to_png(document, out_dir, threshold=1)
    exported = out_dir / "layer_00000.png"
    assert exported.exists()
    payload = exported.read_bytes()
    assert payload.startswith(b"\x89PNG\r\n\x1a\n")


def test_decode_layer_pw0_byte_token_variant_fallback(tmp_path: Path) -> None:
    sample = tmp_path / "synthetic_byte_token.pwmb"
    # word16 decode fails strict completeness on this odd-size payload;
    # adaptive fallback must recover with byte_token decoding.
    _build_synthetic_pwmb(sample, layer_blob=bytes([0x00, 0x01, 0x13]), non_zero_pixels=3)

    document = read_pwmb_document(sample)
    decoded = decode_layer(document, 0, strict=True)
    assert decoded == [0, 17, 17, 17]
    assert document.pw0_variant == "byte_token"
