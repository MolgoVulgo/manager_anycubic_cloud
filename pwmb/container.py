from __future__ import annotations

from pathlib import Path

from pwmb.types import PwmbDocument


def read_pwmb_document(path: str | Path) -> PwmbDocument:
    """Phase 1 placeholder for PWMB container parsing."""
    normalized = Path(path)
    if not normalized.exists():
        raise FileNotFoundError(f"PWMB file not found: {normalized}")

    return PwmbDocument(
        path=normalized,
        version=0,
        table_addresses=[],
        layers=[],
    )

