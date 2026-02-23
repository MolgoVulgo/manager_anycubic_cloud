from __future__ import annotations

from pathlib import Path
from typing import Callable

from app_gui_qt.qt_compat import require_qt
from app_gui_qt.widgets import make_panel


ImportHarCallback = Callable[[Path, Path], tuple[bool, str]]


def build_session_settings_dialog(
    parent=None,
    *,
    default_session_path: str = "session.json",
    on_import_har: ImportHarCallback | None = None,
):
    _qtcore, qtwidgets = require_qt()
    dialog = qtwidgets.QDialog(parent)
    dialog.setWindowTitle("Session Settings")
    dialog.resize(700, 440)

    layout = qtwidgets.QVBoxLayout(dialog)
    layout.setContentsMargins(18, 18, 18, 18)
    layout.setSpacing(12)

    title = qtwidgets.QLabel("Session Settings")
    title.setObjectName("title")
    title.setStyleSheet("font-size: 24px;")
    subtitle = qtwidgets.QLabel("Token import from HAR is active in phase 3.")
    subtitle.setObjectName("subtitle")
    layout.addWidget(title)
    layout.addWidget(subtitle)

    import_panel = make_panel(parent=dialog, object_name="panel")
    import_layout = qtwidgets.QFormLayout(import_panel)
    import_layout.setContentsMargins(12, 12, 12, 12)
    import_layout.setSpacing(10)

    har_path = qtwidgets.QLineEdit()
    har_path.setPlaceholderText("/path/to/session.har")
    har_row = qtwidgets.QWidget(import_panel)
    har_row_layout = qtwidgets.QHBoxLayout(har_row)
    har_row_layout.setContentsMargins(0, 0, 0, 0)
    har_row_layout.setSpacing(8)
    browse = qtwidgets.QPushButton("Browse HAR")
    har_row_layout.addWidget(har_path, 1)
    har_row_layout.addWidget(browse)
    import_layout.addRow("HAR file", har_row)

    session_path = qtwidgets.QLineEdit(default_session_path)
    import_layout.addRow("Session target", session_path)
    layout.addWidget(import_panel)

    info_panel = make_panel(parent=dialog, object_name="cardAlt")
    info_layout = qtwidgets.QVBoxLayout(info_panel)
    info_layout.setContentsMargins(12, 12, 12, 12)
    info_layout.setSpacing(6)
    info_layout.addWidget(qtwidgets.QLabel("Security reminders"))
    info_layout.addWidget(qtwidgets.QLabel("- Only token headers are imported from HAR."))
    info_layout.addWidget(qtwidgets.QLabel("- Never expose Authorization, raw tokens, or signed URLs in logs."))
    info_layout.addWidget(qtwidgets.QLabel("- Session file permissions are expected to be 0600."))
    layout.addWidget(info_panel)

    status = qtwidgets.QLabel("")
    status.setObjectName("subtitle")
    layout.addWidget(status)

    def _browse_har() -> None:
        file_dialog = qtwidgets.QFileDialog(dialog, "Select HAR file")
        file_dialog.setFileMode(qtwidgets.QFileDialog.FileMode.ExistingFile)
        file_dialog.setNameFilters(
            [
                "HAR files (*.har)",
                "JSON files (*.json)",
                "All files (*)",
            ]
        )
        file_dialog.setOption(qtwidgets.QFileDialog.Option.DontUseNativeDialog, True)
        if file_dialog.exec() == qtwidgets.QDialog.DialogCode.Accepted:
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                har_path.setText(selected_files[0])

    def _import_har() -> None:
        raw_har = har_path.text().strip()
        if not raw_har:
            qtwidgets.QMessageBox.warning(dialog, "Missing input", "Please select a HAR file.")
            return
        har_file = Path(raw_har)
        if not har_file.exists():
            qtwidgets.QMessageBox.warning(dialog, "File not found", f"HAR file does not exist:\n{har_file}")
            return

        raw_session_path = session_path.text().strip()
        if not raw_session_path:
            qtwidgets.QMessageBox.warning(dialog, "Missing input", "Please provide a target session path.")
            return

        if on_import_har is None:
            qtwidgets.QMessageBox.information(
                dialog,
                "Not wired",
                "No import callback is configured.",
            )
            return

        ok, message = on_import_har(har_file, Path(raw_session_path))
        status.setText(message)
        if ok:
            qtwidgets.QMessageBox.information(dialog, "Session updated", message)
        else:
            qtwidgets.QMessageBox.critical(dialog, "Import failed", message)

    buttons = qtwidgets.QHBoxLayout()
    import_btn = qtwidgets.QPushButton("Import HAR")
    import_btn.setObjectName("primary")
    close = qtwidgets.QPushButton("Close")

    browse.clicked.connect(_browse_har)
    import_btn.clicked.connect(_import_har)
    close.clicked.connect(dialog.reject)

    buttons.addStretch(1)
    buttons.addWidget(close)
    buttons.addWidget(import_btn)
    layout.addLayout(buttons)
    return dialog
