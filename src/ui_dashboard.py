"""
K-Trader - UI 대시보드 (프론트엔드 프로세스)
[Phase 5] 모의/실계좌 서버 자동 감지에 따른 UI 색상 경고 시스템 추가
"""
import sys
import os
import csv
import json
import copy
import time
import logging
import datetime
import subprocess
import threading

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QGroupBox, QTabWidget, QPushButton, QLabel, QFrame,
    QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox, QLineEdit,
    QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QListWidget, QListWidgetItem, QMessageBox, QSystemTrayIcon, QMenu, QAction,
    QDialog, QSizePolicy
)
from PyQt5.QtCore import QTimer, Qt, QRect, QPropertyAnimation, QEasingCurve, pyqtProperty, pyqtSignal
from PyQt5.QtGui import QIcon, QColor, QFont, QBrush, QPainter, QPen

# PyInstaller --onedir 빌드 시 __file__은 _internal 폴더 안을 가리키므로
# sys.executable(K-Trader.exe) 기준의 폴더를 사용합니다.
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from src.database import Database
from src.config_manager import ConfigManager, SecretManager
from src.market_calendar import MarketCalendar
from src.notifications import Notifier
from src.styles import DARK_THEME_QSS, COLORS, profit_color
from src.utils import calc_sell_cost, get_user_data_dir, get_app_dir, resolve_db_path, __version__
from src.ipc import UI_IPCServer

logger = logging.getLogger("ktrader")

# [Item 1] 설치 디렉토리(읽기전용)와 앱 데이터 디렉토리(쓰기)를 분리
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_APP_DIR   = get_app_dir()
CONFIG_DIR = os.path.join(_APP_DIR, "config")
DATA_DIR   = os.path.join(_APP_DIR, "data")
LOGS_DIR   = os.path.join(_APP_DIR, "logs")
REPORTS_DIR = os.path.join(_APP_DIR, "reports")

for d in [CONFIG_DIR, DATA_DIR, LOGS_DIR, REPORTS_DIR]:
    os.makedirs(d, exist_ok=True)


class ToggleSwitch(QWidget):
    """애니메이션 토글 스위치 (QCheckBox 대체)."""

    stateChanged = pyqtSignal(int)

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._checked = False
        self._text = text
        self._circle_pos = 3.0        # 애니메이션용 원 위치
        self._anim = QPropertyAnimation(self, b"circle_pos", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.InOutQuad)
        self.setFixedHeight(22)
        self.setCursor(Qt.PointingHandCursor)
        self._update_min_width()

    def _update_min_width(self):
        fm = self.fontMetrics()
        text_w = fm.horizontalAdvance(self._text) if self._text else 0
        self.setMinimumWidth(42 + (8 + text_w if text_w else 0))

    def text(self):
        return self._text

    def setText(self, t):
        self._text = t
        self._update_min_width()
        self.update()

    def isChecked(self):
        return self._checked

    def setChecked(self, val):
        self._checked = bool(val)
        self._circle_pos = 23.0 if self._checked else 3.0
        self.update()

    def checkState(self):
        return Qt.Checked if self._checked else Qt.Unchecked

    def mousePressEvent(self, event):
        self.toggle()

    def toggle(self):
        self._checked = not self._checked
        target = 23.0 if self._checked else 3.0
        self._anim.stop()
        self._anim.setStartValue(self._circle_pos)
        self._anim.setEndValue(target)
        self._anim.start()
        self.stateChanged.emit(2 if self._checked else 0)
        self.update()

    @pyqtProperty(float)
    def circle_pos(self):
        return self._circle_pos

    @circle_pos.setter
    def circle_pos(self, val):
        self._circle_pos = val
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        track_w, track_h = 42, 22
        track_x, track_y = 0, 0

        # Track
        if self._checked:
            track_color = QColor(77, 163, 255, 60)
            border_color = QColor(77, 163, 255, 180)
        else:
            track_color = QColor(28, 42, 56)
            border_color = QColor(77, 163, 255, 50)

        p.setBrush(track_color)
        p.setPen(QPen(border_color, 1.2))
        p.drawRoundedRect(track_x, track_y, track_w, track_h, 11, 11)

        # Circle
        circle_r = 8
        cy = track_y + track_h // 2
        cx = int(self._circle_pos) + circle_r

        if self._checked:
            circle_color = QColor(77, 163, 255)
            p.setBrush(circle_color)
            p.setPen(Qt.NoPen)
        else:
            circle_color = QColor(90, 122, 153)
            p.setBrush(circle_color)
            p.setPen(Qt.NoPen)

        p.drawEllipse(cx - circle_r, cy - circle_r, circle_r * 2, circle_r * 2)

        # Text
        if self._text:
            p.setPen(QColor(226, 234, 245))
            p.setFont(self.font())
            p.drawText(track_w + 8, 0, self.width() - track_w - 8, track_h,
                       Qt.AlignVCenter | Qt.AlignLeft, self._text)

        p.end()


