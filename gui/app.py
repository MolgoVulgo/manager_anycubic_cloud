from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
import faulthandler
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
import sys
import threading

from accloud.api import AnycubicCloudApi
from accloud.cache_store import CacheStore
from accloud.client import CloudHttpClient
from accloud.config import AppConfig
from accloud.models import FileItem, Printer, Quota, SessionData
from accloud.session_store import extract_tokens_from_har, load_session, merge_sessions, save_session
from gui.dialogs.print_dialog import build_print_dialog
from gui.dialogs.pwmb3d_dialog import build_pwmb3d_dialog
from gui.dialogs.session_settings_dialog import ImportHarCallback, build_session_settings_dialog
from gui.dialogs.upload_dialog import build_upload_dialog
from gui.qt_compat import require_qt
from gui.tabs.files_tab import build_files_tab
from gui.tabs.log_tab import build_log_tab
from gui.tabs.printer_tab import build_printer_tab
from gui.theme import Theme


def _configure_logging(config: AppConfig) -> None:
    root_logger = logging.getLogger()
    level = getattr(logging, config.log_level, logging.INFO)
    root_logger.setLevel(level)

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    config.http_log_path.parent.mkdir(parents=True, exist_ok=True)
    app_file_handler = TimedRotatingFileHandler(
        filename=str(config.http_log_path),
        when="midnight",
        interval=1,
        backupCount=config.http_log_retention_days,
        encoding="utf-8",
    )
    app_file_handler.setLevel(logging.DEBUG)
    app_file_handler.setFormatter(formatter)
    root_logger.addHandler(app_file_handler)

    http_logger = logging.getLogger("accloud.http")
    http_logger.setLevel(logging.DEBUG)
    # accloud.http records now flow through root handlers to keep a single consolidated log file.
    for handler in list(http_logger.handlers):
        http_logger.removeHandler(handler)
        handler.close()
    http_logger.propagate = True


def _enable_fault_handler(config: AppConfig) -> None:
    if not config.enable_fault_handler:
        return
    fault_path = Path(config.fault_log_path)
    fault_path.parent.mkdir(parents=True, exist_ok=True)
    handle = fault_path.open("a", encoding="utf-8")
    faulthandler.enable(file=handle)


def _install_theme(app, theme: Theme) -> None:
    from PySide6 import QtGui  # type: ignore

    app.setStyle("Fusion")
    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(theme.bg_root))
    palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor(theme.text_main))
    palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor(theme.bg_card))
    palette.setColor(QtGui.QPalette.ColorRole.AlternateBase, QtGui.QColor(theme.bg_card_alt))
    palette.setColor(QtGui.QPalette.ColorRole.ToolTipBase, QtGui.QColor(theme.bg_panel))
    palette.setColor(QtGui.QPalette.ColorRole.ToolTipText, QtGui.QColor(theme.text_main))
    palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor(theme.text_main))
    palette.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor(theme.bg_panel))
    palette.setColor(QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor(theme.text_main))
    palette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor(theme.accent_primary))
    palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtGui.QColor("#ffffff"))
    app.setPalette(palette)
    app.setStyleSheet(theme.style_sheet())


def _open_upload_dialog(owner) -> None:
    dialog = build_upload_dialog(owner)
    dialog.exec()


def _open_print_dialog(owner) -> None:
    dialog = build_print_dialog(owner)
    dialog.exec()


def _open_viewer_dialog(owner) -> None:
    dialog = build_pwmb3d_dialog(owner)
    dialog.exec()


