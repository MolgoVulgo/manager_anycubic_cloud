from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Any
from urllib.parse import urlparse


@dataclass(slots=True)
class CacheStore:
    root: Path

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self._json_dir().mkdir(parents=True, exist_ok=True)
        self._thumb_dir().mkdir(parents=True, exist_ok=True)

    def load_json(self, key: str, *, max_age_s: int) -> dict[str, Any] | list[Any] | None:
        path = self._json_path(key)
        if not path.exists():
            return None
        if max_age_s > 0 and self._is_expired(path, max_age_s=max_age_s):
            return None
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return None
        if isinstance(payload, (dict, list)):
            return payload
        return None

    def save_json(self, key: str, payload: dict[str, Any] | list[Any]) -> None:
        path = self._json_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write_text(path, json.dumps(payload, ensure_ascii=True, separators=(",", ":")))

    def load_thumbnail(self, url: str, *, max_age_s: int) -> bytes | None:
        path = self._thumbnail_path(url)
        if not path.exists():
            return None
        if max_age_s > 0 and self._is_expired(path, max_age_s=max_age_s):
            return None
        try:
            return path.read_bytes()
        except OSError:
            return None

    def save_thumbnail(self, url: str, payload: bytes) -> None:
        path = self._thumbnail_path(url)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write_bytes(path, payload)

    def _json_dir(self) -> Path:
        return self.root / "json"

    def _thumb_dir(self) -> Path:
        return self.root / "thumbnails"

    def _json_path(self, key: str) -> Path:
        clean_key = key.strip().replace("\\", "/")
        if not clean_key:
            clean_key = "default"
        if not clean_key.endswith(".json"):
            clean_key = f"{clean_key}.json"
        return self._json_dir() / clean_key

    def _thumbnail_path(self, url: str) -> Path:
        digest = hashlib.sha1(url.encode("utf-8"), usedforsecurity=False).hexdigest()
        parsed = urlparse(url)
        suffix = Path(parsed.path).suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
            suffix = ".img"
        return self._thumb_dir() / f"{digest}{suffix}"

    @staticmethod
    def _is_expired(path: Path, *, max_age_s: int) -> bool:
        if max_age_s <= 0:
            return False
        try:
            age_s = time.time() - path.stat().st_mtime
        except OSError:
            return True
        return age_s > float(max_age_s)

    @staticmethod
    def _atomic_write_text(path: Path, text: str) -> None:
        fd, temp_path = tempfile.mkstemp(prefix=".tmp_", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
            os.replace(temp_path, path)
        finally:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except OSError:
                pass

    @staticmethod
    def _atomic_write_bytes(path: Path, payload: bytes) -> None:
        fd, temp_path = tempfile.mkstemp(prefix=".tmp_", dir=str(path.parent))
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
            os.replace(temp_path, path)
        finally:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except OSError:
                pass
