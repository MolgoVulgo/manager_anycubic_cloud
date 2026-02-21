from __future__ import annotations

from pwmb.types import HeaderInfo, LayerDef, MachineInfo


def parse_header_table(payload: bytes) -> HeaderInfo:
    _ = payload
    return HeaderInfo()


def parse_machine_table(payload: bytes) -> MachineInfo:
    _ = payload
    return MachineInfo()


def parse_layerdef_table(payload: bytes) -> list[LayerDef]:
    _ = payload
    return []

