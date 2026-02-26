"""
K-Trader Master v6.2 - UI 스타일시트
[개선] 모던 Slate(다크 블루-그레이) 테마 적용으로 가독성 및 세련미 극대화
"""

# 컬러 팔레트 (최신 웹 트렌드 Slate 다크 테마 기반)
COLORS = {
    "bg_primary":     "#0f172a",   # 아주 깊고 세련된 메인 배경 (Slate 900)
    "bg_secondary":   "#1e293b",   # 패널 및 탭 배경 (Slate 800)
    "bg_card":        "#334155",   # 강조된 헤더 및 포인트 영역 (Slate 700)
    "bg_input":       "#020617",   # 입력창은 더 어둡게 하여 확실한 대비 (Slate 950)
    "bg_table":       "#1e293b",   # 테이블 기본 배경
    "bg_table_alt":   "#0f172a",   # 테이블 줄무늬 (배경과 동일하게 하여 자연스럽게)
    "text_primary":   "#f8fafc",   # 눈이 편안한 맑은 흰색 (Slate 50)
    "text_secondary": "#94a3b8",   # 보조 텍스트 (Slate 400)
    "text_bright":    "#ffffff",   # 완전 흰색
    "accent_blue":    "#38bdf8",   # 모던한 스카이 블루 (선택, 포커스)
    "accent_green":   "#34d399",   # 세련된 에메랄드 그린 (가동중)
    "profit_red":     "#f87171",   # 산뜻하고 가독성 좋은 수익 빨강 (한국식)
    "loss_blue":      "#60a5fa",   # 눈에 띄는 손실 파랑 (한국식)
    "warning_orange": "#fbbf24",   # 경고 주황
    "danger_red":     "#ef4444",   # 에러/위험
    "profit_green":   "#34d399",   # 매수 성공 색상
    "loss_red":       "#f87171",   # 스킵 색상
    "border":         "#475569",   # 뚜렷하고 고급스러운 경계선 (Slate 600)
    "hover":          "#334155",   # 마우스 오버 시 색상
    "pressed":        "#0f172a",   # 클릭 시 색상
    "disabled":       "#475569",   # 비활성 테두리
    "disabled_bg":    "#1e293b",   # 비활성 배경
}