def _make_session_import_callback(
    *,
    client: CloudHttpClient,
    api: AnycubicCloudApi,
    logger: logging.Logger,
) -> ImportHarCallback:
    def _import_har(har_path: Path, session_path: Path) -> tuple[bool, str]:
        try:
            incoming = extract_tokens_from_har(har_path)
            logger.debug(
                "HAR parsed token_count=%s token_keys=%s",
                len(incoming.tokens),
                sorted(incoming.tokens.keys()),
            )
            if not incoming.tokens:
                return False, "No token found in HAR file for Anycubic endpoints."
            current = client.session_data
            merged = merge_sessions(current, incoming)
            if not str(merged.tokens.get("token", "")).strip():
                bootstrap_access_token = (
                    str(merged.tokens.get("access_token", "")).strip()
                    or str(merged.tokens.get("id_token", "")).strip()
                )
                if bootstrap_access_token:
                    try:
                        login_data = api.login_with_access_token(bootstrap_access_token)
                        session_token = str(login_data.get("token", "")).strip()
                        if session_token:
                            merged.tokens["token"] = session_token
                            logger.debug("Session token bootstrapped via loginWithAccessToken.")
                    except Exception as exc:
                        logger.warning("Session token bootstrap failed: %s", exc)
            logger.debug(
                "Writing imported session path=%s token_count=%s token_keys=%s",
                session_path,
                len(merged.tokens),
                sorted(merged.tokens.keys()),
            )
            save_session(session_path, merged)
            client.update_session(merged)

            valid, validation_msg = _validate_connection(api=api, logger=logger)
            if not valid:
                # Debug mode: keep imported token in-memory and on disk even if validation fails.
                logger.warning(
                    "Session validation failed after HAR import, keeping imported token for debug "
                    "path=%s token_count=%s error=%s",
                    session_path,
                    len(merged.tokens),
                    validation_msg,
                )
                return (
                    False,
                    "HAR import completed but token validation failed "
                    f"(token kept for debug): {validation_msg}",
                )

            logger.info("Session token import valid tokens=%s", len(merged.tokens))
            return True, f"Session imported and validated from {har_path.name}"
        except Exception as exc:  # pragma: no cover - runtime safety path
            logger.exception("HAR import failed: %s", exc)
            return False, f"HAR import failed: {exc}"

    return _import_har


def _open_session_settings_dialog(owner, *, config: AppConfig, on_import_har: ImportHarCallback) -> None:
    dialog = build_session_settings_dialog(
        owner,
        default_session_path=str(config.session_path),
        on_import_har=on_import_har,
    )
    dialog.exec()


def _create_cloud_client(config: AppConfig, logger: logging.Logger) -> CloudHttpClient:
    logger.debug("Session bootstrap using path=%s", config.session_path)
    if config.session_path.exists():
        try:
            session = load_session(config.session_path)
            logger.info(
                "Loaded session tokens=%s from %s",
                len(session.tokens),
                config.session_path,
            )
            logger.debug("Loaded session token keys=%s", sorted(session.tokens.keys()))
        except Exception as exc:
            logger.warning("Failed to load session file %s: %s", config.session_path, exc)
            session = SessionData()
    else:
        logger.debug("Session file does not exist: %s", config.session_path)
        session = SessionData()
    if not session.tokens:
        logger.debug("No token available in active session at startup.")
    return CloudHttpClient(config=config, session_data=session)


def _make_refresh_files_callback(
    *,
    api: AnycubicCloudApi,
    logger: logging.Logger,
    config: AppConfig,
    cache_store: CacheStore,
):
    def _refresh() -> tuple[Quota | None, list[FileItem], str | None]:
        errors: list[str] = []
        quota: Quota | None = None
        files: list[FileItem] = []

        try:
            quota = api.get_quota()
        except Exception as exc:
            logger.warning("Quota refresh failed: %s", exc)
            errors.append(f"quota: {exc}")

        try:
            files = api.list_files(page=1, page_size=20)
        except Exception as exc:
            logger.warning("Files refresh failed: %s", exc)
            errors.append(f"files: {exc}")

        _enrich_files_with_gcode(
            files=files,
            api=api,
            logger=logger,
            config=config,
            cache_store=cache_store,
        )

        if quota is not None or files:
            _save_startup_snapshot(cache_store=cache_store, quota=quota, files=files)

        if errors and quota is None and not files:
            cached_quota, cached_files = _load_startup_snapshot(cache_store=cache_store, config=config)
            if cached_quota is not None or cached_files:
                return (
                    cached_quota,
                    cached_files,
                    "Cloud unavailable, loaded from local cache.",
                )

        if errors:
            cached_quota, cached_files = _load_startup_snapshot(cache_store=cache_store, config=config)
            if quota is None and cached_quota is not None:
                quota = cached_quota
            if not files and cached_files:
                files = cached_files
            return quota, files, "Refresh partial failure: " + " | ".join(errors)
        return quota, files, None

    return _refresh


