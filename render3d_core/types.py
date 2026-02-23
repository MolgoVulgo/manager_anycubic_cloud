from __future__ import annotations

from dataclasses import dataclass, field


Point2D = tuple[float, float]
Point4D = tuple[float, float, float, float]


@dataclass(slots=True)
class LayerLoops:
    outer: list[list[Point2D]] = field(default_factory=list)
    holes: list[list[Point2D]] = field(default_factory=list)


@dataclass(slots=True)
class PwmbContourStack:
    pitch_x_mm: float
    pitch_y_mm: float
    pitch_z_mm: float
    layers: dict[int, LayerLoops] = field(default_factory=dict)


@dataclass(slots=True)
class LayerRange:
    start: int = 0
    count: int = 0


@dataclass(slots=True)
class PwmbContourGeometry:
    triangle_vertices: list[Point4D] = field(default_factory=list)
    line_vertices: list[Point4D] = field(default_factory=list)
    point_vertices: list[Point4D] = field(default_factory=list)
    tri_range: dict[int, LayerRange] = field(default_factory=dict)
    line_range: dict[int, LayerRange] = field(default_factory=dict)
    point_range: dict[int, LayerRange] = field(default_factory=dict)

