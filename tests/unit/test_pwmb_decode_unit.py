from __future__ import annotations

import pytest

from pwmb_core.decode_pw0 import Pw0DecodeError, decode_pw0_layer
from pwmb_core.decode_pws import PwsConvention, PwsDecodeError, decode_pws_layer, select_pws_convention
from pwmb_core.lut import map_color_index_to_intensity, parse_layer_image_color_table


def _pw0_word(color_index: int, run_len: int) -> bytes:
    value = ((color_index & 0x0F) << 12) | (run_len & 0x0FFF)
    return value.to_bytes(2, "big", signed=False)


def test_decode_pw0_big_endian_and_lut_mapping() -> None:
    blob = _pw0_word(0, 1) + _pw0_word(2, 2) + _pw0_word(15, 1)
    lut = [200] * 16
    lut[0] = 123  # must still decode as empty
    lut[2] = 50
    lut[15] = 201

    decoded = decode_pw0_layer(blob=blob, width=4, height=1, lut=lut)
    assert decoded == [0, 50, 50, 201]


def test_decode_pw0_rejects_zero_run() -> None:
    blob = _pw0_word(1, 0)
    with pytest.raises(Pw0DecodeError):
        _ = decode_pw0_layer(blob=blob, width=1, height=1)


def test_decode_pw0_clamps_and_ignores_trailing_words() -> None:
    blob = _pw0_word(3, 6) + _pw0_word(4, 1)
    decoded = decode_pw0_layer(blob=blob, width=5, height=1)
    assert decoded == [51, 51, 51, 51, 51]


def test_decode_pw0_rejects_short_frame() -> None:
    blob = _pw0_word(1, 2)
    with pytest.raises(Pw0DecodeError):
        _ = decode_pw0_layer(blob=blob, width=4, height=1)


def test_select_pws_convention_prefers_valid_candidate() -> None:
    convention = select_pws_convention(blob=bytes([0x83]), width=4, height=1, anti_aliasing=1)
    assert convention is PwsConvention.C1


def test_decode_pws_anti_aliasing_projection() -> None:
    # Pass 1: 2 exposed then 2 empty
    # Pass 2: 1 exposed then 3 empty
    blob = bytes([0x81, 0x01, 0x80, 0x02])
    decoded = decode_pws_layer(
        blob=blob,
        width=4,
        height=1,
        anti_aliasing=2,
        convention=PwsConvention.C1,
    )
    assert decoded == [255, 128, 0, 0]


def test_decode_pws_rejects_zero_run_when_c0_forced() -> None:
    with pytest.raises(PwsDecodeError):
        _ = decode_pws_layer(
            blob=bytes([0x00]),
            width=1,
            height=1,
            anti_aliasing=1,
            convention=PwsConvention.C0,
        )


def test_decode_pws_rejects_invalid_aa() -> None:
    with pytest.raises(PwsDecodeError):
        _ = decode_pws_layer(
            blob=bytes([0x80]),
            width=1,
            height=1,
            anti_aliasing=0,
            convention=PwsConvention.C1,
        )


def test_lut_index_zero_semantics_and_table_parsing() -> None:
    lut_payload = (1).to_bytes(4, "little") + (4).to_bytes(4, "little") + bytes([15, 17, 33, 255]) + b"\x00\x00\x00\x00"
    lut = parse_layer_image_color_table(lut_payload)
    assert lut == [15, 17, 33, 255]
    assert map_color_index_to_intensity(0, lut=lut) == 0
    assert map_color_index_to_intensity(2, lut=lut) == 33