def _make_refresh_printers_callback(
    *,
    api: AnycubicCloudApi,
    logger: logging.Logger,
    config: AppConfig,
    cache_store: CacheStore,
):
    def _refresh() -> tuple[list[Printer], str | None]:
        try:
            printers = api.list_printers()
        except Exception as exc:
            logger.warning("Printers refresh failed: %s", exc)
            cached_printers = _load_printer_snapshot(cache_store=cache_store, config=config)
            if cached_printers:
                return cached_printers, "Cloud unavailable, loaded printers from local cache."
            return [], f"Printers refresh failed: {exc}"

        _save_printer_snapshot(cache_store=cache_store, printers=printers)
        if printers:
            return printers, None
        return printers, "No printer returned by cloud API."

    return _refresh


def _extract_layer_thickness_mm(extra: dict[str, object]) -> float | None:
    if not extra:
        return None
    for key in ("layer_height", "layerHeight", "thickness", "layer_thickness", "layerThickness"):
        value = extra.get(key)
        if value is None:
            continue
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            continue
        if parsed <= 0:
            continue
        return parsed
    return None


def _enrich_files_with_gcode(
    *,
    files: list[FileItem],
    api: AnycubicCloudApi,
    logger: logging.Logger,
    config: AppConfig,
    cache_store: CacheStore,
) -> None:
    missing: list[tuple[FileItem, str]] = []

    for file_item in files:
        needs_layers = file_item.layer_count is None
        needs_print_time = file_item.print_time_s is None
        needs_thickness = file_item.layer_thickness_mm is None
        if not (needs_layers or needs_print_time or needs_thickness):
            continue

        lookup_id = file_item.gcode_id or file_item.file_id
        if not lookup_id:
            continue

        cached = cache_store.load_json(f"gcode/{lookup_id}", max_age_s=config.cache_gcode_ttl_s)
        if isinstance(cached, dict):
            _apply_cached_gcode(file_item=file_item, payload=cached)
            needs_layers = file_item.layer_count is None
            needs_print_time = file_item.print_time_s is None
            needs_thickness = file_item.layer_thickness_mm is None
            if not (needs_layers or needs_print_time or needs_thickness):
                continue

        missing.append((file_item, lookup_id))

    if not missing:
        return

    # Log analysis shows this endpoint dominated startup latency. Limit and parallelize calls.
    candidates = missing
    workers = max(1, min(4, len(candidates)))

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="gcode-info") as pool:
        futures = {
            pool.submit(api.get_gcode_info, lookup_id): (file_item, lookup_id)
            for file_item, lookup_id in candidates
        }
        for future in as_completed(futures):
            file_item, lookup_id = futures[future]
            try:
                gcode = future.result()
            except Exception as exc:
                logger.debug(
                    "GCode metadata fetch failed file_id=%s gcode_id=%s error=%s",
                    file_item.file_id,
                    lookup_id,
                    exc,
                )
                continue

            _apply_gcode(file_item=file_item, gcode=gcode)
            cache_store.save_json(
                f"gcode/{lookup_id}",
                {
                    "layers": gcode.layers,
                    "print_time_s": gcode.print_time_s,
                    "layer_thickness_mm": _extract_layer_thickness_mm(gcode.extra),
                },
            )


