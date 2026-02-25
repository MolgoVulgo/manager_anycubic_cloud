from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import threading

from pwmb_core.types import PwmbDocument
from render3d_core.types import PwmbContourGeometry, PwmbContourStack


@dataclass(frozen=True, slots=True)
class CacheKey:
    file_signature: str
    pwmb_version: int
    decoder_kind: str
    pws_convention: str | None
    lut_signature: str
    threshold: int
    bin_mode: str
    xy_stride: int
    z_stride: int
    simplify_epsilon: float
    max_layers: int
    max_vertices: int
    render_mode: str


class BuildCache:
    def __init__(self) -> None:
        self._contours: dict[CacheKey, PwmbContourStack] = {}
        self._geometry: dict[CacheKey, PwmbContourGeometry] = {}
        self._lock = threading.RLock()

    def get_contours(self, key: CacheKey) -> PwmbContourStack | None:
        with self._lock:
            return self._contours.get(key)

    def set_contours(self, key: CacheKey, value: PwmbContourStack) -> None:
        with self._lock:
            self._contours[key] = value

    def get_geometry(self, key: CacheKey) -> PwmbContourGeometry | None:
        with self._lock:
            return self._geometry.get(key)

    def set_geometry(self, key: CacheKey, value: PwmbContourGeometry) -> None:
        with self._lock:
            self._geometry[key] = value

    def clear(self) -> None:
        with self._lock:
            self._contours.clear()
            self._geometry.clear()


def compute_file_signature(path: str | Path) -> str:
    normalized = Path(path)
    stat = normalized.stat()
    digest = hashlib.sha1(usedforsecurity=False)
    with normalized.open("rb") as handle:
        head = handle.read(64 * 1024)
        digest.update(head)
        if stat.st_size > 64 * 1024:
            try:
                handle.seek(max(0, stat.st_size - (64 * 1024)))
            except OSError:
                handle.seek(0)
            tail = handle.read(64 * 1024)
            digest.update(tail)
    return f"size={stat.st_size}:mtime={stat.st_mtime_ns}:sha1={digest.hexdigest()}"


def make_cache_key(
    document: PwmbDocument,
    *,
    threshold: int,
    bin_mode: str,
    xy_stride: int,
    z_stride: int,
    simplify_epsilon: float,
    max_layers: int | None,
    max_vertices: int | None,
    render_mode: str,
    file_signature: str | None = None,
) -> CacheKey:
    signature = file_signature or compute_file_signature(document.path)
    return CacheKey(
        file_signature=signature,
        pwmb_version=int(document.version),
        decoder_kind=_normalize_decoder_kind(document.machine.layer_image_format),
        pws_convention=document.pws_convention,
        lut_signature=_lut_signature(document.lut),
        threshold=max(0, min(255, int(threshold))),
        bin_mode=str(bin_mode).strip() or "index_strict",
        xy_stride=max(1, int(xy_stride)),
        z_stride=max(1, int(z_stride)),
        simplify_epsilon=float(simplify_epsilon),
        max_layers=int(max_layers) if max_layers is not None and max_layers > 0 else -1,
        max_vertices=int(max_vertices) if max_vertices is not None and max_vertices > 0 else -1,
        render_mode=str(render_mode).strip() or "fill",
    )


def _normalize_decoder_kind(value: str | None) -> str:
    text = (value or "").strip().lower()
    if "pw0" in text:
        return "pw0Img"
    if "pws" in text:
        return "pwsImg"
    return text or "unknown"


def _lut_signature(values: list[int]) -> str:
    if not values:
        return "none"
    digest = hashlib.sha1(bytes(int(v) & 0xFF for v in values), usedforsecurity=False).hexdigest()
    return f"len={len(values)}:sha1={digest}"
