from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class AppState:
    is_busy: bool = False
    active_stage: str = "idle"
    progress_percent: int = 0
    last_error: str | None = None
    selected_file_id: str | None = None
    selected_printer_id: str | None = None
    runtime_flags: dict[str, str] = field(default_factory=dict)