class IndexChartWindow(QDialog):
    """
    [v8.0] KOSPI / KOSDAQ 지수 차트 팝업 창.
    QPainter로 직접 라인차트를 렌더링합니다.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📈 지수 차트 (당일)")
        self.setMinimumSize(700, 420)
        self.resize(780, 460)
        self.setStyleSheet(f"background-color: {COLORS['bg_primary']}; color: {COLORS['text_primary']};")

        self._kospi_hist  = []   # [(ts_str, price, rate), ...]
        self._kosdaq_hist = []
        self._kospi_now   = (0, 0.0)   # (price, rate)
        self._kosdaq_now  = (0, 0.0)

        layout = QVBoxLayout()
        layout.setSpacing(4)
        layout.setContentsMargins(10, 8, 10, 8)

        # 상단: 현재값 요약
        self._summary_label = QLabel("KOSPI --  |  KOSDAQ --")
        self._summary_label.setStyleSheet(
            f"font-size: 15px; font-weight: bold; color: {COLORS['text_bright']}; padding: 4px;"
        )
        layout.addWidget(self._summary_label)

        # 차트 위젯
        self._chart = _IndexChartWidget(self)
        layout.addWidget(self._chart, stretch=1)

        # 하단: 범례
        kospi_color  = COLORS['profit_red']
        kosdaq_color = COLORS['accent_blue']
        legend = QLabel(
            f"<span style='color:{kospi_color};'>━</span> KOSPI &nbsp;&nbsp;"
            f"<span style='color:{kosdaq_color};'>━</span> KOSDAQ"
        )
        legend.setAlignment(Qt.AlignCenter)
        legend.setStyleSheet("font-size: 12px; padding: 2px;")
        layout.addWidget(legend)

        self.setLayout(layout)

    def update_data(self, kospi_hist, kosdaq_hist, kp, kr, kd_p, kd_r):
        self._kospi_hist  = kospi_hist
        self._kosdaq_hist = kosdaq_hist
        self._kospi_now   = (kp, kr)
        self._kosdaq_now  = (kd_p, kd_r)

        def _arrow(r): return "▲" if r >= 0 else "▼"
        def _col(r):   return COLORS['profit_red'] if r >= 0 else COLORS['loss_blue']

        kp_txt  = f"<span style='color:{_col(kr)};'>KOSPI {kp:,.2f} {_arrow(kr)}{abs(kr):.2f}%</span>"
        kd_txt  = f"<span style='color:{_col(kd_r)};'>KOSDAQ {kd_p:,.2f} {_arrow(kd_r)}{abs(kd_r):.2f}%</span>"
        self._summary_label.setText(f"{kp_txt} &nbsp;&nbsp;|&nbsp;&nbsp; {kd_txt}")

        self._chart.set_data(kospi_hist, kosdaq_hist)
        self._chart.update()


class _IndexChartWidget(QWidget):
    """QPainter 기반 지수 라인차트."""

    PAD_L, PAD_R, PAD_T, PAD_B = 58, 16, 20, 32

    def __init__(self, parent=None):
        super().__init__(parent)
        self._kospi_hist  = []
        self._kosdaq_hist = []

    def set_data(self, kospi_hist, kosdaq_hist):
        self._kospi_hist  = kospi_hist
        self._kosdaq_hist = kosdaq_hist

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        pl, pr, pt, pb = self.PAD_L, self.PAD_R, self.PAD_T, self.PAD_B
        cw = w - pl - pr   # 차트 폭
        ch = h - pt - pb   # 차트 높이

        # 배경
        p.fillRect(0, 0, w, h, QColor(COLORS['bg_primary']))
        p.fillRect(pl, pt, cw, ch, QColor(COLORS['bg_card']))

        # 데이터 없으면 안내
        if not self._kospi_hist and not self._kosdaq_hist:
            p.setPen(QColor(COLORS['text_secondary']))
            p.drawText(pl, pt, cw, ch, Qt.AlignCenter, "장 시작 후 데이터가 축적됩니다")
            p.end()
            return

        # 전체 가격 범위 계산 (두 지수를 각각 정규화)
        # [Fix v8.1] dead code 제거 + 각 지수별 X축 개별 스케일링

        # 등락율 기준으로 Y축 통합
        all_rates = [pt3 for hist in [self._kospi_hist, self._kosdaq_hist] for (_, _, pt3) in hist]
        if not all_rates:
            p.end()
            return

        y_min = min(all_rates) - 0.3
        y_max = max(all_rates) + 0.3
        if y_max - y_min < 0.5:
            mid = (y_max + y_min) / 2
            y_min, y_max = mid - 0.5, mid + 0.5
        y_range = y_max - y_min

        # 격자 및 0% 기준선
        p.setPen(QPen(QColor(COLORS['border']), 1, Qt.DotLine))
        for i in range(5):
            gy = pt + int(ch * i / 4)
            p.drawLine(pl, gy, pl + cw, gy)

        # 0% 기준선 강조
        if y_min < 0 < y_max:
            zero_y = pt + int(ch * (y_max / y_range))
            p.setPen(QPen(QColor(COLORS['border2']), 1, Qt.SolidLine))
            p.drawLine(pl, zero_y, pl + cw, zero_y)

        # Y축 레이블
        p.setPen(QColor(COLORS['text_secondary']))
        font = p.font(); font.setPointSize(9); p.setFont(font)
        for i in range(5):
            val = y_max - (y_range * i / 4)
            ly  = pt + int(ch * i / 4)
            p.drawText(0, ly - 8, pl - 4, 16, Qt.AlignRight | Qt.AlignVCenter, f"{val:+.1f}%")

        # 라인 그리기 (등락율 기준)
        # [Fix v8.1] 각 지수는 자체 데이터 포인트 수 기준으로 X축 스케일링
        colors_map = {"kospi": COLORS['profit_red'], "kosdaq": COLORS['accent_blue']}
        data_map   = {"kospi": self._kospi_hist, "kosdaq": self._kosdaq_hist}

        for key, color in colors_map.items():
            hist = data_map[key]
            if len(hist) < 2:
                continue
            n = len(hist)
            pen = QPen(QColor(color), 2, Qt.SolidLine)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            pts = []
            for i, (_, _, rate) in enumerate(hist):
                x = pl + int(cw * i / (n - 1))
                y = pt + int(ch * (y_max - rate) / y_range)
                pts.append((x, y))
            for i in range(1, len(pts)):
                p.drawLine(pts[i-1][0], pts[i-1][1], pts[i][0], pts[i][1])

        # X축 레이블 (최대 6개) — KOSPI 기준 (더 긴 쪽 사용)
        all_ts = [ts for ts, _, _ in self._kospi_hist] or [ts for ts, _, _ in self._kosdaq_hist]
        if all_ts:
            n_ts = len(all_ts)
            step = max(1, n_ts // 6)
            p.setPen(QColor(COLORS['text_secondary']))
            font.setPointSize(8); p.setFont(font)
            for i in range(0, n_ts, step):
                x = pl + int(cw * i / (n_ts - 1)) if n_ts > 1 else pl
                p.drawText(x - 18, h - pb + 4, 36, pb - 4, Qt.AlignCenter, all_ts[i])

        p.end()


class TradingUI(QMainWindow):
    """K-Trader v8.0 메인 UI 대시보드."""

    def __init__(self):
        super().__init__()

        self.db = Database(resolve_db_path())
        self.config_mgr = ConfigManager(CONFIG_DIR)
        self.config_mgr.load()
        self.secrets = SecretManager(CONFIG_DIR).load()
        self.notifier = Notifier(self.secrets)
        self.calendar = MarketCalendar(api_key=self.secrets.get("calendar_api_key"))

        # 설정 적용/변경 추적
        self._last_applied_config = copy.deepcopy(self.config_mgr.config)
        self._config_dirty = False
        self._last_state = {}  # 엔진 최신 상태 캐시 (컨텍스트 메뉴 등 참조용)

        # 장 상태(시간 기반) UI 갱신/알림
        self._last_market_phase = self.calendar.get_market_phase()
        self._market_open_notified_date = None

        # [Fix #8/#9] 모의/실 비밀번호 분리 관리 (secrets.json 키 연동)
        self.is_mock = True  # 안전한 기본값: 모의투자 가정
        self.engine_status = "OFFLINE"
        self.is_trading_started = False
        self.engine_proc = None
        self._engine_eod_shutdown = False  # 엔진이 EOD 정상 종료 신호를 보냈는지
        self._spawn_pending = False  # QTimer.singleShot 중복 예약 방지
        self._disconnecting = False  # 접속 끊기 중 플래그 (health_check 크래시 방지)
        self.default_conditions = self.config_mgr.get("default_conditions", ["나의급등주02"])

        self._engine_crash_count = 0
        self._max_engine_restarts = 5
        self._last_loaded_conditions = None
        self._ui_pre_market_restart_date = None  # 8:50 UI측 강제 재시작 하루 1회 플래그
        self._available_accounts = []  # 엔진에서 받은 전체 계좌 목록 (계좌변경 다이얼로그용)

        self.setWindowTitle(f"K-Trader v{__version__}")
        self.setGeometry(150, 100, 1150, 950)
        self.setStyleSheet(DARK_THEME_QSS)

        self._setup_ui()
        self._load_config_to_ui()
        self._setup_tray()

        self.ipc_server = UI_IPCServer()
        self.ipc_server.state_received.connect(self._on_state_received)
        self.ipc_server.start()

        self.auto_start_countdown = 30
        self.auto_start_timer = QTimer(self)
        self.auto_start_timer.timeout.connect(self._auto_start_tick)

        self.health_timer = QTimer(self)
        self.health_timer.timeout.connect(self._check_engine_health)
        self.health_timer.start(3000)

        self.eod_timer = QTimer(self)
        self.eod_timer.timeout.connect(self._check_eod)
        self.eod_timer.start(60000)

        self.market_timer = QTimer(self)
        self.market_timer.timeout.connect(self._tick_market_status)
        self.market_timer.start(5000)

        self._send_log(f"🚀 UI 대시보드 v{__version__} 로드 완료. IPC 포트: {self.ipc_server.port}")
        self._spawn_engine()

    def _setup_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.style().standardIcon(self.style().SP_ComputerIcon))
        self.tray.setToolTip(f"K-Trader v{__version__}")

        menu = QMenu()
        show_action = QAction("📊 대시보드 열기", self)
        show_action.triggered.connect(self.show)
        menu.addAction(show_action)

        status_action = QAction("상태: 대기 중", self)
        status_action.setEnabled(False)
        self._tray_status_action = status_action
        menu.addAction(status_action)

        menu.addSeparator()
        exit_action = QAction("❌ 종료", self)
        exit_action.triggered.connect(self._force_quit)
        menu.addAction(exit_action)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show()
            self.activateWindow()

    def changeEvent(self, event):
        # 기본 최소화는 작업표시줄에 남기고, 사용자가 옵션을 켠 경우에만 트레이로 숨깁니다.
        if event.type() == event.WindowStateChange and self.isMinimized():
            if self.config_mgr.get("minimize_to_tray", False):
                self.hide()
                self.tray.showMessage("K-Trader", "시스템 트레이에서 실행 중", QSystemTrayIcon.Information, 2000)
        super().changeEvent(event)

    def _spawn_engine(self):
        # [Fix] 엔진이 이미 살아있으면 중복 스폰 방지
        self._spawn_pending = False
        if self.engine_proc and self.engine_proc.poll() is None:
            logger.info("[UI] _spawn_engine 호출 무시: 엔진 이미 실행 중 (PID=%s)", self.engine_proc.pid)
            return

        try:
            if getattr(sys, 'frozen', False):
                # PyInstaller exe 환경: exe 자체를 "engine" 인자로 재실행
                # [주의] main.py를 인자로 넘기면 sys.argv[1]이 경로 문자열이 되어
                #        mode 판별에 실패하고 UI 모드로 진입하는 버그가 생김
                cmd = [sys.executable, "engine", str(self.ipc_server.port)]
            else:
                # 개발 환경: python main.py engine PORT
                main_script = os.path.join(BASE_DIR, "main.py")
                cmd = [sys.executable, main_script, "engine", str(self.ipc_server.port)]

            self.engine_proc = subprocess.Popen(
                cmd,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            logger.info(f"[UI] 엔진 프로세스 스폰 (PID: {self.engine_proc.pid}, PORT: {self.ipc_server.port})")
        except Exception as e:
            logger.error(f"❌ [UI] 엔진 스폰 실패: {e}")
            self._send_log(f"❌ 엔진 스폰 실패: {e}")

    def _check_engine_health(self):
        # UI → 엔진 heartbeat: 엔진의 last_heartbeat 갱신용 (UI 유휴 시 자폭 방지)
        try:
            self.ipc_server.send_command("PING", "")
        except Exception:
            pass

        if self.engine_proc and self.engine_proc.poll() is not None:
            exit_code = self.engine_proc.returncode

            # 사용자가 접속 끊기를 눌러서 의도적으로 종료한 경우 → 크래시 처리 안 함
            if getattr(self, '_disconnecting', False):
                self.engine_proc = None
                return

            # [Fix] EOD 신호를 받았거나 exit_code==0이면 정상 종료로 처리
            # PyInstaller+PyQt5에서 sys.exit(0)이 0xC0000409 등 비정상 코드로 전달되는 버그 대응
            if (exit_code == 0 or self._engine_eod_shutdown) and self.engine_status != "OFFLINE":
                logger.info("🌙 [UI] 엔진이 정상적으로 종료되었습니다.")
                self.status_label.setText("✅ 엔진 안전 종료 완료")
                self.status_label.setStyleSheet(f"color: {COLORS['accent_blue']};")
                self.engine_status = "OFFLINE"
                self._engine_eod_shutdown = False
                self._last_loaded_conditions = None
                self.engine_proc = None
                return
            elif exit_code == 0 and self.engine_status == "OFFLINE":
                # IPC 연결 전에 code 0으로 종료 (키움 초기화 실패 등) → 크래시로 처리
                logger.warning("⚠️ [UI] 엔진이 연결 전에 종료됨 (code 0) → 재시작 시도")
                self._send_log("⚠️ 엔진이 연결 전에 종료됨 (초기화 실패?) → 재시작 시도")
                exit_code = -1  # 이하 크래시 처리 로직으로 넘김

            logger.warning(f"⚠️ [UI] 엔진 프로세스 사망 감지 (exit={exit_code})")

            # [Fix D/E] 엔진 크래시 시 UI 잠금 해제 — 재시작 후 계좌/조건식 선택 및 가동 가능하게
            if self.is_trading_started:
                self.is_trading_started = False
                self.auto_start_countdown = 30
                self.btn_change_account.setEnabled(bool(self._available_accounts))
                self.btn_start.setText("🚀 전략 가동 시작")
                self.btn_start.setProperty("trading", "false")
                self.btn_start.style().unpolish(self.btn_start)
                self.btn_start.style().polish(self.btn_start)
                logger.info("[UI] 엔진 크래시 → is_trading_started 리셋, UI 잠금 해제")

            # [Fix Maintenance] exit_code=1 은 -101/-106 점검 단절 신호.
            # 이 경우 crash_count를 리셋하여 자동 재시작이 막히지 않도록 한다.
            if exit_code == 1:
                logger.info("[UI] exit_code=1 감지 → 키움 점검/단절로 판단, 재시작 카운터 리셋")
                self._engine_crash_count = 0

            if self._engine_crash_count < self._max_engine_restarts:
                self._engine_crash_count += 1
                # 점검 단절(exit=1)은 더 긴 대기 후 재시작 (키움 점검 종료 대기)
                if exit_code == 1:
                    delay_secs = 120  # 점검 중 → 2분 후 재시도
                else:
                    # 지수 백오프: 1회→10초, 2회→20초, 3회→40초, 4~→60초
                    delay_secs = min(10 * (2 ** (self._engine_crash_count - 1)), 60)
                self._send_log(
                    f"⚠️ 엔진 크래시 감지! {delay_secs}초 후 재시작 "
                    f"({self._engine_crash_count}/{self._max_engine_restarts})"
                )
                self.notifier.notify_error(
                    "엔진 크래시 감지",
                    f"{delay_secs}초 후 자동 재시작 시도 "
                    f"({self._engine_crash_count}/{self._max_engine_restarts})"
                )
                self._last_loaded_conditions = None
                self.engine_proc = None
                # [Fix] 이미 재시작 타이머가 예약된 경우 중복 예약 방지
                if not self._spawn_pending:
                    self._spawn_pending = True
                    QTimer.singleShot(delay_secs * 1000, self._spawn_engine)
            else:
                self._send_log("❌ 엔진 재시작 한도 초과. 수동 확인이 필요합니다.")
                self.notifier.notify_error("엔진 재시작 한도 초과", "수동 확인이 필요합니다.")
                self.engine_proc = None

        # ── 8:50 UI측 최종 안전망 ──────────────────────────────────────────
        # 엔진이 죽어서 재시작 한도를 소진했거나, 엔진이 살아있지만 키움 LOGIN_FAILED 상태가
        # 지속될 경우를 대비해 UI에서도 8:50에 강제로 엔진을 재시작합니다.
        try:
            import datetime as _dt
            now_dt = _dt.datetime.now()
            today = _dt.date.today().isoformat()
            if (now_dt.hour == 8 and now_dt.minute == 50
                    and self._ui_pre_market_restart_date != today):
                need_restart = False

                # 케이스 1: 엔진 프로세스가 아예 없음 (크래시 후 재시작 한도 소진 등)
                if self.engine_proc is None:
                    need_restart = True
                    reason = "엔진 프로세스 없음"
                # 케이스 2: 엔진은 살아있지만 키움 연결 실패 상태
                elif self.engine_status in ("LOGIN_FAILED", "LOGGING_IN"):
                    need_restart = True
                    reason = f"키움 미연결 상태 ({self.engine_status})"

                if need_restart:
                    self._ui_pre_market_restart_date = today  # 하루 1회만 실행
                    logger.warning(f"🔔 [UI] 08:50 안전망 발동: {reason} → 엔진 강제 재시작")
                    self._send_log(f"🔔 [08:50 안전망] {reason} → 엔진 강제 재시작")
                    self.notifier.discord(f"🔔 [UI 08:50 안전망] {reason} → 엔진 강제 재시작 시도")
                    # 기존 프로세스 강제 종료 후 재시작
                    if self.engine_proc:
                        try:
                            self.engine_proc.kill()
                        except Exception:
                            pass
                        self.engine_proc = None
                    self._engine_crash_count = 0   # 재시작 카운터 초기화
                    self._last_loaded_conditions = None
                    self._spawn_engine()
                else:
                    self._ui_pre_market_restart_date = today  # 정상 상태도 하루 1회 기록
                    logger.info(f"✅ [UI] 08:50 점검: 엔진 정상 ({self.engine_status})")
        except Exception as e:
            logger.error(f"❌ [UI 8:50 안전망] 오류: {e}")

    # ── secrets.json 연동 헬퍼 ──────────────────────
    def _get_account_password(self) -> str:
        """[Fix #8/#9] 현재 모의/실 모드에 맞는 비밀번호 반환."""
        if self.is_mock:
            return self.secrets.get('mock_account_password', '0000')
        return self.secrets.get('real_account_password', '')

    def _get_target_account(self) -> str:
        """[Fix #10] 현재 모의/실 모드에 맞는 허용 계좌번호 반환."""
        if self.is_mock:
            return self.secrets.get('mock_target_account', '')
        return self.secrets.get('real_target_account', '')

    def _apply_account(self, acc: str):
        """계좌를 선택/변경한다. secrets.json 갱신 + UI 표시 + 엔진에 예수금 요청."""
        if not acc:
            return
        # secrets.json의 target_account를 단일 진실의 원천으로 갱신
        key = 'mock_target_account' if self.is_mock else 'real_target_account'
        if self.secrets.get(key) != acc:
            self.secrets[key] = acc
            SecretManager(CONFIG_DIR).save(self.secrets)
            logger.info(f"[UI] target_account 갱신: {acc[:4]}****{acc[-2:]} (key={key})")

        # UI 레이블 갱신
        self.account_label.setText(f"{acc[:4]}****{acc[-2:]}")
        self._send_log(f"💳 계좌 설정: {acc[:4]}****{acc[-2:]}")

        # 엔진에 예수금 조회 요청
        self.ipc_server.send_command("REQ_DEPOSIT", f"{acc}^{self.pw_input.text()}")

    def _change_account(self):
        """실행 중 계좌 변경 다이얼로그. 엔진에서 받은 전체 계좌 목록을 보여주고 선택하게 함."""
        if not self._available_accounts:
            QMessageBox.warning(self, "계좌 정보 없음", "엔진에서 아직 계좌 정보를 받지 못했습니다.\n잠시 후 다시 시도해주세요.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("계좌 변경")
        dialog.setMinimumWidth(280)
        layout = QVBoxLayout()

        mode_text = "모의투자" if self.is_mock else "실계좌"
        layout.addWidget(QLabel(f"[{mode_text}] 사용할 계좌를 선택하세요:"))

        list_widget = QListWidget()
        current_target = self._get_target_account()
        for acc in self._available_accounts:
            masked = f"{acc[:4]}****{acc[-2:]}"
            item = QListWidgetItem(masked)
            item.setData(Qt.UserRole, acc)
            list_widget.addItem(item)
            if acc == current_target:
                list_widget.setCurrentItem(item)

        layout.addWidget(list_widget)

        btn_box = QHBoxLayout()
        btn_ok = QPushButton("✅ 선택")
        btn_cancel = QPushButton("취소")
        btn_ok.clicked.connect(dialog.accept)
        btn_cancel.clicked.connect(dialog.reject)
        btn_box.addWidget(btn_ok)
        btn_box.addWidget(btn_cancel)
        layout.addLayout(btn_box)
        dialog.setLayout(layout)

        if dialog.exec_() == QDialog.Accepted:
            selected = list_widget.currentItem()
            if selected:
                self._apply_account(selected.data(Qt.UserRole))

    def _diagnose_discord(self):
        """디스코드 웹훅 연결 상태를 즉시 점검(동기)하고, 가능하면 테스트 메시지도 전송합니다."""
        ok, detail = self.notifier.diagnose_discord()
        if ok:
            # 실제 발송까지 확인하기 위한 짧은 테스트 메시지(채널에 1회 남습니다)
            ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.notifier.discord(f"🔔 [K-Trader] 디스코드 알림 테스트 ({ts})")

        msg = ("✅ 디스코드 웹훅 정상\n" if ok else "❌ 디스코드 웹훅 문제\n") + detail
        self._send_log(f"🔔 [알림 점검] {detail}")
        QMessageBox.information(self, "알림 점검", msg)


    def _on_state_received(self, state: dict):
        self._last_state = state  # 컨텍스트 메뉴 등에서 현재 상태 참조용
        # [Fix] 엔진 EOD 정상 종료 신호 감지
        # PyInstaller+PyQt5 환경에서 sys.exit(0)이 비정상 exit code로 전달되어
        # UI가 크래시로 오인하는 문제 방지
        if state.get("eod_shutdown"):
            self._engine_eod_shutdown = True
            logger.info("🌙 [UI] 엔진 EOD 정상 종료 신호 수신")
            return
        new_status = state.get("status", "OFFLINE")

        # 엔진이 제공하는 장 상태 텍스트를 우선 사용 (UI 정확성 우선)
        phase = state.get("market_phase_text") or self.calendar.status_text()
        # 실시간/계좌 동기화 품질 신호
        deposit_stale = bool(state.get('deposit_stale', False))
        price_stale = bool(state.get('price_stale', False))
        sync_badge = ""
        if deposit_stale or price_stale:
            sync_badge = " ⚠"

        if new_status != self.engine_status:
            # 엔진이 OFFLINE → 연결 상태로 처음 전환되면 크래시 카운터 리셋
            if self.engine_status == "OFFLINE" and new_status not in ("OFFLINE",):
                self._engine_crash_count = 0
                logger.info(f"✅ [UI] 엔진 연결 확인 → 크래시 카운터 초기화 (status: {new_status})")

            self.engine_status = new_status
            # phase는 엔진이 내려준 값을 우선 사용

            # [수정] 모의/실계좌 시각적 구분 추가
            if new_status == "READY_MOCK":
                self.is_mock = True
                self.pw_input.setText(self._get_account_password())
                self.status_label.setText(f"🔵 모의투자 연결 | {phase}{sync_badge}")
                self.status_label.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 14px;") # 밝은 파랑
                # [Fix D/E] 크래시 후 재시작된 엔진이 READY로 돌아오면 자동 가동 타이머 재시작
                # _check_engine_health()에서 이미 is_trading_started=False로 리셋했으므로
                # 조건이 정상적으로 통과됨
                if not self.auto_start_timer.isActive() and not self.is_trading_started:
                    self.auto_start_timer.start(1000)
            
            elif new_status == "READY_REAL":
                self.is_mock = False
                self.pw_input.setText(self._get_account_password())
                self.status_label.setText(f"🚨 실계좌 연결됨 | {phase}{sync_badge}")
                self.status_label.setStyleSheet("color: #ef4444; font-weight: bold; font-size: 14px;") # 경고의 빨강
                if not self.auto_start_timer.isActive() and not self.is_trading_started:
                    self.auto_start_timer.start(1000)

            elif new_status == "LOGGING_IN":
                self.status_label.setText("⏳ 키움증권 로그인 중...")
                self.status_label.setStyleSheet(f"color: {COLORS['warning_orange']};")
                
            elif new_status == "TRADING_MOCK":
                self.status_label.setText(f"🔵 가상매매 가동 중 | {phase}{sync_badge}")
                self.status_label.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 14px;")
                self._tray_status_action.setText("상태: 🔵 가상매매 가동 중")
                
            elif new_status == "TRADING_REAL":
                self.status_label.setText(f"🚨 실전매매 가동 중 | {phase}{sync_badge}")
                self.status_label.setStyleSheet("color: #ef4444; font-weight: bold; font-size: 14px;")
                self._tray_status_action.setText("상태: 🚨 실전매매 가동 중")

        dep_total = state.get('deposit_total', state.get('deposit', 0))
        orderable = state.get('orderable', 0)
        prof = state.get('profit', 0)
        self.deposit_label.setText(f"💰 예수금(D+2): {dep_total:,}원")
        self.orderable_label.setText(f"💳 주문가능: {orderable:,}원")

        # [v8.0] 지수 라벨 갱신
        try:
            self._update_index_labels(state)
        except Exception:
            pass

        # 동기화 경고 표시: 조회가 오래되었거나(예수금), 실시간 시세가 끊긴 종목이 있으면 색상으로 경고
        if deposit_stale:
            self.deposit_label.setStyleSheet(f"color: {COLORS['warning_orange']}; font-weight: bold;")
            self.orderable_label.setStyleSheet(f"color: {COLORS['warning_orange']}; font-weight: bold;")
        else:
            self.deposit_label.setStyleSheet("")
            self.orderable_label.setStyleSheet("")
        self.pnl_label.setText(f"📊 실현손익: {prof:+,}원")
        self.pnl_label.setStyleSheet(f"color: {profit_color(prof)}; font-weight: bold; font-size: 15px;")

        accounts = state.get("accounts", [])
        if accounts:
            self._available_accounts = accounts  # 계좌변경 다이얼로그용 전체 목록 저장
            self.btn_change_account.setEnabled(not self.is_trading_started)

            # [Fix] 계좌 자동 설정:
            # "연결 대기" 조건으로만 판단하면 재연결 후 account_label이 이전 계좌번호로
            # 남아 있어 REQ_DEPOSIT이 전달되지 않아 예수금 0 / 엉뚱한 계좌 조회 버그 발생.
            # _reconnect_engine()에서 account_label을 "계좌 연결 대기 중..."으로 리셋하므로
            # 재연결 시에도 이 블록이 올바르게 실행됩니다.
            if "연결 대기" in self.account_label.text() or "조회 중" in self.account_label.text():
                target = self._get_target_account()
                if target and target in accounts:
                    # secrets.json에 설정된 계좌가 유효하면 그대로 사용
                    self._apply_account(target)
                else:
                    # 미설정이거나 목록에 없으면 첫 번째 계좌 자동 선택
                    if target and target not in accounts:
                        self._send_log("⚠️ secrets.json의 target_account가 로그인 계좌 목록에 없습니다. 첫 번째 계좌로 자동 설정합니다.")
                    self._apply_account(accounts[0])


        conditions = state.get("conditions", [])
        if conditions and conditions != self._last_loaded_conditions:
            self._last_loaded_conditions = conditions
            if self.condition_list.count() == 0:
                for c in conditions:
                    item = QListWidgetItem(c['name'])
                    item.setData(Qt.UserRole, c['idx'])
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.Checked if c['name'] in self.default_conditions else Qt.Unchecked)
                    self.condition_list.addItem(item)

                loaded_names = [c['name'] for c in conditions]
                self._send_log(f"🎯 조건식 업데이트 완료. 현재 감시중: {loaded_names}")

        self._update_portfolio_table(state.get("portfolio", {}))
        self._update_condition_table(state.get("condition_log", []))
        try:
            bl = state.get("blacklist", {})
            if isinstance(bl, dict):
                self._update_bl_table(bl)
            lk = state.get("stock_lookup", {})
            if lk and lk.get("name") and self.bl_code_input.text().strip() == lk.get("code"):
                self.bl_lookup_label.setText(f"→ {lk['name']}")
            elif lk and lk.get("code") and not lk.get("name") and self.bl_code_input.text().strip() == lk.get("code"):
                self.bl_lookup_label.setText("→ (없음)")
        except Exception:
            pass


    def _tick_market_status(self):
        """시간 기반으로 '장 상태' 텍스트/표시를 주기적으로 갱신합니다."""
        phase_text = self.calendar.status_text()
        # 장 시작 알림은 엔진에서 1회만 전송하도록 통일 (UI는 표시만 담당)

        # 엔진 상태별 기본 문구 유지 + 장 상태만 업데이트
        s = self.engine_status
        if s == "READY_MOCK":
            self.status_label.setText(f"🔵 모의투자 연결 | {phase_text}")
        elif s == "READY_REAL":
            self.status_label.setText(f"🚨 실계좌 연결됨 | {phase_text}")
        elif s == "TRADING_MOCK":
            self.status_label.setText(f"🔵 가상매매 가동 중 | {phase_text}")
        elif s == "TRADING_REAL":
            self.status_label.setText(f"🚨 실전매매 가동 중 | {phase_text}")
        elif s == "LOGGING_IN":
            self.status_label.setText("⏳ 키움증권 로그인 중...")
        elif s == "OFFLINE":
            self.status_label.setText(f"⚪ 엔진 오프라인 | {phase_text}")

    def _update_condition_table(self, cond_log: list):
        """조건식 편입 모니터 테이블 업데이트."""
        if not cond_log:
            return

        # 기존 로컬 로그와 비교해서 새 항목만 추가 (깜빡임 방지)
        prev_count = getattr(self, '_cond_log_count', 0)
        if len(cond_log) == prev_count:
            return
        self._cond_log_count = len(cond_log)

        # 최신 항목이 위에 오도록 역순 표시
        display = list(reversed(cond_log))
        self.cond_table.setRowCount(len(display))

        buy_count = 0
        skip_count = 0

        for row, entry in enumerate(display):
            result = entry.get('result', '')
            if '매수' in result:
                buy_count += 1
                result_color = COLORS.get('profit_green', '#34d399')
            elif '대기' in result:
                result_color = COLORS.get('warning_orange', '#ff9800')
            else:
                skip_count += 1
                result_color = COLORS.get('loss_red', '#f87171')

            items = [
                entry.get('time', ''),
                entry.get('name', ''),
                entry.get('code', ''),
                entry.get('cond_name', ''),
                result,
                entry.get('reason', ''),
            ]
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter)
                if col == 4:  # 결과 컬럼 색상
                    item.setForeground(QBrush(QColor(result_color)))
                    item.setFont(QFont("Malgun Gothic", 10, QFont.Bold))
                self.cond_table.setItem(row, col, item)

        total = len(cond_log)
        self.cond_count_label.setText(f"편입 {total}건 | 매수 {buy_count}건 | 스킵 {skip_count}건")

    def _on_table_context_menu(self, pos):
        """매매 테이블 우클릭 컨텍스트 메뉴."""
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        code_item = self.table.item(row, 0)
        name_item = self.table.item(row, 1)
        if not code_item:
            return
        code = code_item.text().strip()
        name = name_item.text().strip() if name_item else code

        # 현재 is_manual 상태 파악 (상태 컬럼 텍스트로 판단)
        state = self._last_state.get('portfolio', {}).get(code, {})
        is_manual = state.get('is_manual', True)

        from PyQt5.QtWidgets import QMenu, QAction
        menu = QMenu(self)
        if is_manual:
            action = QAction(f"🤖 봇 관리로 전환 ({name})", self)
            action.triggered.connect(lambda: self._toggle_manual(code, name, to_manual=False))
        else:
            action = QAction(f"👤 수동 관리로 전환 ({name})", self)
            action.triggered.connect(lambda: self._toggle_manual(code, name, to_manual=True))
        menu.addAction(action)
        menu.exec_(self.table.viewport().mapToGlobal(pos))

    def _toggle_manual(self, code: str, name: str, to_manual: bool):
        """봇 관리 ↔ 수동 관리 전환."""
        label = "수동 관리" if to_manual else "봇 관리"
        self.ipc_server.send_command("TOGGLE_MANUAL", code)
        self._send_log(f"{'👤' if to_manual else '🤖'} {name}({code}) → {label}로 전환")

    def _clear_condition_log(self):
        """조건식 편입 로그 UI 초기화."""
        self.cond_table.setRowCount(0)
        self._cond_log_count = 0
        self.cond_count_label.setText("편입 0건 | 매수 0건 | 스킵 0건")

    # ── [v8.0] 지수 표시 ───────────────────────────────
    def _update_index_labels(self, state: dict):
        """지수 라벨 텍스트 및 색상 갱신."""
        def _fmt(name, price, rate):
            if price == 0:
                return f"{name}  --"
            arrow = "▲" if rate >= 0 else "▼"
            return f"{name}  {price:,.2f}  {arrow}{abs(rate):.2f}%"

        def _color(rate):
            if rate > 0:
                return COLORS['profit_red']     # 상승 → 빨강(한국식)
            elif rate < 0:
                return COLORS['loss_blue']      # 하락 → 파랑
            return COLORS['text_secondary']

        kp = state.get('kospi_price', 0)
        kr = state.get('kospi_rate', 0.0)
        kd_p = state.get('kosdaq_price', 0)
        kd_r = state.get('kosdaq_rate', 0.0)

        # [Fix v8.2] 지수 필터 상태 표시 — 임계값 이하일 때 경고
        idx_filter_on = self.config_mgr.get("index_filter_enabled", False)
        threshold = self.config_mgr.get("index_filter_threshold", -2.0)

        kospi_blocked = idx_filter_on and kp > 0 and kr < threshold
        kosdaq_blocked = idx_filter_on and kd_p > 0 and kd_r < threshold

        kospi_txt = _fmt("KOSPI", kp, kr)
        kosdaq_txt = _fmt("KOSDAQ", kd_p, kd_r)
        if kospi_blocked:
            kospi_txt += " ⛔"
        if kosdaq_blocked:
            kosdaq_txt += " ⛔"

        self.kospi_label.setText(kospi_txt)
        self.kospi_label.setStyleSheet(
            f"color: {_color(kr)}; padding: 2px 6px; "
            "font-family: 'Consolas', monospace; font-size: 12px; font-weight: bold;"
        )
        self.kosdaq_label.setText(kosdaq_txt)
        self.kosdaq_label.setStyleSheet(
            f"color: {_color(kd_r)}; padding: 2px 6px; "
            "font-family: 'Consolas', monospace; font-size: 12px; font-weight: bold;"
        )

        # 차트 창이 열려 있으면 데이터 갱신
        if self._index_chart_win and self._index_chart_win.isVisible():
            self._index_chart_win.update_data(
                state.get('kospi_history', []),
                state.get('kosdaq_history', []),
                kp, kr, kd_p, kd_r,
            )

    def _toggle_index_chart(self):
        """지수 차트 창 열기/닫기."""
        if self._index_chart_win and self._index_chart_win.isVisible():
            self._index_chart_win.hide()
            return
        if self._index_chart_win is None:
            self._index_chart_win = IndexChartWindow(self)
        # 마지막 수신 데이터로 초기 표시
        s = self._last_state
        self._index_chart_win.update_data(
            s.get('kospi_history', []),
            s.get('kosdaq_history', []),
            s.get('kospi_price', 0), s.get('kospi_rate', 0.0),
            s.get('kosdaq_price', 0), s.get('kosdaq_rate', 0.0),
        )
        self._index_chart_win.show()
        self._index_chart_win.raise_()

    # ── [v7.5] 블랙리스트 관리 ──
    def _on_blacklist_toggle(self, state):
        cfg = self.config_mgr.config
        bl_enabled = (state == Qt.Checked)
        cfg["blacklist_enabled"] = bl_enabled
        self.config_mgr.save(cfg)
        try:
            self.ipc_server.send_command("APPLY_SETTINGS", json.dumps(cfg, ensure_ascii=False))
        except Exception:
            pass

        # [Fix v8.2] 토글 변경 시 상태 라벨 즉시 갱신
        bl_count = self.bl_table.rowCount()
        if bl_enabled:
            self.bl_count_label.setText(f"🔒 블랙리스트 활성화 | 합: {bl_count}종목")
            self.bl_count_label.setStyleSheet(f"font-weight: bold; color: {COLORS['accent_green']};")
            self._send_log("🔒 블랙리스트 활성화 — 리스트의 종목은 매수에서 제외됩니다")
        else:
            self.bl_count_label.setText(f"🔓 블랙리스트 비활성 | 합: {bl_count}종목 (필터링 안 됨)")
            self.bl_count_label.setStyleSheet(f"font-weight: bold; color: {COLORS['warning_orange']};")
            self._send_log("🔓 블랙리스트 비활성화 — 리스트의 종목도 매수될 수 있습니다")

    def _add_blacklist(self):
        code = self.bl_code_input.text().strip()
        if len(code) == 6 and code.isdigit():
            self.ipc_server.send_command("ADD_BLACKLIST", code)
            self.bl_code_input.clear()

    def _remove_blacklist(self):
        for item in self.bl_table.selectedItems():
            if item.column() == 0:
                self.ipc_server.send_command("REMOVE_BLACKLIST", item.text())

    def _clear_blacklist(self):
        if self.bl_table.rowCount() > 0:
            self.ipc_server.send_command("CLEAR_BLACKLIST")

    def _on_bl_code_changed(self, text):
        if len(text.strip()) == 6 and text.strip().isdigit():
            self.ipc_server.send_command("LOOKUP_STOCK", text.strip())
        else:
            self.bl_lookup_label.setText("")

    def _update_bl_table(self, bl_dict):
        self.bl_table.setRowCount(len(bl_dict))

        # [Fix v8.2] 블랙리스트 활성/비활성 상태를 명확히 표시
        bl_enabled = self.bl_toggle_cb.isChecked()
        if bl_enabled:
            self.bl_count_label.setText(f"🔒 블랙리스트 활성화 | 합: {len(bl_dict)}종목")
            self.bl_count_label.setStyleSheet(f"font-weight: bold; color: {COLORS['accent_green']};")
        else:
            self.bl_count_label.setText(f"🔓 블랙리스트 비활성 | 합: {len(bl_dict)}종목 (필터링 안 됨)")
            self.bl_count_label.setStyleSheet(f"font-weight: bold; color: {COLORS['warning_orange']};")

        for row, (code, name) in enumerate(sorted(bl_dict.items())):
            for col, txt in enumerate([code, name or code, "당일 매수"]):
                self.bl_table.setItem(row, col, QTableWidgetItem(txt))

    def _update_portfolio_table(self, port):
        self.table.setRowCount(len(port))
        self.table.setAlternatingRowColors(True)

        for row, (code, data) in enumerate(list(port.items())):
            buy_p = data['buy_price']
            curr_p = data['current_price']
            qty = data['qty']
            is_manual = data.get('is_manual', False)
            pnl = calc_sell_cost(buy_p, curr_p, qty, self.is_mock)
            invested = buy_p * qty
            # [Fix v8.2] 수익률: 수수료/세금 포함 순수익률 (엔진 판정 기준과 통일)
            yield_rate = (pnl / invested * 100) if invested > 0 else 0
            status = "👀 기존보유" if is_manual else ("⏳ 주문중" if data.get('sell_ordered') else "🔍 감시중")

            # [v7.5] 분할매수/매도 진행 상태
            sb = data.get('split_buy')
            if sb and sb.get('rounds'):
                done = sum(1 for r in sb['rounds'] if r.get('done'))
                total = len(sb['rounds'])
                if done < total:
                    status = f"📦 분할매수 {done}/{total}"
            ss = data.get('split_sell')
            if ss:
                t1 = ss.get('t1_done', False)
                t2 = ss.get('t2_done', False)
                done = int(t1) + int(t2)
                if done == 1:
                    status = "📤 분할매도 1/2"
                elif done == 2:
                    status = "📤 분할매도 2/2"

            items = [
                code,
                data['name'],
                data.get('cond_name', '-'),
                f"{buy_p:,}",
                f"{curr_p:,}",
                f"{yield_rate:+.2f}%",
                f"{pnl:+,}",
                str(qty),
                status,
            ]

            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter)

                if col == 0:  # 종목코드: 모노스페이스
                    item.setForeground(QBrush(QColor(COLORS['text_secondary'])))
                    item.setFont(QFont("Consolas", 11))

                if col in (5, 6):
                    color_val = yield_rate if col == 5 else pnl
                    item.setForeground(QBrush(QColor(profit_color(color_val))))
                    if abs(yield_rate) >= 2.0:
                        item.setFont(QFont("Malgun Gothic", 11, QFont.Bold))

                self.table.setItem(row, col, item)

            # [Fix v8.1] 매도 버튼 — 컨테이너 없이 직접 셀에 배치
            btn = QPushButton("매도")
            btn.setObjectName("btn_manual_sell")
            btn.setMaximumHeight(26)
            btn.setStyleSheet(
                "QPushButton { background-color: rgba(255,107,107,0.15); "
                "color: #ff6b6b; border: 1px solid rgba(255,107,107,0.4); "
                "border-radius: 3px; padding: 1px 4px; font-size: 11px; font-weight: 600; "
                "margin: 2px; }"
                "QPushButton:hover { background-color: rgba(255,107,107,0.3); }"
            )
            btn.clicked.connect(lambda _, c=code: self.ipc_server.send_command("MANUAL_SELL", c))
            self.table.setCellWidget(row, 9, btn)

    def _setup_ui(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setSpacing(6)
        main_layout.setContentsMargins(8, 6, 8, 6)

        status_bar = QHBoxLayout()

        # [개선] 단일 계좌 표시 — 콤보박스 제거, Label + 변경 버튼으로 교체
        self.account_label = QLabel("계좌 연결 대기 중...")
        self.account_label.setStyleSheet(
            f"font-weight: bold; color: {COLORS['text_primary']}; "
            "padding: 2px 8px; min-width: 130px;"
        )
        self.btn_change_account = QPushButton("🔄 계좌변경")
        self.btn_change_account.setMinimumWidth(100)
        self.btn_change_account.setEnabled(False)  # 엔진 연결 전까지 비활성
        self.btn_change_account.clicked.connect(self._change_account)

        self.pw_input = QLineEdit()
        self.pw_input.setEchoMode(QLineEdit.Password)
        self.pw_input.setPlaceholderText("PW")
        self.pw_input.setFixedWidth(70)
        self.pw_input.setText(self._get_account_password())

        self.status_label = QLabel("엔진 준비 중...")
        self.deposit_label = QLabel("💰 예수금(D+2): 0원")
        self.deposit_label.setStyleSheet(f"color: {COLORS['text_secondary']}; padding: 4px 8px;")
        self.orderable_label = QLabel("💳 주문가능: 0원")
        self.orderable_label.setStyleSheet(f"color: {COLORS['text_secondary']}; padding: 4px 8px;")
        self.pnl_label = QLabel("📊 실현손익: 0원")
        self.pnl_label.setStyleSheet(f"padding: 4px 8px; font-weight: bold; font-size: 15px;")

        # [v8.0] 지수 표시 라벨 + 차트 버튼
        self.kospi_label = QLabel("KOSPI  --")
        self.kospi_label.setStyleSheet(
            f"color: {COLORS['text_secondary']}; padding: 2px 6px; "
            "font-family: 'Consolas', monospace; font-size: 12px;"
        )
        self.kosdaq_label = QLabel("KOSDAQ  --")
        self.kosdaq_label.setStyleSheet(
            f"color: {COLORS['text_secondary']}; padding: 2px 6px; "
            "font-family: 'Consolas', monospace; font-size: 12px;"
        )
        self.btn_index_chart = QPushButton("📈")
        self.btn_index_chart.setFixedSize(28, 28)
        self.btn_index_chart.setToolTip("지수 차트 열기")
        self.btn_index_chart.setStyleSheet(
            f"QPushButton {{ background: {COLORS['bg_card']}; border: 1px solid {COLORS['border2']}; "
            f"border-radius: 5px; color: {COLORS['accent_blue']}; font-size: 14px; }}"
            f"QPushButton:hover {{ background: {COLORS['hover']}; }}"
        )
        self._index_chart_win = None   # 차트 창 참조 보관
        self.btn_index_chart.clicked.connect(self._toggle_index_chart)

        status_bar.addWidget(QLabel("💳"))
        status_bar.addWidget(self.account_label)
        status_bar.addWidget(self.btn_change_account)
        status_bar.addWidget(self.pw_input)

        self.btn_discord_diag = QPushButton("🔔 알림 점검")
        self.btn_discord_diag.setMinimumWidth(110)
        self.btn_discord_diag.clicked.connect(self._diagnose_discord)
        status_bar.addWidget(self.btn_discord_diag)

        status_bar.addWidget(self.status_label, stretch=1)

        # [v8.0] 지수 표시 영역
        sep_idx = QLabel("|"); sep_idx.setStyleSheet(f"color: {COLORS['border']};")
        status_bar.addWidget(sep_idx)
        status_bar.addWidget(self.kospi_label)
        status_bar.addWidget(self.kosdaq_label)
        status_bar.addWidget(self.btn_index_chart)

        sep1 = QLabel("|"); sep1.setStyleSheet(f"color: {COLORS['border']};")
        sep2 = QLabel("|"); sep2.setStyleSheet(f"color: {COLORS['border']};")
        status_bar.addWidget(self.deposit_label)
        status_bar.addWidget(sep1)
        status_bar.addWidget(self.orderable_label)
        status_bar.addWidget(sep2)
        status_bar.addWidget(self.pnl_label)
        main_layout.addLayout(status_bar)

        self.tabs = QTabWidget()

        trade_tab = QWidget()
        trade_layout = QVBoxLayout()

        settings_group = QGroupBox("⚙️ 매매 설정 (변경 시 실시간 핫-리로딩)")
        settings_vbox = QVBoxLayout()
        settings_vbox.setSpacing(8)
        settings_vbox.setContentsMargins(4, 4, 4, 4)

        # ━━━━━━━━ 섹션 1: 매매 전략 ━━━━━━━━
        h1 = QLabel("매매 전략")
        h1.setObjectName("section_header")
        settings_vbox.addWidget(h1)

        s1 = QGridLayout()
        s1.setSpacing(6)
        s1.setColumnStretch(0, 0)   # 라벨
        s1.setColumnStretch(1, 3)   # 조건식 리스트
        s1.setColumnStretch(2, 0)   # 라벨
        s1.setColumnStretch(3, 1)   # 투자 입력
        s1.setColumnStretch(4, 0)   # 라벨
        s1.setColumnStretch(5, 1)   # 값 입력

        # 조건식 (좌측 row 0~2)
        lbl = QLabel("조건식"); lbl.setObjectName("setting_label")
        s1.addWidget(lbl, 0, 0)
        self.condition_list = QListWidget()
        self.condition_list.setMinimumHeight(100)
        self.condition_list.setMaximumHeight(140)
        self.condition_list.itemChanged.connect(self._on_condition_item_changed)
        s1.addWidget(self.condition_list, 0, 1, 3, 1)

        # 투자 (우측 row 0) — 전체 너비 사용
        lbl = QLabel("💰 투자"); lbl.setObjectName("setting_label")
        s1.addWidget(lbl, 0, 2)
        invest_layout = QHBoxLayout()
        self.invest_type_cb = QComboBox()
        self.invest_type_cb.addItems(["비중(%)", "금액(원)"])
        self.invest_type_cb.currentIndexChanged.connect(self._on_invest_type_changed)
        self.invest_type_cb.currentIndexChanged.connect(self._mark_config_dirty)
        self.invest_spin = QSpinBox()
        self.invest_spin.valueChanged.connect(self._mark_config_dirty)
        invest_layout.addWidget(self.invest_type_cb)
        invest_layout.addWidget(self.invest_spin)
        s1.addLayout(invest_layout, 0, 3, 1, 3)  # colspan 3 → 전체 너비

        # Row 1: 익절 | 손절 | T.S — 한 줄에 배치
        lbl = QLabel("🎯 익절"); lbl.setObjectName("setting_label")
        lbl.setStyleSheet(f"color: {COLORS['profit_red']}; font-weight: bold;")
        s1.addWidget(lbl, 1, 2)
        self.profit_spin = QDoubleSpinBox()
        self.profit_spin.setRange(0.1, 30.0)
        self.profit_spin.setSingleStep(0.1)
        self.profit_spin.setSuffix("%")
        self.profit_spin.valueChanged.connect(self._mark_config_dirty)
        self.profit_spin.valueChanged.connect(self._update_split_sell_guide)
        s1.addWidget(self.profit_spin, 1, 3)

        lbl = QLabel("🛑 손절"); lbl.setObjectName("setting_label")
        lbl.setStyleSheet(f"color: {COLORS['loss_blue']}; font-weight: bold;")
        s1.addWidget(lbl, 1, 4)
        self.loss_spin = QDoubleSpinBox()
        self.loss_spin.setRange(-30.0, -0.1)
        self.loss_spin.setSingleStep(0.1)
        self.loss_spin.setSuffix("%")
        self.loss_spin.valueChanged.connect(self._mark_config_dirty)
        s1.addWidget(self.loss_spin, 1, 5)

        # Row 2: T.S — 조건식 옆 공간 활용
        ts_layout = QHBoxLayout()
        self.ts_use_cb = ToggleSwitch("T.S")
        self.ts_use_cb.stateChanged.connect(self._mark_config_dirty)
        self.ts_activation_spin = QDoubleSpinBox()
        self.ts_activation_spin.setRange(0.5, 30.0)
        self.ts_activation_spin.setSingleStep(0.1)
        self.ts_activation_spin.setSuffix("% 활성")
        self.ts_activation_spin.valueChanged.connect(self._mark_config_dirty)
        self.ts_drop_spin = QDoubleSpinBox()
        self.ts_drop_spin.setRange(0.1, 10.0)
        self.ts_drop_spin.setSingleStep(0.1)
        self.ts_drop_spin.setSuffix("% 하락")
        self.ts_drop_spin.valueChanged.connect(self._mark_config_dirty)
        ts_layout.addWidget(self.ts_use_cb)
        ts_layout.addWidget(self.ts_activation_spin)
        ts_layout.addWidget(self.ts_drop_spin)
        s1.addLayout(ts_layout, 2, 2, 1, 4)  # row 2, 조건식 옆

        settings_vbox.addLayout(s1)

        # 구분선 1
        div1 = QFrame(); div1.setObjectName("section_divider"); div1.setFrameShape(QFrame.HLine)
        settings_vbox.addWidget(div1)

        # ━━━━━━━━ 섹션 2: 분할 매매 전략 ━━━━━━━━
        h2 = QLabel("분할 매매 전략")
        h2.setObjectName("section_header_purple")
        settings_vbox.addWidget(h2)

        s2 = QGridLayout()
        s2.setSpacing(6)
        s2.setColumnStretch(0, 0)
        s2.setColumnStretch(1, 0)
        s2.setColumnStretch(2, 0)
        s2.setColumnStretch(3, 0)
        s2.setColumnStretch(4, 0)
        s2.setColumnStretch(5, 0)
        s2.setColumnStretch(6, 1)

        # Row 0: 분할매수
        self.split_buy_cb = ToggleSwitch("분할매수")
        self.split_buy_cb.stateChanged.connect(self._mark_config_dirty)
        s2.addWidget(self.split_buy_cb, 0, 0)
        self.split_buy_rounds_spin = QSpinBox()
        self.split_buy_rounds_spin.setRange(2, 3)
        self.split_buy_rounds_spin.setSuffix("회")
        self.split_buy_rounds_spin.valueChanged.connect(self._mark_config_dirty)
        s2.addWidget(self.split_buy_rounds_spin, 0, 1)
        self.split_buy_ratio1 = QSpinBox()
        self.split_buy_ratio1.setRange(10, 90)
        self.split_buy_ratio1.setSuffix("% 1차")
        self.split_buy_ratio1.valueChanged.connect(self._mark_config_dirty)
        s2.addWidget(self.split_buy_ratio1, 0, 2)
        self.split_buy_ratio2 = QSpinBox()
        self.split_buy_ratio2.setRange(10, 90)
        self.split_buy_ratio2.setSuffix("% 2차")
        self.split_buy_ratio2.valueChanged.connect(self._mark_config_dirty)
        s2.addWidget(self.split_buy_ratio2, 0, 3)
        lbl = QLabel("확인상승:"); lbl.setObjectName("setting_label")
        s2.addWidget(lbl, 0, 4)
        self.split_buy_confirm = QDoubleSpinBox()
        self.split_buy_confirm.setRange(-10.0, 10.0)
        self.split_buy_confirm.setSingleStep(0.1)
        self.split_buy_confirm.setSuffix("% 확인")
        self.split_buy_confirm.setToolTip("양수: 상승확인 후 추매 | 음수: 하락 시 물타기")
        self.split_buy_confirm.valueChanged.connect(self._mark_config_dirty)
        s2.addWidget(self.split_buy_confirm, 0, 5)

        # Row 1: 분할매도 — TS 독립형 (Option C)
        # 1차: 익절% 도달 → ratio1% 매도 / 2차: 익절%+offset% 도달 → 잔여 전량 (TS 없어도 작동)
        self.split_sell_cb = ToggleSwitch("분할매도")
        self.split_sell_cb.setToolTip(
            "TS 독립형 분할매도 (Option C)\n"
            "① 익절% 도달 → 1차 비중(ratio1%) 매도\n"
            "② 익절%+offset% 도달 → 잔여 전량 매도\n"
            "③ TS 발동 시 잔여 전량 우선 처리 (TS 설정 시)"
        )
        self.split_sell_cb.stateChanged.connect(self._mark_config_dirty)
        s2.addWidget(self.split_sell_cb, 1, 0)
        lbl = QLabel("1차비중:"); lbl.setObjectName("setting_label")
        s2.addWidget(lbl, 1, 1)
        self.split_sell_t1_ratio = QSpinBox()
        self.split_sell_t1_ratio.setRange(10, 90)
        self.split_sell_t1_ratio.setValue(50)
        self.split_sell_t1_ratio.setSuffix("%")
        self.split_sell_t1_ratio.setToolTip("익절% 도달 시 1차 매도 비중 (%)")
        self.split_sell_t1_ratio.valueChanged.connect(self._mark_config_dirty)
        s2.addWidget(self.split_sell_t1_ratio, 1, 2)
        lbl_off = QLabel("2차+"); lbl_off.setObjectName("setting_label")
        s2.addWidget(lbl_off, 1, 3)
        self.split_sell_offset = QDoubleSpinBox()
        self.split_sell_offset.setRange(0.1, 10.0)
        self.split_sell_offset.setSingleStep(0.5)
        self.split_sell_offset.setValue(1.5)
        self.split_sell_offset.setSuffix("%")
        self.split_sell_offset.setDecimals(1)
        self.split_sell_offset.setToolTip("2차 트리거 = 익절% + offset%\n잔여 전량 매도 (TS 없어도 작동)")
        self.split_sell_offset.valueChanged.connect(self._mark_config_dirty)
        self.split_sell_offset.valueChanged.connect(self._update_split_sell_guide)
        s2.addWidget(self.split_sell_offset, 1, 4)
        self.split_sell_guide = QLabel("→ 2차 +2.3%")
        self.split_sell_guide.setObjectName("setting_label")
        self.split_sell_guide.setStyleSheet(f"color: {COLORS.get('profit_green', '#4caf50')}; font-size: 11px;")
        s2.addWidget(self.split_sell_guide, 1, 5)

        settings_vbox.addLayout(s2)

        # 구분선 2
        div2 = QFrame(); div2.setObjectName("section_divider"); div2.setFrameShape(QFrame.HLine)
        settings_vbox.addWidget(div2)

        # ━━━━━━━━ 섹션 3: 리스크 관리 / 운영 ━━━━━━━━
        h3 = QLabel("리스크 관리 / 운영")
        h3.setObjectName("section_header_orange")
        settings_vbox.addWidget(h3)

        s3 = QGridLayout()
        s3.setSpacing(6)
        s3.setColumnStretch(0, 0)
        s3.setColumnStretch(1, 1)
        s3.setColumnStretch(2, 0)
        s3.setColumnStretch(3, 1)
        s3.setColumnStretch(4, 0)
        s3.setColumnStretch(5, 1)

        # Row 0: 최대보유 / 손실한도 / 주문유형
        lbl = QLabel("최대보유"); lbl.setObjectName("setting_label")
        s3.addWidget(lbl, 0, 0)
        self.max_hold_spin = QSpinBox()
        self.max_hold_spin.setRange(1, 20)
        self.max_hold_spin.setSuffix(" 종목")
        self.max_hold_spin.valueChanged.connect(self._mark_config_dirty)
        s3.addWidget(self.max_hold_spin, 0, 1)

        lbl = QLabel("손실한도"); lbl.setObjectName("setting_label")
        s3.addWidget(lbl, 0, 2)
        self.max_loss_spin = QSpinBox()
        self.max_loss_spin.setRange(0, 10000000)
        self.max_loss_spin.setSingleStep(50000)
        self.max_loss_spin.setSuffix("원")
        self.max_loss_spin.valueChanged.connect(self._mark_config_dirty)
        s3.addWidget(self.max_loss_spin, 0, 3)

        lbl = QLabel("주문유형"); lbl.setObjectName("setting_label")
        s3.addWidget(lbl, 0, 4)
        self.order_type_cb = QComboBox()
        self.order_type_cb.addItems(["시장가 (03)", "최유리지정가 (06)"])
        self.order_type_cb.currentIndexChanged.connect(self._mark_config_dirty)
        s3.addWidget(self.order_type_cb, 0, 5)

        # Row 1: 타임컷 / 마감 / 최소화
        self.timecut_cb = ToggleSwitch("⏰ 15:15 타임컷")
        self.timecut_cb.setChecked(True)
        self.timecut_cb.stateChanged.connect(self._mark_config_dirty)
        s3.addWidget(self.timecut_cb, 1, 0, 1, 2)

        shutdown_layout = QHBoxLayout()
        shutdown_layout.addWidget(QLabel("🌙 마감:"))
        self.shutdown_cb = QComboBox()
        self.shutdown_cb.addItems(["종료 안 함", "프로그램만 종료 (VPS)", "PC 전원 끄기"])
        self.shutdown_cb.currentIndexChanged.connect(self._mark_config_dirty)
        shutdown_layout.addWidget(self.shutdown_cb)
        s3.addLayout(shutdown_layout, 1, 2, 1, 2)

        self.minimize_to_tray_cb = ToggleSwitch("🗂 최소화 시 트레이로 숨김")
        self.minimize_to_tray_cb.setChecked(self.config_mgr.get("minimize_to_tray", False))
        self.minimize_to_tray_cb.stateChanged.connect(self._mark_config_dirty)
        s3.addWidget(self.minimize_to_tray_cb, 1, 4, 1, 2)

        # Row 2: 수동 종목 봇 관리
        self.manual_manage_cb = ToggleSwitch("🤖 수동 종목도 익절/손절 적용")
        self.manual_manage_cb.setChecked(self.config_mgr.get("manual_manage_all", False))
        self.manual_manage_cb.setToolTip(
            "ON: 수동 매수 종목도 설정된 익절/손절/TS 조건 적용\n"
            "OFF: 수동 매수 종목은 직접 관리 (기본값)"
        )
        self.manual_manage_cb.stateChanged.connect(self._mark_config_dirty)
        s3.addWidget(self.manual_manage_cb, 2, 0, 1, 3)

        # [v8.0] Row 3: 지수 필터
        div_idx = QFrame(); div_idx.setObjectName("section_divider"); div_idx.setFrameShape(QFrame.HLine)
        s3.addWidget(div_idx, 3, 0, 1, 6)

        self.index_filter_cb = ToggleSwitch("🛡️ 지수 필터")
        self.index_filter_cb.setToolTip(
            "ON: KOSPI/KOSDAQ 지수 등락율이 설정 임계값 미만이면 매수 차단\n"
            "OFF: 지수 조건 무관하게 조건식 신호 그대로 처리"
        )
        self.index_filter_cb.stateChanged.connect(self._mark_config_dirty)
        s3.addWidget(self.index_filter_cb, 4, 0)

        lbl_thr = QLabel("임계값"); lbl_thr.setObjectName("setting_label")
        s3.addWidget(lbl_thr, 4, 1)
        self.index_threshold_spin = QDoubleSpinBox()
        self.index_threshold_spin.setRange(-30.0, 0.0)
        self.index_threshold_spin.setSingleStep(0.5)
        self.index_threshold_spin.setSuffix("%")
        self.index_threshold_spin.setValue(-2.0)
        self.index_threshold_spin.setToolTip("이 값 이상일 때만 매수 허용 (예: -2.0% → 지수가 -2% 이상이어야 매수)")
        self.index_threshold_spin.valueChanged.connect(self._mark_config_dirty)
        s3.addWidget(self.index_threshold_spin, 4, 2)

        lbl_tgt = QLabel("대상"); lbl_tgt.setObjectName("setting_label")
        s3.addWidget(lbl_tgt, 4, 3)
        self.index_target_cb = QComboBox()
        self.index_target_cb.addItems(["둘 다(AND)", "둘 중 하나(OR)", "KOSPI만", "KOSDAQ만"])
        self.index_target_cb.setToolTip(
            "둘 다(AND): KOSPI와 KOSDAQ 모두 임계값 이상이어야 매수\n"
            "둘 중 하나(OR): 하나만 임계값 이상이면 매수 허용"
        )
        self.index_target_cb.currentIndexChanged.connect(self._mark_config_dirty)
        s3.addWidget(self.index_target_cb, 4, 4, 1, 2)

        settings_vbox.addLayout(s3)

        # ── 적용 버튼 ──
        apply_bar = QHBoxLayout()
        self.apply_status = QLabel("")
        self.apply_status.setStyleSheet(f"color: {COLORS['warning_orange']}; font-weight: bold;")
        self.btn_apply = QPushButton("✅ 적용하기")
        self.btn_apply.setMinimumWidth(120)
        self.btn_apply.clicked.connect(self._apply_settings)
        apply_bar.addWidget(self.apply_status, stretch=1)
        apply_bar.addWidget(self.btn_apply)
        settings_vbox.addLayout(apply_bar)

        settings_group.setLayout(settings_vbox)
        trade_layout.addWidget(settings_group)

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(
            ["종목코드", "종목명", "조건식", "매수단가", "현재가", "수익률(추정)", "손익금(추정)", "수량", "상태", "조작"]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 78)
        header.setSectionResizeMode(9, QHeaderView.Fixed)
        self.table.setColumnWidth(9, 76)  # [Fix v8.1] 매도 버튼 수납 (76px)
        self.table.verticalHeader().setDefaultSectionSize(34)  # [Fix v8.1] 행 높이 34px
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_table_context_menu)
        trade_layout.addWidget(self.table, stretch=1)

        trade_tab.setLayout(trade_layout)
        self.tabs.addTab(trade_tab, "📈 매매")

        # ── 🔍 조건식 편입 모니터 탭 ──
        cond_tab = QWidget()
        cond_layout = QVBoxLayout()

        cond_header = QHBoxLayout()
        self.cond_count_label = QLabel("편입 0건 | 매수 0건 | 스킵 0건")
        self.cond_count_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        cond_clear_btn = QPushButton("🗑 초기화")
        cond_clear_btn.setMinimumWidth(95)
        cond_clear_btn.clicked.connect(self._clear_condition_log)
        cond_header.addWidget(self.cond_count_label)
        cond_header.addStretch()
        cond_header.addWidget(cond_clear_btn)
        cond_layout.addLayout(cond_header)

        self.cond_table = QTableWidget(0, 6)
        self.cond_table.setHorizontalHeaderLabels(
            ["시간", "종목명", "종목코드", "조건식", "결과", "상세"]
        )
        self.cond_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.cond_table.setAlternatingRowColors(True)
        self.cond_table.verticalHeader().setVisible(False)
        self.cond_table.setSortingEnabled(False)
        cond_layout.addWidget(self.cond_table, stretch=1)

        cond_tab.setLayout(cond_layout)
        self.tabs.addTab(cond_tab, "🔍 조건식")

        # ── [v7.5] 🚫 블랙리스트 관리 탭 ──
        bl_tab = QWidget()
        bl_layout = QVBoxLayout()
        bl_header = QHBoxLayout()
        self.bl_toggle_cb = ToggleSwitch("🔒 블랙리스트 활성화")
        self.bl_toggle_cb.setChecked(self.config_mgr.get("blacklist_enabled", True))
        self.bl_toggle_cb.stateChanged.connect(self._on_blacklist_toggle)
        self.bl_count_label = QLabel("0종목")
        self.bl_count_label.setStyleSheet("font-weight: bold;")
        bl_clear_btn = QPushButton("🗑 초기화")
        bl_clear_btn.setMinimumWidth(95)
        bl_clear_btn.clicked.connect(self._clear_blacklist)
        bl_header.addWidget(self.bl_toggle_cb)
        bl_header.addWidget(self.bl_count_label)
        bl_header.addStretch()
        bl_header.addWidget(bl_clear_btn)
        bl_layout.addLayout(bl_header)
        bl_add = QHBoxLayout()
        self.bl_code_input = QLineEdit()
        self.bl_code_input.setPlaceholderText("종목코드 6자리 (예: 005930)")
        self.bl_code_input.setFixedWidth(200)
        self.bl_code_input.setMaxLength(6)
        self.bl_lookup_label = QLabel("")
        self.bl_code_input.textChanged.connect(self._on_bl_code_changed)
        bl_add_btn = QPushButton("➕ 추가")
        bl_add_btn.setMinimumWidth(80)
        bl_add_btn.clicked.connect(self._add_blacklist)
        bl_rm_btn = QPushButton("➖ 제거")
        bl_rm_btn.setMinimumWidth(80)
        bl_rm_btn.clicked.connect(self._remove_blacklist)
        bl_add.addWidget(QLabel("종목코드:"))
        bl_add.addWidget(self.bl_code_input)
        bl_add.addWidget(self.bl_lookup_label, stretch=1)
        bl_add.addWidget(bl_add_btn)
        bl_add.addWidget(bl_rm_btn)
        bl_layout.addLayout(bl_add)
        self.bl_table = QTableWidget(0, 3)
        self.bl_table.setHorizontalHeaderLabels(["종목코드", "종목명", "사유"])
        self.bl_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.bl_table.setAlternatingRowColors(True)
        self.bl_table.verticalHeader().setVisible(False)
        self.bl_table.setSelectionBehavior(QTableWidget.SelectRows)
        bl_layout.addWidget(self.bl_table, stretch=1)
        bl_tab.setLayout(bl_layout)
        self.tabs.addTab(bl_tab, "🚫 블랙리스트")

        stats_tab = QWidget()
        stats_layout = QVBoxLayout()

        stats_btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("🔄 통계 새로고침")
        refresh_btn.clicked.connect(self._update_statistics_tab)
        stats_btn_layout.addWidget(refresh_btn)
        excel_btn = QPushButton("📥 엑셀 내보내기")
        excel_btn.clicked.connect(self._export_excel)
        stats_btn_layout.addWidget(excel_btn)
        stats_btn_layout.addStretch()
        stats_layout.addLayout(stats_btn_layout)

        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setObjectName("log_window")
        self.stats_text.setFont(QFont("Consolas", 11))
        stats_layout.addWidget(self.stats_text)

        stats_tab.setLayout(stats_layout)
        self.tabs.addTab(stats_tab, "📊 통계")

        log_tab = QWidget()
        log_layout = QVBoxLayout()
        self.log_window = QTextEdit()
        self.log_window.setReadOnly(True)
        self.log_window.setObjectName("log_window")
        log_layout.addWidget(self.log_window)
        log_tab.setLayout(log_layout)
        self.tabs.addTab(log_tab, "📝 로그")

        main_layout.addWidget(self.tabs, stretch=1)

        btn_layout = QHBoxLayout()
        self.btn_start = QPushButton("🚀 전략 가동 시작")
        self.btn_start.setObjectName("btn_start")
        self.btn_start.clicked.connect(self._start_trading)

        self.btn_disconnect = QPushButton("🔌 접속 끊기")
        self.btn_disconnect.setObjectName("btn_disconnect")
        self.btn_disconnect.setToolTip("키움 접속만 해제합니다 (UI는 유지). 재연결 버튼으로 다시 연결할 수 있습니다.")
        self.btn_disconnect.clicked.connect(self._disconnect_engine)

        self.btn_exit = QPushButton("❌ 안전 종료")
        self.btn_exit.setObjectName("btn_exit")
        self.btn_exit.clicked.connect(self._confirm_exit)

        btn_layout.addWidget(self.btn_start, stretch=5)
        btn_layout.addWidget(self.btn_disconnect, stretch=3)
        btn_layout.addWidget(self.btn_exit, stretch=2)
        main_layout.addLayout(btn_layout)

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

    def _save_config(self, *args):
        checked = []
        for i in range(self.condition_list.count()):
            item = self.condition_list.item(i)
            if item.checkState() == Qt.Checked:
                checked.append(item.text())
        if checked:
            self.default_conditions = checked

        order_type_map = {"시장가 (03)": "03", "최유리지정가 (06)": "06"}
        config = {
            "invest_type": self.invest_type_cb.currentText(),
            "invest": self.invest_spin.value(),
            "profit": round(self.profit_spin.value(), 2),
            "loss": round(self.loss_spin.value(), 2),
            "max_hold": self.max_hold_spin.value(),
            "max_loss": self.max_loss_spin.value(),
            "ts_use": self.ts_use_cb.isChecked(),
            "ts_activation": round(self.ts_activation_spin.value(), 2),
            "ts_drop": round(self.ts_drop_spin.value(), 2),
            "timecut": self.timecut_cb.isChecked(),
            "shutdown_opt": self.shutdown_cb.currentText(),
            "minimize_to_tray": self.minimize_to_tray_cb.isChecked(),
            "manual_manage_all": self.manual_manage_cb.isChecked(),
            "default_conditions": self.default_conditions,
            "order_type": order_type_map.get(self.order_type_cb.currentText(), "03"),
            "condition_params": self.config_mgr.get("condition_params", {}),
            "entry_filters": self.config_mgr.get("entry_filters", {}),
            "blacklist_enabled": self.bl_toggle_cb.isChecked(),
            "split_buy_enabled": self.split_buy_cb.isChecked(),
            "split_buy_rounds": self.split_buy_rounds_spin.value(),
            "split_buy_ratios": [self.split_buy_ratio1.value(), 100 - self.split_buy_ratio1.value()] if self.split_buy_rounds_spin.value() == 2 else [self.split_buy_ratio1.value(), self.split_buy_ratio2.value(), max(0, 100 - self.split_buy_ratio1.value() - self.split_buy_ratio2.value())],
            "split_buy_confirm_pct": round(self.split_buy_confirm.value(), 2),
            "split_sell_enabled": self.split_sell_cb.isChecked(),
            "split_sell_ratio1": self.split_sell_t1_ratio.value(),   # 1차 매도 비중(%)
            "split_sell_offset": round(self.split_sell_offset.value(), 1),  # 2차 트리거 = 익절%+offset%
            # [v8.0] 지수 필터
            "index_filter_enabled":   self.index_filter_cb.isChecked(),
            "index_filter_threshold": round(self.index_threshold_spin.value(), 1),
            "index_filter_target":    {
                "둘 다(AND)": "both", "둘 중 하나(OR)": "either",
                "KOSPI만": "kospi", "KOSDAQ만": "kosdaq"
            }.get(self.index_target_cb.currentText(), "both"),
            # 계좌는 secrets.json의 target_account를 단일 진실의 원천으로 사용 (config 저장 불필요)
        }
        self.config_mgr.save(config)

    def _on_condition_item_changed(self, item):
        """조건식 체크 변경 — 가동 중이면 엔진에 즉시 반영, 아니면 설정 변경 표시."""
        if self.is_trading_started:
            # 가동 중: 전체 체크 목록을 다시 수집해서 UPDATE_CONDITIONS 전송
            selected = []
            self.condition_list.blockSignals(True)
            for i in range(self.condition_list.count()):
                it = self.condition_list.item(i)
                if it.checkState() == Qt.Checked:
                    selected.append(f"{it.data(Qt.UserRole)}^{it.text()}")
            self.condition_list.blockSignals(False)
            if not selected:
                # 최소 1개 강제 유지 — 방금 해제한 항목 복원
                self.condition_list.blockSignals(True)
                item.setCheckState(Qt.Checked)
                self.condition_list.blockSignals(False)
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.warning(self, "경고", "최소 1개의 조건식이 활성화되어 있어야 합니다.")
                return
            self.ipc_server.send_command("UPDATE_CONDITIONS", ";".join(selected))
            self._send_log(f"🔄 조건식 변경 적용: {len(selected)}개 감시 중")
        else:
            self._mark_config_dirty(item)

    def _mark_config_dirty(self, *args):
        # 사용자가 값을 바꿨지만 아직 엔진에 반영(적용)하지 않은 상태
        self._config_dirty = True
        try:
            self.apply_status.setText("⚠️ 설정 변경됨 (미적용)")
        except Exception:
            pass

    def _apply_settings(self):
        """UI의 설정을 저장하고(파일), 엔진에 즉시 반영시키며, 변경 내용을 디스코드로 남깁니다."""
        # 1) 현재 UI 값 → config 저장
        prev = copy.deepcopy(self._last_applied_config)
        self._save_config()
        curr = copy.deepcopy(self.config_mgr.config)

        # 2) 변경점(diff) 생성
        label_map = {
            "invest_type": "투자 방식",
            "invest": "투자 값",
            "profit": "익절",
            "loss": "손절",
            "max_hold": "최대 보유",
            "max_loss": "손실한도",
            "ts_use": "트레일링",
            "ts_activation": "TS 활성",
            "ts_drop": "TS 하락폭",
            "timecut": "15:15 타임컷",
            "shutdown_opt": "마감 옵션",
            "order_type": "주문유형",
            "default_conditions": "기본 조건식",
            "minimize_to_tray": "트레이 최소화",
            "blacklist_enabled": "블랙리스트",
            "split_buy_enabled": "분할매수",
            "split_sell_enabled": "분할매도",
            "index_filter_enabled": "지수필터",
            "index_filter_threshold": "지수필터 임계값",
            "index_filter_target": "지수필터 대상",
        }
        changed_lines = []
        for k, label in label_map.items():
            if prev.get(k) != curr.get(k):
                changed_lines.append(f"• {label}: {prev.get(k)} → {curr.get(k)}")

        # 3) 엔진에 적용(IPC)
        try:
            self.ipc_server.send_command("APPLY_SETTINGS", json.dumps(curr, ensure_ascii=False))
            applied_ok = True
        except Exception as e:
            applied_ok = False
            self._send_log(f"❌ 설정 적용(IPC) 실패: {e}")

        # 4) 디스코드 알림
        try:
            ts = time.strftime('%Y-%m-%d %H:%M:%S')
            if changed_lines:
                body = "\n".join(changed_lines)
                msg = f"⚙️ [설정 적용]{' ✅' if applied_ok else ' ❌'}\n{body}\n⏰ {ts}"
            else:
                msg = f"⚙️ [설정 적용]{' ✅' if applied_ok else ' ❌'}\n변경된 값이 없습니다.\n⏰ {ts}"
            self.notifier.discord(msg)
        except Exception:
            pass

        if applied_ok:
            self._last_applied_config = copy.deepcopy(curr)
            self._config_dirty = False
            self.apply_status.setText("✅ 적용 완료")
            # 2초 뒤 상태 문구 정리
            QTimer.singleShot(2000, lambda: self.apply_status.setText(""))
        else:
            self.apply_status.setText("❌ 적용 실패(로그 확인)")


    def _load_config_to_ui(self):
        c = self.config_mgr.config
        self._block_signals(True)
        self.invest_type_cb.setCurrentText(c.get("invest_type", "비중(%)"))
        self._on_invest_type_changed()
        self.invest_spin.setValue(c.get("invest", 50))
        self.profit_spin.setValue(c.get("profit", 2.3))
        self.loss_spin.setValue(c.get("loss", -1.7))
        self.max_hold_spin.setValue(c.get("max_hold", 5))
        self.max_loss_spin.setValue(c.get("max_loss", 50000))
        self.ts_use_cb.setChecked(c.get("ts_use", False))
        self.ts_activation_spin.setValue(c.get("ts_activation", 4.0))
        self.ts_drop_spin.setValue(c.get("ts_drop", 0.75))
        self.timecut_cb.setChecked(c.get("timecut", True))
        shutdown_val = c.get("shutdown_opt", "프로그램만 종료 (VPS)")
        # 구버전 config 호환 처리
        if shutdown_val == "프로그램만 종료 (VPS용)":
            shutdown_val = "프로그램만 종료 (VPS)"
        self.shutdown_cb.setCurrentText(shutdown_val)
        self.minimize_to_tray_cb.setChecked(c.get("minimize_to_tray", False))
        self.manual_manage_cb.setChecked(c.get("manual_manage_all", False))

        order_type = c.get("order_type", "03")
        self.order_type_cb.setCurrentText("시장가 (03)" if order_type == "03" else "최유리지정가 (06)")
        self.bl_toggle_cb.setChecked(c.get("blacklist_enabled", True))
        self.split_buy_cb.setChecked(c.get("split_buy_enabled", False))
        self.split_buy_rounds_spin.setValue(c.get("split_buy_rounds", 2))
        ratios = c.get("split_buy_ratios", [30, 70])
        self.split_buy_ratio1.setValue(ratios[0] if ratios else 30)
        self.split_buy_ratio2.setValue(ratios[1] if len(ratios) > 1 else 70)
        self.split_buy_confirm.setValue(c.get("split_buy_confirm_pct", 1.0))
        self.split_sell_cb.setChecked(c.get("split_sell_enabled", False))
        # 구버전 호환: split_sell_targets / split_sell_ratio → split_sell_ratio1 으로 마이그레이션
        legacy_ratio = 50
        if "split_sell_targets" in c and c["split_sell_targets"]:
            legacy_ratio = c["split_sell_targets"][0].get("ratio", 50)
        self.split_sell_t1_ratio.setValue(
            c.get("split_sell_ratio1", c.get("split_sell_ratio", legacy_ratio))
        )
        self.split_sell_offset.setValue(c.get("split_sell_offset", 1.5))

        # [v8.0] 지수 필터
        self.index_filter_cb.setChecked(c.get("index_filter_enabled", False))
        self.index_threshold_spin.setValue(c.get("index_filter_threshold", -2.0))
        target_map = {"both": "둘 다(AND)", "either": "둘 중 하나(OR)",
                      "kospi": "KOSPI만", "kosdaq": "KOSDAQ만"}
        self.index_target_cb.setCurrentText(
            target_map.get(c.get("index_filter_target", "both"), "둘 다(AND)")
        )

        self._block_signals(False)
        self._update_split_sell_guide()

    def _block_signals(self, block: bool):
        for w in [self.invest_type_cb, self.invest_spin, self.profit_spin,
                  self.loss_spin, self.max_hold_spin, self.max_loss_spin,
                  self.ts_use_cb, self.ts_activation_spin, self.ts_drop_spin,
                  self.timecut_cb, self.shutdown_cb, self.order_type_cb, self.minimize_to_tray_cb,
                  self.split_buy_cb, self.split_buy_rounds_spin, self.split_buy_ratio1,
                  self.split_buy_ratio2, self.split_buy_confirm,
                  self.split_sell_cb, self.split_sell_t1_ratio, self.split_sell_offset,
                  self.index_filter_cb, self.index_threshold_spin, self.index_target_cb]:
            w.blockSignals(block)

    def _update_split_sell_guide(self):
        """분할매도 2차 트리거 = 익절% + offset% 를 실시간으로 표시."""
        try:
            profit = self.profit_spin.value()
            offset = self.split_sell_offset.value()
            self.split_sell_guide.setText(f"→ 2차 +{profit + offset:.1f}%")
        except Exception:
            pass

    def _on_invest_type_changed(self):
        if self.invest_type_cb.currentText() == "비중(%)":
            self.invest_spin.setRange(1, 100)
            self.invest_spin.setSingleStep(1)
            self.invest_spin.setSuffix("%")
            if self.invest_spin.value() > 100:
                self.invest_spin.setValue(20)
        else:
            self.invest_spin.setRange(10000, 1000000000)
            self.invest_spin.setSingleStep(50000)
            self.invest_spin.setSuffix("원")
            if self.invest_spin.value() <= 100:
                self.invest_spin.setValue(1000000)

    def _export_excel(self):
        """매매 기록 엑셀 내보내기."""
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        import os
        default_name = f"K-Trader_매매기록_{datetime.datetime.now().strftime('%Y%m%d')}.xlsx"
        default_path = os.path.join(os.path.expanduser("~"), "Desktop", default_name)
        path, _ = QFileDialog.getSaveFileName(self, "엑셀 파일 저장", default_path, "Excel Files (*.xlsx)")
        if not path:
            return
        ok = self.db.export_to_excel(path, days=365)
        if ok:
            QMessageBox.information(self, "내보내기 완료", f"저장 완료:\n{path}")
        else:
            QMessageBox.warning(self, "내보내기 실패", "엑셀 저장에 실패했습니다.\nopenpyxl이 설치되어 있는지 확인하세요.")

    def _update_statistics_tab(self):
        try:
            stats = self.db.get_statistics(30)
            if not stats:
                self.stats_text.setPlainText("📊 아직 매매 데이터가 없습니다.\n실전 매매 후 통계가 자동 생성됩니다.")
                return

            text = f"""
    ━━━━━━━━ 최근 30일 매매 통계 ━━━━━━━━

    📊 총 매도 횟수: {stats['total_sells']}건
    ✅ 승리: {stats['wins']}건  |  ❌ 패배: {stats['losses']}건  |  ➖ 무승부: {stats['breakeven']}건
    🏆 승률: {stats['win_rate']}%

    💰 총 실현손익: {stats['total_profit']:+,}원
    📈 평균 손익/건: {stats['avg_profit']:+,}원
    🥇 최고 수익 거래: {stats['best_trade']:+,}원
    🥉 최대 손실 거래: {stats['worst_trade']:+,}원

    📊 평균 수익 (승리 시): {stats['avg_win']:+,}원
    📊 평균 손실 (패배 시): {stats['avg_loss']:+,}원
    ⚖️ 손익비 (Profit Factor): {stats['profit_factor']}

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """
            self.stats_text.setPlainText(text)

            cond_perf = self.db.get_condition_performance(30)
            if cond_perf:
                cond_text = "\n━━━━━━━━ 조건식별 성과 ━━━━━━━━\n\n"
                for name, trades, wins, pnl in cond_perf:
                    wr = (wins / trades * 100) if trades > 0 else 0
                    cond_text += f"  [{name}] {trades}건 | 승률 {wr:.0f}% | 손익 {pnl:+,}원\n"
                self._append_stats_text(cond_text)

        except Exception as e:
            logger.error(f"❌ [UI] 통계 탭 갱신 실패: {e}")
            try:
                self.stats_text.setPlainText(f"❌ 통계 표시 중 오류가 발생했습니다.\n{e}")
            except Exception:
                pass
    def _append_stats_text(self, text: str):
        """통계 탭에 텍스트를 추가합니다."""
        current = self.stats_text.toPlainText()
        self.stats_text.setPlainText(current + text)


    def _auto_start_tick(self):
        if self.auto_start_countdown > 0:
            self.btn_start.setText(f"🚀 자동 가동 ({self.auto_start_countdown}초)")
            self.auto_start_countdown -= 1
        else:
            self.auto_start_timer.stop()
            self._start_trading()

    def _start_trading(self):
        if self.auto_start_timer.isActive():
            self.auto_start_timer.stop()
        if self.is_trading_started:
            return

        # 계좌 확인 — target_account가 단일 진실의 원천
        target_acc = self._get_target_account()
        if not target_acc:
            QMessageBox.warning(self, "계좌 미설정", "매매할 계좌가 설정되지 않았습니다.\n계좌변경 버튼으로 계좌를 선택해주세요.")
            return

        selected = []
        for i in range(self.condition_list.count()):
            item = self.condition_list.item(i)
            if item.checkState() == Qt.Checked:
                selected.append(f"{item.data(Qt.UserRole)}^{item.text()}")

        if not selected:
            QMessageBox.warning(self, "경고", "최소 1개의 조건식을 선택해주세요.")
            return

        # 매매 중 계좌변경 차단 (조건식은 가동 중에도 변경 가능)
        self.btn_change_account.setEnabled(False)
        self.is_trading_started = True

        self.ipc_server.send_command("START_TRADING", ";".join(selected))
        self._send_log(f"🚀 엔진에 가동 명령 하달 | {len(selected)}개 조건식 병렬 감시")
        self.btn_start.setText("🟢 엔진 가동 중")
        self.btn_start.setProperty("trading", "true")
        self.btn_start.style().unpolish(self.btn_start)
        self.btn_start.style().polish(self.btn_start)

    def _check_eod(self):
        now = datetime.datetime.now()
        today = now.strftime("%Y-%m-%d")

        # 날짜가 바뀌면 플래그 자동 리셋
        if getattr(self, '_timecut_date', None) != today:
            self._timecut_fired = False
            self._timecut_date = today
        if getattr(self, '_shutdown_date', None) != today:
            self._shutdown_fired = False
            self._shutdown_date = today

        if not self._timecut_fired and self.calendar.is_eod_timecut(now) and self.timecut_cb.isChecked():
            self._timecut_fired = True
            self._send_log("⏰ 15:15 타임컷! 일괄 청산 명령 하달.")
            self.ipc_server.send_command("TIME_CUT")

        if not self._shutdown_fired and self.calendar.is_eod_shutdown(now):
            self._shutdown_fired = True
            self._send_log("🌙 장 마감 시간이 되어 엔진을 안전 종료합니다.")
            # [P3-8] Qt 메인 스레드에서 실행 (스레드 안전성)
            QTimer.singleShot(0, self._execute_eod)

    def _execute_eod(self):
        """장 마감 처리. blocking 작업은 스레드에서, Qt 종료는 메인 스레드에서."""
        self._send_log("🌙 장 마감 정산 돌입. 엔진 안전 종료.")
        # [Fix C] 엔진이 이미 OFFLINE인 경우 SHUTDOWN_ENGINE 명령 생략 (불필요한 IPC 오류 방지)
        if self.engine_status != "OFFLINE":
            self.ipc_server.send_command("SHUTDOWN_ENGINE", "장 마감 자동 종료")
        else:
            logger.info("[UI] EOD: 엔진이 이미 OFFLINE 상태 → SHUTDOWN_ENGINE 명령 생략")

        def _eod_worker():
            if self.engine_proc:
                try:
                    self.engine_proc.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    self.engine_proc.terminate()

            today = datetime.datetime.now().strftime("%Y-%m-%d")
            filepath = os.path.join(REPORTS_DIR, f"{today.replace('-', '')}_Report.csv")
            try:
                rows = self.db.get_today_trades()
                with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    writer.writerow(["체결시간", "매매구분", "조건식", "종목명", "단가", "수량", "손익(원)"])
                    writer.writerows(rows)
                logger.info(f"✅ [EOD] CSV 리포트 저장 완료: {filepath}")
            except Exception as e:
                logger.error(f"❌ [EOD] CSV 리포트 저장 오류: {e}")

            # Qt 종료/PC 끄기는 메인 스레드에서 실행
            QTimer.singleShot(0, self._eod_shutdown_action)

        threading.Thread(target=_eod_worker, daemon=True).start()

    def _eod_shutdown_action(self):
        """장 마감 후 종료 옵션 실행 (메인 스레드에서 호출)."""
        opt = self.shutdown_cb.currentText()
        if "프로그램" in opt:
            # [Fix] app.quit()은 closeEvent 호출을 보장하지 않아 IPC 스레드가 살아남아
            # 프로세스가 종료되지 않고 ui.lock이 남는 버그 수정.
            # 리소스를 명시적으로 정리 후 os._exit(0)으로 확실하게 종료.
            try:
                self.ipc_server.stop()
                self.ipc_server.wait(2000)   # 최대 2초 대기
            except Exception:
                pass
            if self.engine_proc:
                try:
                    self.engine_proc.terminate()
                    self.engine_proc.wait(timeout=3)
                except Exception:
                    pass
                self.engine_proc = None
            try:
                self.tray.hide()
            except Exception:
                pass
            try:
                self.db.close()
            except Exception:
                pass
            # ui.lock 명시적 삭제 (os._exit은 atexit를 건너뛰므로 직접 삭제)
            try:
                lock_path = os.path.join(get_app_dir(), "data", "ui.lock")
                if os.path.exists(lock_path):
                    os.remove(lock_path)
            except Exception:
                pass
            os._exit(0)

        elif "PC" in opt:
            try:
                if sys.platform == "win32":
                    os.system("shutdown /s /t 60")
                else:
                    os.system("shutdown -h +1")
            except Exception:
                pass

            try:
                app = QApplication.instance()
                if app:
                    app.quit()
                    return
            except Exception:
                pass
            os._exit(0)

    def _send_log(self, msg):
        ts = datetime.datetime.now().strftime('%H:%M:%S')
        clean = msg.replace("**", "").replace("`", "")
        logging.info(clean)
        self.log_window.append(f"[{ts}] {clean}")
        self.log_window.verticalScrollBar().setValue(self.log_window.verticalScrollBar().maximum())

    def _disconnect_engine(self):
        """키움 접속만 끊습니다. UI는 유지되고 재연결 버튼으로 다시 연결할 수 있습니다."""
        if self.is_trading_started:
            if QMessageBox.question(
                self, "매매 중 접속 해제",
                "현재 전략이 가동 중입니다.\n접속을 끊으면 보유 포지션은 유지되고 자동 매매는 중단됩니다.\n계속하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No
            ) != QMessageBox.Yes:
                return

        self._send_log("🔌 키움 접속 해제 중... (UI는 유지됩니다)")
        self.is_trading_started = False
        self._disconnecting = True  # health_check에서 크래시로 처리 방지 플래그
        # [Fix Maintenance] crash_count 를 최대치로 올리지 않음.
        # 기존 코드는 자동 재시작을 막기 위해 최대치로 올렸으나,
        # 이후 -101/-106 점검 단절이 오면 엔진이 exit(1)로 죽어도
        # UI가 재시작을 거부하는 문제가 발생했음.

        # 엔진 프로세스를 직접 종료 (IPC가 끊겨도 안전)
        try:
            self.ipc_server.send_command("DISCONNECT", "")
        except Exception:
            pass
        # 엔진이 스스로 종료하지 않을 경우 대비 강제 종료
        if self.engine_proc:
            try:
                self.engine_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.engine_proc.terminate()
                try:
                    self.engine_proc.wait(timeout=3)
                except Exception:
                    pass
            self.engine_proc = None

        self.engine_status = "DISCONNECTED"

        # 버튼 전환: 재연결 모드
        self.btn_disconnect.setText("🔄 재연결")
        self.btn_disconnect.setToolTip("키움에 다시 접속합니다.")
        self.btn_disconnect.clicked.disconnect()
        self.btn_disconnect.clicked.connect(self._reconnect_engine)
        self.btn_start.setEnabled(False)
        self.btn_start.setText("🚀 전략 가동 시작")
        self.btn_start.setProperty("trading", "false")
        self.btn_start.style().unpolish(self.btn_start)
        self.btn_start.style().polish(self.btn_start)
        self.btn_change_account.setEnabled(True)
        self.condition_list.setEnabled(True)
        self.status_label.setText("🔌 접속 해제됨 — 재연결 버튼으로 다시 연결하세요")
        self.status_label.setStyleSheet(f"color: {COLORS['warning_orange']};")

    def _reconnect_engine(self):
        """엔진을 재스폰하여 키움에 다시 접속합니다."""
        self._send_log("🔄 재연결 중... 엔진을 다시 시작합니다.")
        self._disconnecting = False
        self._engine_crash_count = 0
        self.engine_status = "OFFLINE"
        self.auto_start_countdown = 30

        # [Fix] 재연결 시 계좌/예수금 레이블 초기화
        # → _handle_state에서 "연결 대기" 조건이 True가 되어
        #   secrets.json의 올바른 계좌로 _apply_account() → REQ_DEPOSIT이 재전송됨
        # → 미리셋 시: 엔진 self.account="" 유지 → Kiwoom 기본계좌(첫번째)로 조회되거나 예수금 0
        self.account_label.setText("계좌 연결 대기 중...")
        self.account_label.setStyleSheet(
            "color: #aaaaaa; font-size: 13px; padding: 4px 8px;"
        )
        self.deposit_label.setText("💰 예수금(D+2): 조회 중...")
        self._last_loaded_conditions = None  # 조건식 목록도 재로딩 허용

        self._spawn_engine()
        # 버튼 원복
        self.btn_disconnect.setText("🔌 접속 끊기")
        self.btn_disconnect.setToolTip("키움 접속만 해제합니다 (UI는 유지). 재연결 버튼으로 다시 연결할 수 있습니다.")
        self.btn_disconnect.clicked.disconnect()
        self.btn_disconnect.clicked.connect(self._disconnect_engine)
        self.btn_start.setEnabled(True)
        self.status_label.setText("🔄 재연결 중...")
        self.status_label.setStyleSheet(f"color: {COLORS['accent_blue']};")

    def _confirm_exit(self):
        if QMessageBox.question(self, "종료", "시스템을 종료하시겠습니까?\n엔진도 함께 종료됩니다.",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self._send_log("🌙 프로그램을 안전 종료합니다.")
            self.ipc_server.send_command("SHUTDOWN_ENGINE", "사용자 수동 종료")
            if self.engine_proc:
                try:
                    self.engine_proc.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    pass
            self.close()

    def _force_quit(self):
        self._send_log("🌙 프로그램을 강제 종료합니다.")
        self.ipc_server.send_command("SHUTDOWN_ENGINE", "사용자 강제 종료")
        time.sleep(3)
        self.close()

    def closeEvent(self, event):
        self.ipc_server.send_command("SHUTDOWN_ENGINE", "UI 종료")
        self.ipc_server.stop()
        if self.engine_proc:
            try:
                self.engine_proc.terminate()
                self.engine_proc.wait(timeout=5)
            except Exception:
                pass
        self.tray.hide()
        self.db.close()
        event.accept()


def _cleanup_old_logs(logs_dir, max_days=30):
    """30일 이상 된 로그 파일을 자동 삭제합니다."""
    import glob
    cutoff = time.time() - (max_days * 86400)
    for pattern in ["engine_*.log", "ui_*.log"]:
        for f in glob.glob(os.path.join(logs_dir, pattern)):
            try:
                if os.path.getmtime(f) < cutoff:
                    os.remove(f)
            except Exception:
                pass


def run_ui():
    _cleanup_old_logs(LOGS_DIR)
    log_file = os.path.join(LOGS_DIR, f"ui_{datetime.datetime.now().strftime('%Y%m%d')}.log")
    kt_logger = logging.getLogger("ktrader")
    kt_logger.setLevel(logging.INFO)
    if not kt_logger.handlers:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        kt_logger.addHandler(fh)

    # [Fix #6] 마법사 실행 후 QApplication 중복 생성 방지
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    win = TradingUI()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    run_ui()