def _apply_gcode(file_item: FileItem, gcode) -> None:
    if file_item.layer_count is None and gcode.layers is not None:
        file_item.layer_count = gcode.layers
    if file_item.print_time_s is None and gcode.print_time_s is not None:
        file_item.print_time_s = gcode.print_time_s
    if file_item.layer_thickness_mm is None:
        thickness = _extract_layer_thickness_mm(gcode.extra)
        if thickness is not None:
            file_item.layer_thickness_mm = thickness


def _apply_cached_gcode(file_item: FileItem, payload: dict[str, object]) -> None:
    if file_item.layer_count is None:
        layers = _to_optional_int(payload.get("layers"))
        if layers is not None:
            file_item.layer_count = layers

    if file_item.print_time_s is None:
        print_time = _to_optional_int(payload.get("print_time_s"))
        if print_time is not None:
            file_item.print_time_s = print_time

    if file_item.layer_thickness_mm is None:
        thickness = _to_optional_float(payload.get("layer_thickness_mm"))
        if thickness is not None and thickness > 0:
            file_item.layer_thickness_mm = thickness


def _save_startup_snapshot(*, cache_store: CacheStore, quota: Quota | None, files: list[FileItem]) -> None:
    payload: dict[str, object] = {
        "quota": asdict(quota) if quota is not None else None,
        "files": [asdict(item) for item in files],
    }
    cache_store.save_json("startup_snapshot", payload)


def _save_printer_snapshot(*, cache_store: CacheStore, printers: list[Printer]) -> None:
    payload = [asdict(item) for item in printers]
    cache_store.save_json("printers_snapshot", payload)


def _load_startup_snapshot(*, cache_store: CacheStore, config: AppConfig) -> tuple[Quota | None, list[FileItem]]:
    payload = cache_store.load_json("startup_snapshot", max_age_s=config.cache_startup_ttl_s)
    if not isinstance(payload, dict):
        return None, []

    quota = _deserialize_quota(payload.get("quota"))
    files = _deserialize_files(payload.get("files"))
    return quota, files


def _load_printer_snapshot(*, cache_store: CacheStore, config: AppConfig) -> list[Printer]:
    payload = cache_store.load_json("printers_snapshot", max_age_s=config.cache_startup_ttl_s)
    return _deserialize_printers(payload)


def _deserialize_quota(raw: object) -> Quota | None:
    if not isinstance(raw, dict):
        return None
    total = _to_int(raw.get("total_bytes"), default=0)
    used = _to_int(raw.get("used_bytes"), default=0)
    free = _to_int(raw.get("free_bytes"), default=max(total - used, 0))
    percent = _to_float(raw.get("used_percent"), default=(used / total * 100.0 if total > 0 else 0.0))
    return Quota(total_bytes=total, used_bytes=used, free_bytes=free, used_percent=percent)


def _deserialize_files(raw: object) -> list[FileItem]:
    if not isinstance(raw, list):
        return []
    output: list[FileItem] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        output.append(
            FileItem(
                file_id=str(item.get("file_id", "")),
                name=str(item.get("name", "unnamed.pwmb")),
                size_bytes=_to_int(item.get("size_bytes"), default=0),
                upload_time=_to_optional_str(item.get("upload_time")),
                created_at=_to_optional_str(item.get("created_at")),
                updated_at=_to_optional_str(item.get("updated_at")),
                status=_to_optional_str(item.get("status")),
                status_code=_to_optional_int(item.get("status_code")),
                thumbnail_url=_to_optional_str(item.get("thumbnail_url")),
                download_url=_to_optional_str(item.get("download_url")),
                gcode_id=_to_optional_str(item.get("gcode_id")),
                layer_count=_to_optional_int(item.get("layer_count")),
                print_time_s=_to_optional_int(item.get("print_time_s")),
                layer_thickness_mm=_to_optional_float(item.get("layer_thickness_mm")),
                machine_name=_to_optional_str(item.get("machine_name")),
                material_name=_to_optional_str(item.get("material_name")),
                resin_usage_ml=_to_optional_float(item.get("resin_usage_ml")),
                size_x_mm=_to_optional_float(item.get("size_x_mm")),
                size_y_mm=_to_optional_float(item.get("size_y_mm")),
                size_z_mm=_to_optional_float(item.get("size_z_mm")),
                file_extension=_to_optional_str(item.get("file_extension")),
                bottom_layers=_to_optional_int(item.get("bottom_layers")),
                exposure_time_s=_to_optional_float(item.get("exposure_time_s")),
                off_time_s=_to_optional_float(item.get("off_time_s")),
                printer_names=_to_str_list(item.get("printer_names")),
                md5=_to_optional_str(item.get("md5")),
                region=_to_optional_str(item.get("region")),
                bucket=_to_optional_str(item.get("bucket")),
                object_path=_to_optional_str(item.get("object_path")),
            )
        )
    return output


