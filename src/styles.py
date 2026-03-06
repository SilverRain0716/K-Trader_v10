"""
K-Trader - UI 스타일시트
[Redesign] Deep Navy / Terminal 테마
"""

COLORS = {
    "bg_primary":     "#0d1117",
    "bg_secondary":   "#111820",
    "bg_card":        "#161f2b",
    "bg_input":       "#1c2a38",
    "bg_table":       "#111820",
    "bg_table_alt":   "#0d1117",
    "text_primary":   "#e2eaf5",
    "text_secondary": "#7a9bb5",
    "text_bright":    "#f0f6ff",
    "accent_blue":    "#4da3ff",
    "accent_green":   "#00d68f",
    "profit_red":     "#ff6b6b",
    "loss_blue":      "#60a5fa",
    "profit_green":   "#00d68f",
    "loss_red":       "#ff6b6b",
    "warning_orange": "#ffb347",
    "danger_red":     "#ff6b6b",
    "border":         "rgba(77,163,255,0.12)",
    "border2":        "rgba(77,163,255,0.25)",
    "hover":          "#1c2f44",
    "pressed":        "#223040",
    "disabled":       "#1c2a38",
    "disabled_bg":    "#111820",
}

DARK_THEME_QSS = f"""
QMainWindow, QWidget {{
    background-color: {COLORS['bg_primary']};
    color: {COLORS['text_primary']};
    font-family: 'Pretendard', 'Malgun Gothic', 'Segoe UI', sans-serif;
    font-size: 13px;
}}

QGroupBox {{
    background-color: {COLORS['bg_secondary']};
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
    margin-top: 20px;
    padding: 16px 14px 14px 14px;
    font-weight: bold;
    font-size: 12px;
    color: {COLORS['accent_blue']};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 3px 10px;
    background-color: {COLORS['bg_card']};
    color: {COLORS['accent_blue']};
    border: 1px solid {COLORS['border']};
    border-radius: 5px;
    margin-left: 12px;
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 0.06em;
}}

QLabel {{
    color: {COLORS['text_primary']};
    font-size: 13px;
    background-color: transparent;
}}

QLineEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {COLORS['bg_input']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    padding: 5px 9px;
    font-size: 13px;
    font-family: 'Consolas', 'D2Coding', monospace;
    selection-background-color: {COLORS['accent_blue']};
    selection-color: #fff;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {COLORS['accent_blue']};
}}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover {{
    border: 1px solid {COLORS['border2']};
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background-color: {COLORS['bg_card']};
    border: none;
    border-radius: 3px;
    width: 16px;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: {COLORS['hover']};
}}

QComboBox {{
    background-color: {COLORS['bg_input']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    padding: 5px 9px;
    font-size: 13px;
    min-width: 90px;
}}
QComboBox:hover {{ border: 1px solid {COLORS['border2']}; }}
QComboBox:focus {{ border: 1px solid {COLORS['accent_blue']}; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background-color: {COLORS['bg_card']};
    color: {COLORS['text_primary']};
    selection-background-color: {COLORS['hover']};
    selection-color: {COLORS['accent_blue']};
    border: 1px solid {COLORS['border2']};
    border-radius: 6px;
    outline: none;
    padding: 4px;
}}
QComboBox QAbstractItemView::item {{
    padding: 6px 10px;
    border-radius: 4px;
    min-height: 22px;
}}

QListWidget {{
    background-color: {COLORS['bg_input']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    font-size: 13px;
    padding: 4px;
    outline: none;
}}
QListWidget::item {{
    padding: 7px 10px;
    border-radius: 5px;
    color: {COLORS['text_secondary']};
}}
QListWidget::item:hover {{
    background-color: {COLORS['hover']};
    color: {COLORS['text_primary']};
}}
QListWidget::item:selected {{
    background-color: rgba(77,163,255,0.14);
    color: {COLORS['accent_blue']};
    font-weight: bold;
    border: 1px solid rgba(77,163,255,0.25);
}}

QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled,
QComboBox:disabled, QListWidget:disabled {{
    background-color: {COLORS['disabled_bg']};
    color: {COLORS['text_secondary']};
    border: 1px solid {COLORS['disabled']};
}}

QCheckBox {{
    color: {COLORS['text_primary']};
    spacing: 8px;
    font-size: 13px;
    background-color: transparent;
}}
QCheckBox::indicator {{
    width: 34px;
    height: 18px;
    border-radius: 9px;
    border: 1px solid {COLORS['border2']};
    background-color: {COLORS['bg_card']};
}}
QCheckBox::indicator:hover {{ border-color: {COLORS['accent_blue']}; }}
QCheckBox::indicator:checked {{
    background-color: rgba(77,163,255,0.25);
    border-color: {COLORS['accent_blue']};
}}
QCheckBox:disabled {{ color: {COLORS['text_secondary']}; }}
QCheckBox::indicator:disabled {{
    background-color: {COLORS['disabled_bg']};
    border-color: {COLORS['disabled']};
}}

QPushButton {{
    background-color: {COLORS['bg_card']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 7px;
    padding: 7px 15px;
    font-size: 13px;
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: {COLORS['hover']};
    border-color: {COLORS['border2']};
    color: {COLORS['accent_blue']};
}}
QPushButton:pressed {{ background-color: {COLORS['pressed']}; }}
QPushButton:disabled {{
    background-color: {COLORS['disabled_bg']};
    color: {COLORS['text_secondary']};
    border-color: {COLORS['disabled']};
}}

QPushButton#btn_start {{
    background-color: rgba(0,97,255,0.2);
    color: #60a5fa;
    border: 1px solid rgba(96,165,250,0.35);
    font-size: 15px;
    font-weight: 700;
    min-height: 42px;
    border-radius: 9px;
}}
QPushButton#btn_start:hover {{
    background-color: rgba(0,97,255,0.3);
    border-color: #60a5fa;
}}
QPushButton#btn_start[trading="true"] {{
    background-color: rgba(0,214,143,0.15);
    color: {COLORS['accent_green']};
    border: 1px solid rgba(0,214,143,0.35);
}}
QPushButton#btn_start[trading="true"]:hover {{
    background-color: rgba(0,214,143,0.25);
    border-color: {COLORS['accent_green']};
}}

QPushButton#btn_exit {{
    background-color: transparent;
    color: {COLORS['text_secondary']};
    border: 1px solid {COLORS['border']};
    font-size: 15px;
    font-weight: 600;
    min-height: 42px;
    border-radius: 9px;
}}
QPushButton#btn_exit:hover {{
    background-color: rgba(255,107,107,0.1);
    border-color: rgba(255,107,107,0.4);
    color: {COLORS['danger_red']};
}}

QPushButton#btn_disconnect {{
    background-color: rgba(77,163,255,0.08);
    color: {COLORS['text_secondary']};
    border: 1px solid {COLORS['border']};
    font-size: 15px;
    font-weight: 600;
    min-height: 42px;
    border-radius: 9px;
}}
QPushButton#btn_disconnect:hover {{
    background-color: rgba(77,163,255,0.15);
    border-color: {COLORS['border2']};
    color: {COLORS['accent_blue']};
}}

QPushButton#btn_manual_sell {{
    background-color: rgba(255,107,107,0.1);
    color: {COLORS['danger_red']};
    border: 1px solid rgba(255,107,107,0.25);
    border-radius: 5px;
    padding: 3px 6px;
    font-size: 12px;
}}
QPushButton#btn_manual_sell:hover {{
    background-color: rgba(255,107,107,0.2);
    border-color: rgba(255,107,107,0.5);
}}

QTableWidget {{
    background-color: {COLORS['bg_table']};
    alternate-background-color: {COLORS['bg_table_alt']};
    color: {COLORS['text_primary']};
    gridline-color: rgba(77,163,255,0.07);
    border: 1px solid {COLORS['border']};
    border-radius: 9px;
    font-size: 13px;
    selection-background-color: {COLORS['hover']};
    selection-color: {COLORS['accent_blue']};
    outline: none;
}}
QTableWidget::item {{
    padding: 8px 10px;
    border-bottom: 1px solid rgba(77,163,255,0.05);
}}
QTableWidget::item:selected {{
    background-color: rgba(77,163,255,0.12);
    color: {COLORS['accent_blue']};
}}
QHeaderView::section {{
    background-color: {COLORS['bg_card']};
    color: #b8cfe8;
    border: none;
    border-right: 1px solid {COLORS['border']};
    border-bottom: 2px solid rgba(77,163,255,0.3);
    padding: 8px 10px;
    font-weight: 700;
    font-size: 12px;
    letter-spacing: 0.03em;
}}

QTextEdit#log_window {{
    background-color: {COLORS['bg_input']};
    color: {COLORS['text_secondary']};
    font-family: 'Consolas', 'D2Coding', monospace;
    font-size: 12px;
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 8px;
}}

QTabWidget::pane {{
    background-color: {COLORS['bg_secondary']};
    border: 1px solid {COLORS['border']};
    border-radius: 9px;
    border-top-left-radius: 0px;
}}
QTabBar::tab {{
    background-color: transparent;
    color: {COLORS['text_secondary']};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 8px 18px;
    margin-right: 2px;
    font-weight: 600;
    font-size: 13px;
}}
QTabBar::tab:hover {{
    color: {COLORS['text_primary']};
    border-bottom: 2px solid {COLORS['border2']};
}}
QTabBar::tab:selected {{
    color: {COLORS['accent_blue']};
    border-bottom: 2px solid {COLORS['accent_blue']};
}}

QScrollBar:vertical {{
    background-color: transparent;
    width: 6px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background-color: rgba(77,163,255,0.2);
    border-radius: 3px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{ background-color: rgba(77,163,255,0.4); }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

QScrollBar:horizontal {{
    background-color: transparent;
    height: 6px;
    border: none;
}}
QScrollBar::handle:horizontal {{
    background-color: rgba(77,163,255,0.2);
    border-radius: 3px;
    min-width: 20px;
}}
QScrollBar::handle:horizontal:hover {{ background-color: rgba(77,163,255,0.4); }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

QMenu {{
    background-color: {COLORS['bg_card']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border2']};
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{ padding: 7px 20px; border-radius: 5px; }}
QMenu::item:selected {{
    background-color: {COLORS['hover']};
    color: {COLORS['accent_blue']};
}}
QMenu::separator {{
    height: 1px;
    background-color: {COLORS['border']};
    margin: 3px 8px;
}}

QFrame#section_divider {{
    background-color: {COLORS['border']};
    max-height: 1px;
    margin: 6px 0;
}}
QLabel#section_header {{
    color: {COLORS['accent_blue']};
    font-weight: 700;
    font-size: 11px;
    padding: 2px 8px;
    border-left: 3px solid {COLORS['accent_blue']};
    background-color: transparent;
    letter-spacing: 0.06em;
}}
QLabel#section_header_orange {{
    color: {COLORS['warning_orange']};
    font-weight: 700;
    font-size: 11px;
    padding: 2px 8px;
    border-left: 3px solid {COLORS['warning_orange']};
    background-color: transparent;
    letter-spacing: 0.06em;
}}
QLabel#section_header_purple {{
    color: #a78bfa;
    font-weight: 700;
    font-size: 11px;
    padding: 2px 8px;
    border-left: 3px solid #a78bfa;
    background-color: transparent;
    letter-spacing: 0.06em;
}}
QLabel#setting_label {{
    color: {COLORS['text_secondary']};
    font-size: 12px;
    padding: 0 2px;
    background-color: transparent;
}}
"""


def profit_color(value) -> str:
    try:
        val = float(value)
        if val > 0:
            return COLORS['profit_red']
        elif val < 0:
            return COLORS['loss_blue']
    except (ValueError, TypeError):
        pass
    return COLORS['text_secondary']


def yield_style(rate: float) -> str:
    try:
        r = float(rate)
        color = profit_color(r)
        weight = "bold" if abs(r) >= 1.0 else "normal"
        return f"color: {color}; font-weight: {weight};"
    except (ValueError, TypeError):
        return f"color: {COLORS['text_secondary']}; font-weight: normal;"
