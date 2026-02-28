"""
K-Trader Master v7.6 - UI 스타일시트
[개선] 미드톤 Navy Twilight 테마 — 어둡지 않고 너무 밝지 않은 중간 톤
      Bento Grid 카드 구조 + 눈에 편안한 다크-네이비 팔레트
"""

# ── 컬러 팔레트 (Mid-Tone Navy Twilight Theme) ──────────────────────
COLORS = {
    # 배경 (중간 밝기 다크 네이비)
    "bg_primary":     "#1E2D40",   # 메인 배경 (중간 다크 네이비)
    "bg_secondary":   "#243347",   # 카드/패널 배경 (살짝 밝은 네이비)
    "bg_card":        "#1A2535",   # 테이블 헤더, 구분 영역 (살짝 어두운 네이비)
    "bg_input":       "#2C3E54",   # 입력창 배경 (블루-슬레이트)
    "bg_table":       "#243347",   # 테이블 기본 배경
    "bg_table_alt":   "#1E2D40",   # 테이블 줄무늬

    # 텍스트 (밝은 색 — 다크 배경에 가독성)
    "text_primary":   "#E2E8F0",   # 기본 텍스트 (Slate 200)
    "text_secondary": "#94A3B8",   # 보조 텍스트 (Slate 400)
    "text_bright":    "#F8FAFC",   # 강조 텍스트 (near white)

    # 포인트 컬러 (다크 배경에 밝게)
    "accent_blue":    "#60A5FA",   # 메인 블루 (Blue 400 — 다크bg용)
    "accent_green":   "#34D399",   # 에메랄드 그린 (Emerald 400)

    # 트레이딩 색상 (한국식: 수익=빨강, 손실=파랑)
    "profit_red":     "#F87171",   # 수익/상승 빨강 (Red 400 — 다크bg용)
    "loss_blue":      "#60A5FA",   # 손실/하락 파랑 (Blue 400)
    "profit_green":   "#34D399",   # 매수 성공 (Emerald 400)
    "loss_red":       "#F87171",   # 매도/손절

    # 경고/위험
    "warning_orange": "#FBBF24",   # 경고 주황 (Amber 400)
    "danger_red":     "#F87171",   # 에러/위험

    # 테두리 & 상태
    "border":         "#334155",   # 기본 경계선 (Slate 700)
    "hover":          "#2D4060",   # 마우스 오버 (네이비 밝게)
    "pressed":        "#3B526B",   # 클릭
    "disabled":       "#334155",   # 비활성 테두리
    "disabled_bg":    "#1A2535",   # 비활성 배경
}


