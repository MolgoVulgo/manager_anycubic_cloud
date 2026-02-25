from __future__ import annotations

import logging
from pathlib import Path

from accloud_core.config import AppConfig
from accloud_core.models import FileItem
from app_gui_qt.app import _make_open_viewer_callback


class _FakeApi:
    pass


def _config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        session_path=tmp_path / "session.json",
        cache_dir=tmp_path / "cache",
        app_log_path=tmp_path / "app.log",
        http_log_path=tmp_path / "http.log",
        fault_log_path=tmp_path / "fault.log",
    )


def test_open_viewer_callback_defers_pwmb_resolution(monkeypatch, tmp_path: Path) -> None:
    opened: dict[str, object] = {}
    called = {"resolver_called": False}

    def _fake_open_viewer_dialog(owner, **kwargs) -> None:
        opened["owner"] = owner
        opened.update(kwargs)

    def _fake_resolve(**kwargs):
        called["resolver_called"] = True
        return None

    monkeypatch.setattr("app_gui_qt.app._open_viewer_dialog", _fake_open_viewer_dialog)
    monkeypatch.setattr("app_gui_qt.app._resolve_pwmb_path_for_viewer", _fake_resolve)

    callback = _make_open_viewer_callback(
        owner="owner",
        api=_FakeApi(),  # type: ignore[arg-type]
        config=_config(tmp_path),
        logger=logging.getLogger("tests.viewer"),
    )
    callback(FileItem(file_id="42", name="demo.pwmb", size_bytes=123))

    assert called["resolver_called"] is False
    assert opened["owner"] == "owner"
    assert opened["pwmb_path"] is None
    assert opened["file_label"] == "demo.pwmb"
    assert callable(opened["resolve_pwmb_path"])