def _deserialize_printers(raw: object) -> list[Printer]:
    if not isinstance(raw, list):
        return []
    output: list[Printer] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        output.append(
            Printer(
                printer_id=str(item.get("printer_id", "")),
                name=str(item.get("name", "Unknown printer")),
                online=_to_bool(item.get("online")),
                state=_to_optional_str(item.get("state")),
                model=_to_optional_str(item.get("model")),
                printer_type=_to_optional_str(item.get("printer_type")),
                description=_to_optional_str(item.get("description")),
                reason=_to_optional_str(item.get("reason")),
                device_status=_to_optional_int(item.get("device_status")),
                is_printing=_to_optional_int(item.get("is_printing")),
                last_update_time=_to_optional_str(item.get("last_update_time")),
                material_type=_to_optional_str(item.get("material_type")),
                material_used=_to_optional_str(item.get("material_used")),
                print_total_time=_to_optional_str(item.get("print_total_time")),
                image_url=_to_optional_str(item.get("image_url")),
                machine_type=_to_optional_int(item.get("machine_type")),
                key=_to_optional_str(item.get("key")),
            )
        )
    return output


def _to_int(value: object, *, default: int = 0) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _to_optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _to_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _to_optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _to_optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "online"}
    return False


def _to_str_list(value: object) -> list[str]:
    if isinstance(value, (list, tuple)):
        output: list[str] = []
        for item in value:
            text = _to_optional_str(item)
            if text:
                output.append(text)
        return output
    text = _to_optional_str(value)
    if text:
        return [text]
    return []


def _validate_connection(
    *,
    api: AnycubicCloudApi,
    logger: logging.Logger,
) -> tuple[bool, str]:
    try:
        api.validate_session()
        return True, "Connection validated."
    except Exception as exc:
        logger.warning("Connection validation failed: %s", exc)
        return False, str(exc)


def _bootstrap_startup(
    *,
    window,
    config: AppConfig,
    client: CloudHttpClient,
    api: AnycubicCloudApi,
    logger: logging.Logger,
    session_import_cb: ImportHarCallback,
    refresh_cb,
    cache_store: CacheStore,
) -> None:
    files_tab = getattr(window, "_files_tab_controller", None)
    printer_tab = getattr(window, "_printer_tab_controller", None)

    if files_tab is not None:
        cached_quota, cached_files = _load_startup_snapshot(cache_store=cache_store, config=config)
        if cached_quota is not None or cached_files:
            files_tab.apply_refresh_result(
                quota=cached_quota,
                files=cached_files,
                error_message="Loaded from local cache while syncing cloud data.",
            )
    if printer_tab is not None and hasattr(printer_tab, "render_printers"):
        cached_printers = _load_printer_snapshot(cache_store=cache_store, config=config)
        if cached_printers:
            try:
                printer_tab.render_printers(cached_printers)
            except Exception as exc:  # pragma: no cover - UI safety path
                logger.debug("Could not apply cached printers on startup: %s", exc)

    _start_refresh_job(
        window=window,
        config=config,
        client=client,
        api=api,
        logger=logger,
        session_import_cb=session_import_cb,
        refresh_cb=refresh_cb,
        retry_import=1,
    )