# ── QSS ─────────────────────────────────────────────────────────────
DARK_THEME_QSS = f"""
/* ════════════════ 전역 ════════════════ */
QMainWindow, QWidget {{
    background-color: {COLORS['bg_primary']};
    color: {COLORS['text_primary']};
    font-family: 'Pretendard', 'Malgun Gothic', 'Segoe UI', sans-serif;
    font-size: 13px;
}}

/* ════════════════ 그룹박스 (카드) ════════════════ */
QGroupBox {{
    background-color: {COLORS['bg_secondary']};
    border: 1px solid {COLORS['border']};
    border-radius: 12px;
    margin-top: 18px;
    padding: 18px 14px 14px 14px;
    font-weight: bold;
    font-size: 13px;
    color: {COLORS['accent_blue']};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 4px 12px;
    background-color: {COLORS['bg_secondary']};
    color: {COLORS['accent_blue']};
    border-radius: 8px;
    margin-left: 12px;
    font-size: 12px;
    font-weight: bold;
}}

/* ════════════════ 레이블 ════════════════ */
QLabel {{
    color: {COLORS['text_primary']};
    font-size: 13px;
    padding: 2px;
    background-color: transparent;
}}

/* ════════════════ 입력 필드 ════════════════ */
QLineEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {COLORS['bg_input']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 13px;
    selection-background-color: {COLORS['accent_blue']};
    selection-color: #FFFFFF;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 2px solid {COLORS['accent_blue']};
    background-color: {COLORS['bg_input']};
}}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover {{
    border: 1px solid {COLORS['accent_blue']};
}}

/* ════════════════ 콤보박스 ════════════════ */
QComboBox {{
    background-color: {COLORS['bg_input']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 13px;
    min-width: 100px;
}}
QComboBox:hover {{
    border: 1px solid {COLORS['accent_blue']};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background-color: {COLORS['bg_secondary']};
    color: {COLORS['text_primary']};
    selection-background-color: {COLORS['hover']};
    selection-color: {COLORS['accent_blue']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    outline: none;
}}

/* ════════════════ 리스트 ════════════════ */
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
    border-radius: 6px;
}}
QListWidget::item:hover {{
    background-color: {COLORS['hover']};
}}
QListWidget::item:selected {{
    background-color: {COLORS['hover']};
    color: {COLORS['accent_blue']};
    font-weight: bold;
}}

/* 비활성화 상태 */
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled,
QComboBox:disabled, QListWidget:disabled {{
    background-color: {COLORS['disabled_bg']};
    color: {COLORS['text_secondary']};
    border: 1px solid {COLORS['disabled']};
}}

/* ════════════════ 체크박스 ════════════════ */
QCheckBox {{
    color: {COLORS['text_primary']};
    spacing: 8px;
    font-size: 13px;
    background-color: transparent;
}}
QCheckBox::indicator {{
    width: 18px; height: 18px;
    border: 1.5px solid {COLORS['border']};
    border-radius: 5px;
    background-color: {COLORS['bg_input']};
}}
QCheckBox::indicator:hover {{
    border-color: {COLORS['accent_blue']};
}}
QCheckBox::indicator:checked {{
    background-color: {COLORS['accent_blue']};
    border-color: {COLORS['accent_blue']};
}}
QCheckBox:disabled {{
    color: {COLORS['text_secondary']};
}}
QCheckBox::indicator:disabled {{
    background-color: {COLORS['disabled_bg']};
    border-color: {COLORS['disabled']};
}}

/* ════════════════ 버튼 (기본) ════════════════ */
QPushButton {{
    background-color: {COLORS['bg_card']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: bold;
}}
QPushButton:hover {{
    background-color: {COLORS['hover']};
    border-color: {COLORS['accent_blue']};
    color: {COLORS['accent_blue']};
}}
QPushButton:pressed {{
    background-color: {COLORS['pressed']};
    border-color: {COLORS['accent_blue']};
}}
QPushButton:disabled {{
    background-color: {COLORS['disabled_bg']};
    color: {COLORS['text_secondary']};
    border-color: {COLORS['disabled']};
}}

/* 전략 가동 버튼 */
QPushButton#btn_start {{
    background-color: #2563EB;
    color: white;
    border: none;
    font-size: 15px;
    min-height: 44px;
    border-radius: 10px;
}}
QPushButton#btn_start:hover {{
    background-color: #3B82F6;
}}
QPushButton#btn_start[trading="true"] {{
    background-color: #059669;
}}
QPushButton#btn_start[trading="true"]:hover {{
    background-color: #10B981;
}}

/* 종료 버튼 */
QPushButton#btn_exit {{
    background-color: {COLORS['bg_card']};
    color: {COLORS['text_secondary']};
    border: 1px solid {COLORS['border']};
    font-size: 15px;
    min-height: 44px;
    border-radius: 10px;
}}
QPushButton#btn_exit:hover {{
    background-color: rgba(248, 113, 113, 0.15);
    border-color: {COLORS['danger_red']};
    color: {COLORS['danger_red']};
}}

/* 접속 끊기 / 재연결 버튼 */
QPushButton#btn_disconnect {{
    background-color: rgba(96, 165, 250, 0.12);
    color: {COLORS['accent_blue']};
    border: 1.5px solid rgba(96, 165, 250, 0.35);
    font-size: 15px;
    min-height: 44px;
    border-radius: 10px;
}}
QPushButton#btn_disconnect:hover {{
    background-color: rgba(96, 165, 250, 0.22);
    border-color: {COLORS['accent_blue']};
}}

/* 수동매도 버튼 */
QPushButton#btn_manual_sell {{
    background-color: rgba(248, 113, 113, 0.12);
    color: {COLORS['danger_red']};
    border: 1px solid rgba(248, 113, 113, 0.35);
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 12px;
}}
QPushButton#btn_manual_sell:hover {{
    background-color: rgba(248, 113, 113, 0.22);
    border-color: {COLORS['danger_red']};
}}

/* ════════════════ 테이블 ════════════════ */
QTableWidget {{
    background-color: {COLORS['bg_table']};
    alternate-background-color: {COLORS['bg_table_alt']};
    color: {COLORS['text_primary']};
    gridline-color: {COLORS['border']};
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
    font-size: 13px;
    selection-background-color: {COLORS['hover']};
    selection-color: {COLORS['accent_blue']};
    outline: none;
}}
QTableWidget::item {{
    padding: 7px 10px;
    border-bottom: 1px solid #F1F5F9;
}}
QTableWidget::item:selected {{
    background-color: {COLORS['hover']};
    color: {COLORS['accent_blue']};
}}
QHeaderView::section {{
    background-color: {COLORS['bg_card']};
    color: {COLORS['text_secondary']};
    border: none;
    border-right: 1px solid {COLORS['border']};
    border-bottom: 1px solid {COLORS['border']};
    padding: 8px 10px;
    font-weight: bold;
    font-size: 11px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}}

/* ════════════════ 로그 창 ════════════════ */
QTextEdit#log_window {{
    background-color: {COLORS['bg_input']};
    color: {COLORS['text_secondary']};
    font-family: 'Consolas', 'D2Coding', monospace;
    font-size: 12px;
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
    padding: 8px;
}}

/* ════════════════ 탭 위젯 ════════════════ */
QTabWidget::pane {{
    background-color: {COLORS['bg_secondary']};
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
    border-top-left-radius: 0px;
}}
QTabBar::tab {{
    background-color: {COLORS['bg_card']};
    color: {COLORS['text_secondary']};
    border: 1px solid {COLORS['border']};
    border-bottom: none;
    padding: 9px 18px;
    margin-right: 2px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    font-weight: bold;
    font-size: 13px;
}}
QTabBar::tab:hover {{
    background-color: {COLORS['hover']};
    color: {COLORS['accent_blue']};
}}
QTabBar::tab:selected {{
    background-color: {COLORS['bg_secondary']};
    color: {COLORS['accent_blue']};
    border-bottom: 2px solid {COLORS['accent_blue']};
}}

/* ════════════════ 스크롤바 ════════════════ */
QScrollBar:vertical {{
    background-color: transparent;
    width: 8px;
    border: none;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background-color: {COLORS['border']};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: #64748B;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}

QScrollBar:horizontal {{
    background-color: transparent;
    height: 8px;
    border: none;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background-color: {COLORS['border']};
    border-radius: 4px;
    min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{
    background-color: #64748B;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}

/* ════════════════ 트레이 메뉴 ════════════════ */
QMenu {{
    background-color: {COLORS['bg_secondary']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{
    padding: 7px 20px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background-color: {COLORS['hover']};
    color: {COLORS['accent_blue']};
}}

/* ════════════════ 섹션 레이블 ════════════════ */
QFrame#section_divider {{
    background-color: {COLORS['border']};
    max-height: 1px;
    margin: 4px 0px;
}}
QLabel#section_header {{
    color: {COLORS['accent_blue']};
    font-weight: bold;
    font-size: 12px;
    padding: 2px 8px;
    border-left: 3px solid {COLORS['accent_blue']};
    background-color: transparent;
}}
QLabel#section_header_orange {{
    color: {COLORS['warning_orange']};
    font-weight: bold;
    font-size: 12px;
    padding: 2px 8px;
    border-left: 3px solid {COLORS['warning_orange']};
    background-color: transparent;
}}
QLabel#section_header_purple {{
    color: #7C3AED;
    font-weight: bold;
    font-size: 12px;
    padding: 2px 8px;
    border-left: 3px solid #7C3AED;
    background-color: transparent;
}}
QLabel#setting_label {{
    color: {COLORS['text_secondary']};
    font-size: 12px;
    padding: 0px 2px;
    background-color: transparent;
}}
"""


# ── 동적 스타일 (수익/손실 색상) ────────────────────────────────────
def profit_color(value) -> str:
    """수익은 빨강(한국식), 손실은 파랑, 0은 회색."""
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
    """수익률 셀의 인라인 스타일 (웹/라벨 혼용)"""
    try:
        r = float(rate)
        color = profit_color(r)
        weight = "bold" if abs(r) >= 1.0 else "normal"
        return f"color: {color}; font-weight: {weight};"
    except (ValueError, TypeError):
        return f"color: {COLORS['text_secondary']}; font-weight: normal;"
