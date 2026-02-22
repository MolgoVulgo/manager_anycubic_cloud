from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Theme:
    font_family: str = '"IBM Plex Sans", "Source Sans Pro", "Noto Sans", sans-serif'
    font_mono: str = '"JetBrains Mono", "Fira Code", monospace'
    bg_root: str = "#f4efe4"
    bg_panel: str = "#fffaf1"
    bg_card: str = "#fffef8"
    bg_card_alt: str = "#f9f3e8"
    border_soft: str = "#d8cfbf"
    border_strong: str = "#baa98f"
    text_main: str = "#2d281f"
    text_muted: str = "#6f6454"
    accent_primary: str = "#0f8a7f"
    accent_secondary: str = "#d47f2f"
    danger: str = "#b23b3b"
    ok: str = "#2c7a3d"
    warn: str = "#a7731b"

    def style_sheet(self) -> str:
        return f"""
        QWidget {{
            font-family: {self.font_family};
            color: {self.text_main};
        }}

        QMainWindow#mainWindow {{
            background: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 1,
                stop: 0 {self.bg_root},
                stop: 0.52 {self.bg_panel},
                stop: 1 #f1e8d7
            );
        }}

        QDialog {{
            background: {self.bg_root};
        }}

        QFileDialog,
        QFileDialog QWidget {{
            background: {self.bg_root};
            color: {self.text_main};
        }}

        QFileDialog QTreeView,
        QFileDialog QListView {{
            background: {self.bg_card};
            color: {self.text_main};
            border: 1px solid {self.border_soft};
            selection-background-color: {self.accent_primary};
            selection-color: white;
        }}

        QFileDialog QHeaderView::section {{
            background: {self.bg_panel};
            color: {self.text_main};
            border: 1px solid {self.border_soft};
            padding: 4px 6px;
        }}

        QMenu,
        QToolTip {{
            background: {self.bg_panel};
            color: {self.text_main};
            border: 1px solid {self.border_soft};
        }}

        QMenu::item:selected {{
            background: {self.accent_primary};
            color: white;
        }}

        QWidget#tabRoot {{
            background: transparent;
        }}

        QLabel#title {{
            font-size: 30px;
            font-weight: 700;
            letter-spacing: 0.5px;
            color: {self.text_main};
        }}

        QLabel#subtitle {{
            font-size: 14px;
            color: {self.text_muted};
            padding-bottom: 6px;
        }}

        QFrame#panel {{
            background: {self.bg_panel};
            border: 1px solid {self.border_soft};
            border-radius: 14px;
        }}

        QFrame#card {{
            background: {self.bg_card};
            border: 1px solid {self.border_soft};
            border-radius: 12px;
        }}

        QFrame#cardAlt {{
            background: {self.bg_card_alt};
            border: 1px solid {self.border_soft};
            border-radius: 12px;
        }}

        QLabel#metricValue {{
            font-size: 24px;
            font-weight: 700;
        }}

        QLabel#metricLabel {{
            font-size: 12px;
            color: {self.text_muted};
            text-transform: uppercase;
            letter-spacing: 0.8px;
        }}

        QLabel#badgeOk {{
            color: white;
            background: {self.ok};
            border-radius: 8px;
            padding: 2px 8px;
            font-size: 11px;
            font-weight: 700;
        }}

        QLabel#badgeWarn {{
            color: white;
            background: {self.warn};
            border-radius: 8px;
            padding: 2px 8px;
            font-size: 11px;
            font-weight: 700;
        }}

        QLabel#badgeDanger {{
            color: white;
            background: {self.danger};
            border-radius: 8px;
            padding: 2px 8px;
            font-size: 11px;
            font-weight: 700;
        }}

        QPushButton {{
            border: 1px solid {self.border_strong};
            border-radius: 10px;
            background: #fcf5e9;
            padding: 8px 14px;
            font-weight: 600;
        }}

        QPushButton:hover {{
            background: #f7ecd8;
        }}

        QPushButton:pressed {{
            background: #efddbe;
        }}

        QPushButton#primary {{
            color: white;
            background: {self.accent_primary};
            border: 1px solid #0a635c;
        }}

        QPushButton#primary:hover {{
            background: #0d7c73;
        }}

        QPushButton#danger {{
            color: white;
            background: {self.danger};
            border: 1px solid #8d2828;
        }}

        QLineEdit,
        QComboBox,
        QPlainTextEdit,
        QListWidget {{
            background: {self.bg_card};
            border: 1px solid {self.border_soft};
            border-radius: 10px;
            padding: 6px 8px;
            selection-background-color: {self.accent_primary};
            selection-color: white;
        }}

        QComboBox::drop-down {{
            border: none;
            background: transparent;
            width: 24px;
        }}

        QComboBox QAbstractItemView,
        QAbstractItemView,
        QListView,
        QTreeView,
        QTableView {{
            background: {self.bg_card};
            color: {self.text_main};
            border: 1px solid {self.border_soft};
            selection-background-color: {self.accent_primary};
            selection-color: white;
            outline: 0;
        }}

        QAbstractScrollArea,
        QScrollArea,
        QScrollArea > QWidget > QWidget {{
            background: transparent;
        }}

        QAbstractScrollArea::viewport,
        QPlainTextEdit::viewport,
        QTextEdit::viewport {{
            background: {self.bg_card};
            color: {self.text_main};
        }}

        QScrollBar:vertical {{
            background: {self.bg_panel};
            width: 12px;
            border: 1px solid {self.border_soft};
            border-radius: 6px;
            margin: 0;
        }}

        QScrollBar::handle:vertical {{
            background: #d4c6ad;
            min-height: 26px;
            border-radius: 6px;
        }}

        QScrollBar::handle:vertical:hover {{
            background: #c4b18f;
        }}

        QScrollBar:horizontal {{
            background: {self.bg_panel};
            height: 12px;
            border: 1px solid {self.border_soft};
            border-radius: 6px;
            margin: 0;
        }}

        QScrollBar::handle:horizontal {{
            background: #d4c6ad;
            min-width: 26px;
            border-radius: 6px;
        }}

        QScrollBar::handle:horizontal:hover {{
            background: #c4b18f;
        }}

        QScrollBar::add-line,
        QScrollBar::sub-line,
        QScrollBar::add-page,
        QScrollBar::sub-page {{
            background: transparent;
            border: none;
        }}

        QTabWidget::pane {{
            border: 1px solid {self.border_soft};
            border-radius: 12px;
            background: rgba(255, 250, 241, 170);
            margin-top: 8px;
        }}

        QTabBar::tab {{
            border: 1px solid {self.border_soft};
            border-bottom: none;
            border-top-left-radius: 10px;
            border-top-right-radius: 10px;
            padding: 8px 14px;
            margin-right: 4px;
            background: #efe6d5;
            color: {self.text_muted};
            font-weight: 600;
        }}

        QTabBar::tab:selected {{
            background: {self.bg_panel};
            color: {self.text_main};
        }}

        QLabel#monoBlock,
        QPlainTextEdit#monoBlock {{
            font-family: {self.font_mono};
            color: {self.text_muted};
            font-size: 12px;
        }}
        """