def _start_refresh_job(
    *,
    window,
    config: AppConfig,
    client: CloudHttpClient,
    api: AnycubicCloudApi,
    logger: logging.Logger,
    session_import_cb: ImportHarCallback,
    refresh_cb,
    retry_import: int,
) -> None:
    qtcore, _qtwidgets = require_qt()
    files_tab = getattr(window, "_files_tab_controller", None)
    printer_tab = getattr(window, "_printer_tab_controller", None)

    if files_tab is not None:
        files_tab.set_loading(True, "Loading cloud data...")

    state: dict[str, object] = {}

    def _worker() -> None:
        if not client.session_data.tokens:
            state["invalid"] = "No session token found."
            return

        valid, message = _validate_connection(api=api, logger=logger)
        if not valid:
            state["invalid"] = message
            return

        quota, files, error_message = refresh_cb()
        state["quota"] = quota
        state["files"] = files
        state["error_message"] = error_message

    worker = threading.Thread(target=_worker, daemon=True, name="startup-refresh")
    worker.start()

    timer = qtcore.QTimer(window)
    timer.setInterval(80)

    def _poll() -> None:
        if worker.is_alive():
            return
        timer.stop()

        invalid = state.get("invalid")
        if isinstance(invalid, str):
            if retry_import > 0:
                logger.info("Session invalid at startup, opening HAR import dialog: %s", invalid)
                if files_tab is not None:
                    files_tab.set_loading(False, "Session invalid. Import HAR required.")
                _open_session_settings_dialog(window, config=config, on_import_har=session_import_cb)
                if client.session_data.tokens:
                    _start_refresh_job(
                        window=window,
                        config=config,
                        client=client,
                        api=api,
                        logger=logger,
                        session_import_cb=session_import_cb,
                        refresh_cb=refresh_cb,
                        retry_import=retry_import - 1,
                    )
                return

            if files_tab is not None:
                files_tab.set_loading(False, f"Session invalid: {invalid}")
            return

        quota = state.get("quota")
        files = state.get("files")
        error_message = state.get("error_message")
        if files_tab is not None:
            files_tab.apply_refresh_result(
                quota=quota if isinstance(quota, Quota) else None,
                files=files if isinstance(files, list) else [],
                error_message=error_message if isinstance(error_message, str) else None,
            )
        if printer_tab is not None and hasattr(printer_tab, "refresh"):
            try:
                printer_tab.refresh()
            except Exception as exc:  # pragma: no cover - UI safety path
                logger.debug("Printer startup refresh skipped: %s", exc)

    timer.timeout.connect(_poll)
    timer.start()
    window._startup_timer = timer  # type: ignore[attr-defined]
    window._startup_worker = worker  # type: ignore[attr-defined]


