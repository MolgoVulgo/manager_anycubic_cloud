from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Quota:
    total_bytes: int
    used_bytes: int
    free_bytes: int
    used_percent: float


@dataclass(slots=True)
class FileItem:
    file_id: str
    name: str
    size_bytes: int
    created_at: str | None = None
    updated_at: str | None = None
    status: str | None = None


@dataclass(slots=True)
class GcodeInfo:
    layers: int | None = None
    print_time_s: int | None = None
    resin_volume_ml: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Printer:
    printer_id: str
    name: str
    online: bool
    state: str | None = None


@dataclass(slots=True)
class SessionData:
    cookies: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    tokens: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def auth_headers(self) -> dict[str, str]:
        merged = dict(self.headers)
        merged.update(self.tokens)
        return merged

