from __future__ import annotations

import logging
import mmap
import re
import struct
from pathlib import Path
import hashlib

import numpy as np

from accloud_core.logging_contract import emit_event, get_op_id
from pwmb_core.decode_pw0 import decode_pw0_layer
from pwmb_core.decode_pws import PwsConvention, decode_pws_layer, select_pws_convention
from pwmb_core.lut import parse_layer_image_color_table
from pwmb_core.structs import parse_header_table, parse_layerdef_table, parse_machine_table
from pwmb_core.types import PwmbDocument


LOGGER_PARSE = logging.getLogger("pwmb.parse")
LOGGER_DECODE = logging.getLogger("pwmb.decode")


def read_pwmb_document(path: str | Path) -> PwmbDocument:
    normalized = Path(path)
    op_id = get_op_id()
    if not normalized.exists():
        error = FileNotFoundError(f"PWMB file not found: {normalized}")
        emit_event(
            LOGGER_PARSE,
            logging.ERROR,
            event="pwmb.open_fail",
            msg="PWMB file open failed",
            component="pwmb.parse",
            op_id=op_id,
            data={"pwmb": {"pwmb_path_hash": _path_hash(normalized)}},
            error={"type": type(error).__name__, "message": str(error)},
        )
        raise error
    if not normalized.is_file():
        error = ValueError(f"PWMB path is not a file: {normalized}")
        emit_event(
            LOGGER_PARSE,
            logging.ERROR,
            event="pwmb.open_fail",
            msg="PWMB path is not a file",
            component="pwmb.parse",
            op_id=op_id,
            data={"pwmb": {"pwmb_path_hash": _path_hash(normalized)}},
            error={"type": type(error).__name__, "message": str(error)},
        )
        raise error

    file_size = normalized.stat().st_size
    if file_size <= 0:
        error = ValueError("PWMB file is empty")
        emit_event(
            LOGGER_PARSE,
            logging.ERROR,
            event="pwmb.open_fail",
            msg="PWMB file is empty",
            component="pwmb.parse",
            op_id=op_id,
            data={"pwmb": {"pwmb_path_hash": _path_hash(normalized)}},
            error={"type": type(error).__name__, "message": str(error)},
        )
        raise error

    with normalized.open("rb") as handle:
        data = mmap.mmap(handle.fileno(), length=0, access=mmap.ACCESS_READ)
        try:
            version, table_addresses = _parse_filemark(data)
            framed_tables = _discover_framed_tables(data, table_addresses)

            header_payload = _select_framed_or_index_payload(
                data=data,
                table_addresses=table_addresses,
                framed_tables=framed_tables,
                table_name="HEADER",
                fallback_index=0,
                file_size=file_size,
            )
            if not header_payload:
                raise ValueError("PWMB header table is missing")

            machine_payload = _select_framed_or_index_payload(
                data=data,
                table_addresses=table_addresses,
                framed_tables=framed_tables,
                table_name="MACHINE",
                fallback_index=6,
                file_size=file_size,
            )
            layerdef_payload = _select_framed_or_index_payload(
                data=data,
                table_addresses=table_addresses,
                framed_tables=framed_tables,
                table_name="LAYERDEF",
                fallback_index=4,
                file_size=file_size,
            )
            if not layerdef_payload:
                raise ValueError("PWMB layer definition table is missing")

            lut_payload = _select_lut_payload(
                data=data,
                table_addresses=table_addresses,
                framed_tables=framed_tables,
                file_size=file_size,
            )
        finally:
            data.close()

    try:
        header = parse_header_table(header_payload)
        if header.resolution_x <= 0 or header.resolution_y <= 0:
            raise ValueError("PWMB header has invalid resolution")

        machine = parse_machine_table(machine_payload)
        if machine.layer_image_format == "unknown":
            machine.layer_image_format = "pw0Img"

        layers = parse_layerdef_table(layerdef_payload)
        if not layers:
            raise ValueError("PWMB file has no layers")

        # Keep layer entries parseable even if some are invalid (per-layer policy).
        for layer in layers:
            if layer.data_address < 0:
                layer.data_address = 0
                layer.data_length = 0
                continue
            if layer.data_length <= 0:
                layer.data_length = 0
                continue
            if layer.data_address >= file_size or layer.data_address + layer.data_length > file_size:
                layer.data_length = 0

        document = PwmbDocument(
            path=normalized,
            version=version,
            file_size=file_size,
            header=header,
            machine=machine,
            layers=layers,
            table_addresses=table_addresses,
            lut=parse_layer_image_color_table(lut_payload),
        )
    except Exception as exc:
        emit_event(
            LOGGER_PARSE,
            logging.ERROR,
            event="pwmb.open_fail",
            msg="PWMB parsing failed",
            component="pwmb.parse",
            op_id=op_id,
            data={"pwmb": {"pwmb_path_hash": _path_hash(normalized)}},
            error={"type": type(exc).__name__, "message": str(exc)},
        )
        raise

    emit_event(
        LOGGER_PARSE,
        logging.INFO,
        event="pwmb.open_ok",
        msg="PWMB opened successfully",
        component="pwmb.parse",
        op_id=op_id,
        data={
            "pwmb": {
                "pwmb_path_hash": _path_hash(normalized),
                "W": document.width,
                "H": document.height,
                "aa": document.header.anti_aliasing,
            }
        },
    )
    return document