DARK_THEME_QSS = f"""
/* ═══════════════════ 전역 ═══════════════════ */
QMainWindow, QWidget {{
    background-color: {COLORS['bg_primary']};
    color: {COLORS['text_primary']};
    font-family: 'Pretendard', 'Malgun Gothic', 'Segoe UI', sans-serif;
    font-size: 13px; /* 가독성을 위해 기존 12px에서 13px로 증가 */
}}

/* ═══════════════════ 그룹박스 ═══════════════════ */
QGroupBox {{
    background-color: {COLORS['bg_secondary']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    margin-top: 16px;
    padding: 18px 12px 12px 12px;
    font-weight: bold;
    font-size: 14px;
    color: {COLORS['accent_blue']};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 4px 14px;
    background-color: {COLORS['bg_card']};
    color: {COLORS['text_bright']};
    border-radius: 6px;
    margin-left: 10px;
}}

/* ═══════════════════ 레이블 ═══════════════════ */
QLabel {{
    color: {COLORS['text_primary']};
    font-size: 13px;
    padding: 2px;
}}

/* ═══════════════════ 입력 필드 ═══════════════════ */
QLineEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {COLORS['bg_input']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    selection-background-color: {COLORS['accent_blue']};
    selection-color: {COLORS['bg_input']};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 2px solid {COLORS['accent_blue']};
    background-color: {COLORS['bg_secondary']};
}}

/* ═══════════════════ 콤보박스 ═══════════════════ */
QComboBox {{
    background-color: {COLORS['bg_input']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    min-width: 100px;
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background-color: {COLORS['bg_secondary']};
    color: {COLORS['text_primary']};
    selection-background-color: {COLORS['hover']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
}}

/* ═══════════════════ 리스트 ═══════════════════ */
QListWidget {{
    background-color: {COLORS['bg_input']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    font-size: 13px;
    padding: 4px;
}}
QListWidget::item {{
    padding: 6px 8px;
    border-radius: 4px;
}}
QListWidget::item:selected {{
    background-color: {COLORS['hover']};
    color: {COLORS['accent_blue']};
    font-weight: bold;
}}

/* 비활성화 상태 처리 */
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, 
QComboBox:disabled, QListWidget:disabled {{
    background-color: {COLORS['disabled_bg']};
    color: {COLORS['text_secondary']};
    border: 1px solid {COLORS['disabled']};
}}

/* ═══════════════════ 체크박스 ═══════════════════ */
QCheckBox {{
    color: {COLORS['text_primary']};
    spacing: 8px;
    font-size: 13px;
}}
QCheckBox::indicator {{
    width: 18px; height: 18px;
    border: 2px solid {COLORS['border']};
    border-radius: 4px;
    background-color: {COLORS['bg_input']};
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

/* ═══════════════════ 버튼 ═══════════════════ */
QPushButton {{
    background-color: {COLORS['bg_card']};
    color: {COLORS['text_bright']};
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: bold;
}}
QPushButton:hover {{
    background-color: {COLORS['accent_blue']};
    color: {COLORS['bg_primary']};
}}
QPushButton:pressed {{
    background-color: {COLORS['pressed']};
}}
QPushButton:disabled {{
    background-color: {COLORS['disabled']};
    color: {COLORS['text_secondary']};
}}

/* 메인 시작 버튼 (모던 플랫 디자인) */
QPushButton#btn_start {{
    background-color: #2563eb; /* Blue 600 */
    color: white;
    font-size: 16px;
    min-height: 50px;
    border-radius: 8px;
}}
QPushButton#btn_start:hover {{
    background-color: #1d4ed8; /* Blue 700 */
}}
QPushButton#btn_start[trading="true"] {{
    background-color: #059669; /* Emerald 600 */
}}

/* 메인 종료 버튼 */
QPushButton#btn_exit {{
    background-color: #3f3f46; /* Zinc 700 */
    color: #fca5a5;
    font-size: 16px;
    min-height: 50px;
    border-radius: 8px;
}}
QPushButton#btn_exit:hover {{
    background-color: #dc2626; /* Red 600 */
    color: white;
}}

/* 수동매도 버튼 */
QPushButton#btn_manual_sell {{
    background-color: #4c1d95; /* Violet 900 */
    color: #ddd6fe;
    border-radius: 4px;
    padding: 4px 10px;
    font-size: 12px;
}}
QPushButton#btn_manual_sell:hover {{
    background-color: #7c3aed; /* Violet 600 */
    color: white;
}}

/* ═══════════════════ 테이블 ═══════════════════ */
QTableWidget {{
    background-color: {COLORS['bg_table']};
    alternate-background-color: {COLORS['bg_table_alt']}; 
    color: {COLORS['text_primary']};
    gridline-color: {COLORS['border']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    font-size: 13px;
    selection-background-color: {COLORS['hover']};
}}
QTableWidget::item {{
    padding: 6px 8px;
}}
QHeaderView::section {{
    background-color: {COLORS['bg_card']};
    color: {COLORS['text_primary']};
    border: none;
    border-right: 1px solid {COLORS['border']};
    border-bottom: 1px solid {COLORS['border']};
    padding: 8px;
    font-weight: bold;
    font-size: 12px;
}}

/* ═══════════════════ 로그 창 ═══════════════════ */
QTextEdit#log_window {{
    background-color: {COLORS['bg_input']};
    color: {COLORS['accent_green']};
    font-family: 'Consolas', 'D2Coding', monospace;
    font-size: 12px;
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    padding: 8px;
}}

/* ═══════════════════ 탭 위젯 ═══════════════════ */
QTabWidget::pane {{
    background-color: {COLORS['bg_secondary']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    border-top-left-radius: 0px;
}}
QTabBar::tab {{
    background-color: {COLORS['bg_primary']};
    color: {COLORS['text_secondary']};
    border: 1px solid {COLORS['border']};
    border-bottom: none;
    padding: 10px 20px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: bold;
}}
QTabBar::tab:selected {{
    background-color: {COLORS['bg_secondary']};
    color: {COLORS['accent_blue']};
}}

/* ═══════════════════ 스크롤바 ═══════════════════ */
QScrollBar:vertical {{
    background-color: {COLORS['bg_primary']};
    width: 12px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background-color: {COLORS['border']};
    border-radius: 6px;
    min-height: 20px;
    margin: 2px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: {COLORS['text_secondary']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}

QScrollBar:horizontal {{
    background-color: {COLORS['bg_primary']};
    height: 12px;
    border: none;
}}
QScrollBar::handle:horizontal {{
    background-color: {COLORS['border']};
    border-radius: 6px;
    min-width: 20px;
    margin: 2px;
}}
QScrollBar::handle:horizontal:hover {{
    background-color: {COLORS['text_secondary']};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}

/* ═══════════════════ 시스템 트레이 ═══════════════════ */
QMenu {{
    background-color: {COLORS['bg_secondary']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 20px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background-color: {COLORS['hover']};
    color: {COLORS['accent_blue']};
}}

/* 설정 섹션 구분선 */
QFrame#section_divider {{
    background-color: {COLORS['border']};
    max-height: 1px;
    margin: 4px 0px;
}}
QLabel#section_header {{
    color: {COLORS['accent_blue']};
    font-weight: bold; font-size: 12px;
    padding: 2px 8px; border-left: 3px solid {COLORS['accent_blue']};
}}
QLabel#section_header_orange {{
    color: {COLORS['warning_orange']};
    font-weight: bold; font-size: 12px;
    padding: 2px 8px; border-left: 3px solid {COLORS['warning_orange']};
}}
QLabel#section_header_purple {{
    color: #c084fc;
    font-weight: bold; font-size: 12px;
    padding: 2px 8px; border-left: 3px solid #c084fc;
}}
QLabel#setting_label {{
    color: {COLORS['text_secondary']};
    font-size: 12px; padding: 0px 2px;
}}
"""

# 동적 스타일 (수익/손실 색상)
def profit_color(value) -> str:
    """수익은 산뜻한 빨강(한국식), 손실은 밝은 파랑, 0은 회색."""
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