def build_main_window(
    *,
    config: AppConfig,
    client: CloudHttpClient,
    api: AnycubicCloudApi,
    cache_store: CacheStore,
):
    _qtcore, qtwidgets = require_qt()
    logger = logging.getLogger("gui.app")
    session_import_cb = _make_session_import_callback(client=client, api=api, logger=logger)
    refresh_cb = _make_refresh_files_callback(
        api=api,
        logger=logger,
        config=config,
        cache_store=cache_store,
    )
    refresh_printers_cb = _make_refresh_printers_callback(
        api=api,
        logger=logger,
        config=config,
        cache_store=cache_store,
    )

    window = qtwidgets.QMainWindow()
    window.setObjectName("mainWindow")
    window.setWindowTitle("Anycubic Cloud Client + PWMB Viewer (Phase 3 - Cloud)")
    window.resize(1320, 860)
    window.setMinimumSize(760, 420)

    root = qtwidgets.QWidget(window)
    root_layout = qtwidgets.QVBoxLayout(root)
    root_layout.setContentsMargins(18, 14, 18, 18)
    root_layout.setSpacing(10)
    window.setCentralWidget(root)

    header = qtwidgets.QFrame(root)
    header.setObjectName("panel")
    header_layout = qtwidgets.QHBoxLayout(header)
    header_layout.setContentsMargins(14, 12, 14, 12)
    header_layout.setSpacing(10)

    title_col = qtwidgets.QVBoxLayout()
    title = qtwidgets.QLabel("Anycubic Cloud Control Room")
    title.setObjectName("title")
    subtitle = qtwidgets.QLabel(
        "Phase 3 cloud baseline: HAR import and files refresh are active."
    )
    subtitle.setObjectName("subtitle")
    title_col.addWidget(title)
    title_col.addWidget(subtitle)
    header_layout.addLayout(title_col, 1)

    upload_btn = qtwidgets.QPushButton("Upload Dialog")
    upload_btn.setObjectName("primary")
    upload_btn.clicked.connect(lambda: _open_upload_dialog(window))

    print_btn = qtwidgets.QPushButton("Print Dialog")
    print_btn.clicked.connect(lambda: _open_print_dialog(window))

    view_btn = qtwidgets.QPushButton("3D Viewer Dialog")
    view_btn.clicked.connect(lambda: _open_viewer_dialog(window))

    session_btn = qtwidgets.QPushButton("Session Settings")
    session_btn.clicked.connect(
        lambda: _open_session_settings_dialog(
            window,
            config=config,
            on_import_har=session_import_cb,
        )
    )

    for button in [session_btn, print_btn, view_btn, upload_btn]:
        header_layout.addWidget(button)

    root_layout.addWidget(header)

    tabs = qtwidgets.QTabWidget(root)
    files_widget = build_files_tab(
        window,
        on_open_viewer=lambda: _open_viewer_dialog(window),
        on_refresh=refresh_cb,
        auto_refresh=False,
        cache_store=cache_store,
        thumbnail_ttl_s=config.cache_thumbnail_ttl_s,
    )
    tabs.addTab(
        files_widget,
        "Files",
    )
    printer_widget = build_printer_tab(
        window,
        on_open_print_dialog=lambda _printer=None: _open_print_dialog(window),
        on_refresh=refresh_printers_cb,
        auto_refresh=False,
    )
    tabs.addTab(printer_widget, "Printer")
    tabs.addTab(build_log_tab(window, log_path=config.http_log_path), "Log")
    root_layout.addWidget(tabs, 1)

    window._files_tab_controller = getattr(files_widget, "_files_tab_controller", None)  # type: ignore[attr-defined]
    window._printer_tab_controller = getattr(printer_widget, "_printer_tab_controller", None)  # type: ignore[attr-defined]
    window._session_import_cb = session_import_cb  # type: ignore[attr-defined]
    window._refresh_files_cb = refresh_cb  # type: ignore[attr-defined]
    window._refresh_printers_cb = refresh_printers_cb  # type: ignore[attr-defined]
    return window


def main(argv: list[str] | None = None) -> int:
    config = AppConfig.from_env()
    config.cache_dir.mkdir(parents=True, exist_ok=True)
    cache_store = CacheStore(config.cache_dir)
    _configure_logging(config)
    _enable_fault_handler(config)
    logger = logging.getLogger("gui.app")

    try:
        qtcore, qtwidgets = require_qt()
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 2

    qtcore.QCoreApplication.setAttribute(
        qtcore.Qt.ApplicationAttribute.AA_DontUseNativeDialogs,
        True,
    )

    client = _create_cloud_client(config, logger)
    api = AnycubicCloudApi(client)

    app = qtwidgets.QApplication(argv or sys.argv)
    app.aboutToQuit.connect(client.close)
    _install_theme(app, Theme())

    window = build_main_window(
        config=config,
        client=client,
        api=api,
        cache_store=cache_store,
    )
    window.show()
    qtcore.QTimer.singleShot(
        0,
        lambda: _bootstrap_startup(
            window=window,
            config=config,
            client=client,
            api=api,
            logger=logger,
            session_import_cb=getattr(window, "_session_import_cb"),
            refresh_cb=getattr(window, "_refresh_files_cb"),
            cache_store=cache_store,
        ),
    )
    logger.info("GUI started in phase-3 cloud mode")
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
