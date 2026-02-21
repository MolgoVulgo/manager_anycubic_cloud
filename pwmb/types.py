from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class HeaderInfo:
    pixel_size_um: float = 0.0
    layer_height_mm: float = 0.0
    exposure_time_s: float = 0.0
    bottom_exposure_time_s: float = 0.0
    bottom_layers_count: int = 0
    anti_aliasing: int = 1
    resolution_x: int = 0
    resolution_y: int = 0


@dataclass(slots=True)
class MachineInfo:
    machine_name: str = ""
    layer_image_format: str = "unknown"
    max_antialiasing_level: int = 1


@dataclass(slots=True)
class LayerDef:
    index: int
    data_address: int
    data_length: int
    exposure_time_s: float | None = None
    layer_height_mm: float | None = None
    non_zero_pixel_count: int | None = None


@dataclass(slots=True)
class PwmbDocument:
    path: Path
    version: int
    header: HeaderInfo = field(default_factory=HeaderInfo)
    machine: MachineInfo = field(default_factory=MachineInfo)
    layers: list[LayerDef] = field(default_factory=list)
    table_addresses: list[int] = field(default_factory=list)

    @property
    def width(self) -> int:
        return self.header.resolution_x

    @property
    def height(self) -> int:
        return self.header.resolution_y

    @property
    def pixel_count(self) -> int:
        return self.width * self.height