def decode_layer(
    document: PwmbDocument,
    layer_index: int,
    *,
    threshold: int | None = None,
    convention: PwsConvention | None = None,
    strict: bool = True,
    as_array: bool = False,
) -> list[int] | np.ndarray:
    op_id = get_op_id()
    if layer_index < 0 or layer_index >= len(document.layers):
        error = IndexError(f"Layer index out of range: {layer_index}")
        emit_event(
            LOGGER_DECODE,
            logging.ERROR,
            event="pwmb.decode_layer_fail",
            msg="Layer index out of range",
            component="pwmb.decode",
            op_id=op_id,
            data={"pwmb": {"layer_index": layer_index, "W": document.width, "H": document.height}},
            error={"type": type(error).__name__, "message": str(error)},
        )
        raise error
    if document.width <= 0 or document.height <= 0:
        error = ValueError("PWMB document has invalid resolution")
        emit_event(
            LOGGER_DECODE,
            logging.ERROR,
            event="pwmb.decode_layer_fail",
            msg="PWMB document has invalid resolution",
            component="pwmb.decode",
            op_id=op_id,
            data={"pwmb": {"layer_index": layer_index, "W": document.width, "H": document.height}},
            error={"type": type(error).__name__, "message": str(error)},
        )
        raise error

    try:
        layer = document.layers[layer_index]
        pixel_count = document.pixel_count
        if layer.data_length <= 0:
            decoded: list[int] | np.ndarray
            if as_array:
                decoded = np.zeros(pixel_count, dtype=np.uint8)
            else:
                decoded = [0] * pixel_count
            output = _apply_threshold(decoded, threshold, as_array=as_array)
            emit_event(
                LOGGER_DECODE,
                logging.DEBUG,
                event="pwmb.decode_layer_ok",
                msg="PWMB layer decoded (empty layer payload)",
                component="pwmb.decode",
                op_id=op_id,
                data={
                    "pwmb": {
                        "layer_index": layer_index,
                        "W": document.width,
                        "H": document.height,
                        "aa": max(1, document.header.anti_aliasing),
                        "decoder": document.machine.layer_image_format,
                    }
                },
            )
            return output

        with document.path.open("rb") as handle:
            handle.seek(layer.data_address)
            blob = handle.read(layer.data_length)
        if len(blob) != layer.data_length:
            raise ValueError(f"Unable to read complete layer payload: layer={layer_index}")

        format_name = document.machine.layer_image_format.lower()
        if "pws" in format_name:
            selected_convention = convention
            if selected_convention is None and document.pws_convention:
                selected_convention = PwsConvention(document.pws_convention)
            if selected_convention is None:
                selected_convention = select_pws_convention(
                    blob=blob,
                    width=document.width,
                    height=document.height,
                    anti_aliasing=max(1, document.header.anti_aliasing),
                )
                document.pws_convention = selected_convention.value
            decoded = decode_pws_layer(
                blob=blob,
                width=document.width,
                height=document.height,
                anti_aliasing=max(1, document.header.anti_aliasing),
                convention=selected_convention,
                lut=document.lut,
                as_array=as_array,
            )
            decoder_name = f"pws:{selected_convention.value}"
        elif "pw0" in format_name:
            decoded = decode_pw0_layer(
                blob=blob,
                width=document.width,
                height=document.height,
                lut=document.lut,
                strict=strict,
                as_array=as_array,
            )
            decoder_name = "pw0"
        else:
            raise ValueError(f"Unsupported PWMB layer format: {document.machine.layer_image_format}")

        output = _apply_threshold(decoded, threshold, as_array=as_array)
        emit_event(
            LOGGER_DECODE,
            logging.DEBUG,
            event="pwmb.decode_layer_ok",
            msg="PWMB layer decoded",
            component="pwmb.decode",
            op_id=op_id,
            data={
                "pwmb": {
                    "layer_index": layer_index,
                    "W": document.width,
                    "H": document.height,
                    "aa": max(1, document.header.anti_aliasing),
                    "decoder": decoder_name,
                }
            },
        )
        return output
    except Exception as exc:
        emit_event(
            LOGGER_DECODE,
            logging.ERROR,
            event="pwmb.decode_layer_fail",
            msg="PWMB layer decoding failed",
            component="pwmb.decode",
            op_id=op_id,
            data={"pwmb": {"layer_index": layer_index, "W": document.width, "H": document.height}},
            error={"type": type(exc).__name__, "message": str(exc)},
        )
        raise


def _parse_filemark(data: mmap.mmap) -> tuple[int, list[int]]:
    minimum = 12 + 4 + 4
    if len(data) < minimum:
        raise ValueError("PWMB file is too small for FILEMARK")

    mark = bytes(data[0:12]).rstrip(b"\x00")
    if not mark.startswith(b"ANYCUBIC"):
        raise ValueError("Invalid PWMB signature")

    version = _read_u32(data, 12)
    table_count = _read_u32(data, 16)
    if table_count <= 0 or table_count > 64:
        raise ValueError(f"Invalid PWMB table count: {table_count}")

    addresses_offset = 20
    required = addresses_offset + table_count * 4
    if required > len(data):
        raise ValueError("PWMB FILEMARK table addresses exceed file bounds")

    table_addresses: list[int] = []
    for index in range(table_count):
        address = _read_u32(data, addresses_offset + (index * 4))
        if address < 0 or address >= len(data):
            if address == 0:
                table_addresses.append(0)
                continue
            raise ValueError(f"PWMB table address out of bounds at index {index}: {address}")
        table_addresses.append(address)

    return version, table_addresses


def _discover_framed_tables(data: mmap.mmap, table_addresses: list[int]) -> dict[str, bytes]:
    tables: dict[str, bytes] = {}
    seen_offsets: set[int] = set()
    for address in table_addresses:
        if address in seen_offsets or address <= 0:
            continue
        seen_offsets.add(address)
        result = _read_framed_table(data, address)
        if result is None:
            continue
        table_name, payload = result
        if table_name not in tables:
            tables[table_name] = payload
    return tables


def _select_framed_or_index_payload(
    *,
    data: mmap.mmap,
    table_addresses: list[int],
    framed_tables: dict[str, bytes],
    table_name: str,
    fallback_index: int,
    file_size: int,
) -> bytes:
    direct = framed_tables.get(table_name.upper())
    if direct is not None:
        return direct
    return _slice_table_payload_by_index(
        data=data,
        table_addresses=table_addresses,
        index=fallback_index,
        file_size=file_size,
    )


def _select_lut_payload(
    *,
    data: mmap.mmap,
    table_addresses: list[int],
    framed_tables: dict[str, bytes],
    file_size: int,
) -> bytes:
    for table_name, payload in framed_tables.items():
        if "COLOR" in table_name or "LUT" in table_name:
            return payload

    # v516 typical fallback index for LayerImageColorTable.
    return _slice_table_payload_by_index(
        data=data,
        table_addresses=table_addresses,
        index=3,
        file_size=file_size,
        max_len=1024,
    )


def _slice_table_payload_by_index(
    *,
    data: mmap.mmap,
    table_addresses: list[int],
    index: int,
    file_size: int,
    max_len: int | None = None,
) -> bytes:
    if index < 0 or index >= len(table_addresses):
        return b""
    start = table_addresses[index]
    if start <= 0 or start >= file_size:
        return b""

    framed = _read_framed_table(data, start)
    if framed is not None:
        return framed[1]

    end_candidates = [addr for addr in table_addresses if addr > start]
    end = min(end_candidates) if end_candidates else file_size
    if end <= start:
        return b""
    if max_len is not None:
        end = min(end, start + max_len)
    return bytes(data[start:end])


def _read_framed_table(data: mmap.mmap, address: int) -> tuple[str, bytes] | None:
    if address < 0 or address + 16 > len(data):
        return None

    raw_name = bytes(data[address : address + 12])
    table_name = raw_name.split(b"\x00", 1)[0].decode("ascii", errors="ignore").strip().upper()
    if not _looks_like_table_name(table_name):
        return None

    payload_length = _read_u32(data, address + 12)
    payload_start = address + 16
    payload_end = payload_start + payload_length
    if payload_end > len(data):
        return None

    return table_name, bytes(data[payload_start:payload_end])


def _looks_like_table_name(name: str) -> bool:
    if len(name) < 3 or len(name) > 12:
        return False
    return bool(re.fullmatch(r"[A-Z0-9_]+", name))


def _read_u32(data: mmap.mmap, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _apply_threshold(
    values: list[int] | np.ndarray,
    threshold: int | None,
    *,
    as_array: bool,
) -> list[int] | np.ndarray:
    if threshold is None:
        if as_array:
            if isinstance(values, np.ndarray):
                return values
            return np.asarray(values, dtype=np.uint8)
        if isinstance(values, np.ndarray):
            return values.tolist()
        return values

    limit = max(0, min(255, int(threshold)))
    arr = values if isinstance(values, np.ndarray) else np.asarray(values, dtype=np.uint8)
    thresholded = np.where(arr >= limit, 255, 0).astype(np.uint8, copy=False)
    if as_array:
        return thresholded
    return thresholded.tolist()


def _path_hash(path: Path) -> str:
    return hashlib.sha256(str(path).encode("utf-8")).hexdigest()
