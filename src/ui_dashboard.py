"""
K-Trader Master - UI 대시보드 (프론트엔드 프로세스)
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
    QListWidget, QListWidgetItem, QMessageBox, QSystemTrayIcon, QMenu, QAction
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QIcon, QColor, QFont, QBrush

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import Database
from src.config_manager import ConfigManager, SecretManager
from src.market_calendar import MarketCalendar
from src.notifications import Notifier
from src.styles import DARK_THEME_QSS, COLORS, profit_color
from src.utils import calc_sell_cost, get_user_data_dir, resolve_db_path, __version__
from src.ipc import UI_IPCServer

logger = logging.getLogger("ktrader")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
DATA_DIR = os.path.join(BASE_DIR, "data")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")

for d in [CONFIG_DIR, DATA_DIR, LOGS_DIR, REPORTS_DIR]:
    os.makedirs(d, exist_ok=True)


class TradingUI(QMainWindow):
    """K-Trader v7.4 메인 UI 대시보드."""

    def __init__(self):
        super().__init__()

        self.db = Database(resolve_db_path(BASE_DIR))
        self.config_mgr = ConfigManager(CONFIG_DIR)
        self.config_mgr.load()
        self.secrets = SecretManager(CONFIG_DIR).load()
        self.notifier = Notifier(self.secrets)
        self.calendar = MarketCalendar(api_key=self.secrets.get("calendar_api_key"))

        # 설정 적용/변경 추적
        self._last_applied_config = copy.deepcopy(self.config_mgr.config)
        self._config_dirty = False

        # 장 상태(시간 기반) UI 갱신/알림
        self._last_market_phase = self.calendar.get_market_phase()
        self._market_open_notified_date = None

        # [Fix #8/#9] 모의/실 비밀번호 분리 관리 (secrets.json 키 연동)
        self.is_mock = True  # 안전한 기본값: 모의투자 가정
        self.engine_status = "OFFLINE"
        self.is_trading_started = False
        self.engine_proc = None
        self.default_conditions = self.config_mgr.get("default_conditions", ["나의급등주02"])

        self._engine_crash_count = 0
        self._max_engine_restarts = 5
        self._last_loaded_conditions = None

        self.setWindowTitle(f"K-Trader Master v{__version__}")
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
        self.tray.setToolTip(f"K-Trader Master v{__version__}")

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
        main_script = os.path.join(BASE_DIR, "main.py")
        try:
            self.engine_proc = subprocess.Popen(
                [sys.executable, main_script, "engine", str(self.ipc_server.port)],
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
            if exit_code == 0:
                if self.engine_status != "OFFLINE":
                    logger.info("🌙 [UI] 엔진이 정상적으로 종료되었습니다.")
                    self.status_label.setText("✅ 엔진 안전 종료 완료")
                    self.status_label.setStyleSheet(f"color: {COLORS['accent_blue']};")
                    self.engine_status = "OFFLINE"
                    self._last_loaded_conditions = None
                self.engine_proc = None
                return

            logger.warning(f"⚠️ [UI] 엔진 프로세스 사망 감지 (exit={exit_code})")
            if self._engine_crash_count < self._max_engine_restarts:
                self._engine_crash_count += 1
                self._send_log(f"⚠️ 엔진 크래시 감지! 자동 재시작 ({self._engine_crash_count}/{self._max_engine_restarts})")
                self.notifier.notify_error(
                    "엔진 크래시 감지",
                    f"자동 재시작 시도 ({self._engine_crash_count}/{self._max_engine_restarts})"
                )
                self._last_loaded_conditions = None
                self._spawn_engine()
            else:
                self._send_log("❌ 엔진 재시작 한도 초과. 수동 확인이 필요합니다.")
                self.notifier.notify_error("엔진 재시작 한도 초과", "수동 확인이 필요합니다.")
                self.engine_proc = None

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

    def _get_saved_account(self) -> str:
        """마지막으로 사용한 계좌(모의/실)를 config에 저장해두었다가 복원합니다."""
        key = 'last_account_mock' if self.is_mock else 'last_account_real'
        return self.config_mgr.get(key, '') or ''

    def _save_last_account(self, acc: str):
        """현재 선택한 계좌를 모의/실 모드별로 저장합니다."""
        if not acc:
            return
        key = 'last_account_mock' if self.is_mock else 'last_account_real'
        cfg = self.config_mgr.config
        if cfg.get(key) != acc:
            cfg[key] = acc
            self.config_mgr.save(cfg)

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
            self.engine_status = new_status
            # phase는 엔진이 내려준 값을 우선 사용
            
            # [수정] 모의/실계좌 시각적 구분 추가
            if new_status == "READY_MOCK":
                self.is_mock = True
                self.pw_input.setText(self._get_account_password())
                self.status_label.setText(f"🔵 모의투자 연결 | {phase}{sync_badge}")
                self.status_label.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 14px;") # 밝은 파랑
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
        if accounts and self.account_cb.count() == 0:
            # 계좌 목록 채우기
            for a in accounts:
                self.account_cb.addItem(f"{a[:4]}****{a[-2:]}", userData=a)

            # ✅ 개선: 실계좌/모의 각각
            # 1) secrets.json의 target_account가 있으면 그 계좌로 자동 선택
            # 2) 없으면 마지막으로 선택했던 계좌(last_account_*)로 자동 복원
            desired = self._get_target_account() or self._get_saved_account()
            idx = self.account_cb.findData(desired) if desired else -1
            self.account_cb.blockSignals(True)
            if idx >= 0:
                self.account_cb.setCurrentIndex(idx)
                self._send_log(f"💳 자동 계좌 선택: {desired[:4]}****{desired[-2:]}")
            else:
                self.account_cb.setCurrentIndex(0)
                if desired:
                    self._send_log("⚠️ 저장/타겟 계좌가 로그인 계좌 목록에 없습니다. 첫 번째 계좌로 선택합니다.")
            self.account_cb.blockSignals(False)

            if self.account_cb.count() > 0:
                self._on_account_changed()


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

    def _clear_condition_log(self):
        """조건식 편입 로그 UI 초기화."""
        self.cond_table.setRowCount(0)
        self._cond_log_count = 0
        self.cond_count_label.setText("편입 0건 | 매수 0건 | 스킵 0건")

    # ── [v7.5] 블랙리스트 관리 ──
    def _on_blacklist_toggle(self, state):
        cfg = self.config_mgr.config
        cfg["blacklist_enabled"] = (state == Qt.Checked)
        self.config_mgr.save(cfg)
        try:
            self.ipc_server.send_command("APPLY_SETTINGS", json.dumps(cfg, ensure_ascii=False))
        except Exception:
            pass

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
        self.bl_count_label.setText(f"{len(bl_dict)}종목")
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
            if ss and ss.get('targets'):
                done = sum(1 for t in ss['targets'] if t.get('done'))
                total = len(ss['targets'])
                if 0 < done < total:
                    status = f"📤 분할매도 {done}/{total}"

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

            btn = QPushButton("매도")
            btn.setObjectName("btn_manual_sell")
            btn.clicked.connect(lambda _, c=code: self.ipc_server.send_command("MANUAL_SELL", c))
            self.table.setCellWidget(row, 9, btn)

    def _setup_ui(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setSpacing(8)

        status_bar = QHBoxLayout()
        self.account_cb = QComboBox()
        self.account_cb.setFixedWidth(140)
        self.account_cb.currentIndexChanged.connect(self._on_account_changed)

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

        status_bar.addWidget(QLabel("💳"))
        status_bar.addWidget(self.account_cb)
        status_bar.addWidget(self.pw_input)

        self.btn_discord_diag = QPushButton("🔔 알림 점검")
        self.btn_discord_diag.setFixedWidth(110)
        self.btn_discord_diag.clicked.connect(self._diagnose_discord)
        status_bar.addWidget(self.btn_discord_diag)

        status_bar.addWidget(self.status_label, stretch=1)
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
        settings_vbox.setSpacing(4)

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
        self.condition_list.setMaximumHeight(72)
        self.condition_list.itemChanged.connect(self._mark_config_dirty)
        s1.addWidget(self.condition_list, 0, 1, 3, 1)

        # 투자 (우측 row 0)
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
        s1.addLayout(invest_layout, 0, 3)

        # 익절
        lbl = QLabel("🎯 익절"); lbl.setObjectName("setting_label")
        lbl.setStyleSheet(f"color: {COLORS['profit_red']}; font-weight: bold;")
        s1.addWidget(lbl, 0, 4)
        self.profit_spin = QDoubleSpinBox()
        self.profit_spin.setRange(0.1, 30.0)
        self.profit_spin.setSingleStep(0.1)
        self.profit_spin.setSuffix("%")
        self.profit_spin.valueChanged.connect(self._mark_config_dirty)
        s1.addWidget(self.profit_spin, 0, 5)

        # 손절
        lbl = QLabel("🛑 손절"); lbl.setObjectName("setting_label")
        lbl.setStyleSheet(f"color: {COLORS['loss_blue']}; font-weight: bold;")
        s1.addWidget(lbl, 1, 2)
        self.loss_spin = QDoubleSpinBox()
        self.loss_spin.setRange(-30.0, -0.1)
        self.loss_spin.setSingleStep(0.1)
        self.loss_spin.setSuffix("%")
        self.loss_spin.valueChanged.connect(self._mark_config_dirty)
        s1.addWidget(self.loss_spin, 1, 3)

        # T.S
        ts_layout = QHBoxLayout()
        self.ts_use_cb = QCheckBox("T.S")
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
        s1.addLayout(ts_layout, 1, 4, 1, 2)

        settings_vbox.addLayout(s1)

        # 구분선 1
        div1 = QFrame(); div1.setObjectName("section_divider"); div1.setFrameShape(QFrame.HLine)
        settings_vbox.addWidget(div1)

        # ━━━━━━━━ 섹션 2: 리스크 관리 / 운영 ━━━━━━━━
        h2 = QLabel("리스크 관리 / 운영")
        h2.setObjectName("section_header_orange")
        settings_vbox.addWidget(h2)

        s2 = QGridLayout()
        s2.setSpacing(6)
        s2.setColumnStretch(0, 0)
        s2.setColumnStretch(1, 1)
        s2.setColumnStretch(2, 0)
        s2.setColumnStretch(3, 1)
        s2.setColumnStretch(4, 0)
        s2.setColumnStretch(5, 1)

        # Row 0: 최대보유 / 손실한도 / 주문유형
        lbl = QLabel("최대보유"); lbl.setObjectName("setting_label")
        s2.addWidget(lbl, 0, 0)
        self.max_hold_spin = QSpinBox()
        self.max_hold_spin.setRange(1, 20)
        self.max_hold_spin.setSuffix(" 종목")
        self.max_hold_spin.valueChanged.connect(self._mark_config_dirty)
        s2.addWidget(self.max_hold_spin, 0, 1)

        lbl = QLabel("손실한도"); lbl.setObjectName("setting_label")
        s2.addWidget(lbl, 0, 2)
        self.max_loss_spin = QSpinBox()
        self.max_loss_spin.setRange(0, 10000000)
        self.max_loss_spin.setSingleStep(50000)
        self.max_loss_spin.setSuffix("원")
        self.max_loss_spin.valueChanged.connect(self._mark_config_dirty)
        s2.addWidget(self.max_loss_spin, 0, 3)

        lbl = QLabel("주문유형"); lbl.setObjectName("setting_label")
        s2.addWidget(lbl, 0, 4)
        self.order_type_cb = QComboBox()
        self.order_type_cb.addItems(["시장가 (03)", "최유리지정가 (06)"])
        self.order_type_cb.currentIndexChanged.connect(self._mark_config_dirty)
        s2.addWidget(self.order_type_cb, 0, 5)

        # Row 1: 타임컷 / 마감 / 최소화
        self.timecut_cb = QCheckBox("⏰ 15:15 타임컷")
        self.timecut_cb.setChecked(True)
        self.timecut_cb.stateChanged.connect(self._mark_config_dirty)
        s2.addWidget(self.timecut_cb, 1, 0, 1, 2)

        shutdown_layout = QHBoxLayout()
        shutdown_layout.addWidget(QLabel("🌙 마감:"))
        self.shutdown_cb = QComboBox()
        self.shutdown_cb.addItems(["종료 안 함", "프로그램만 종료 (VPS)", "PC 전원 끄기"])
        self.shutdown_cb.currentIndexChanged.connect(self._mark_config_dirty)
        shutdown_layout.addWidget(self.shutdown_cb)
        s2.addLayout(shutdown_layout, 1, 2, 1, 2)

        self.minimize_to_tray_cb = QCheckBox("🗂 최소화 시 트레이로 숨김")
        self.minimize_to_tray_cb.setChecked(self.config_mgr.get("minimize_to_tray", False))
        self.minimize_to_tray_cb.stateChanged.connect(self._mark_config_dirty)
        s2.addWidget(self.minimize_to_tray_cb, 1, 4, 1, 2)

        settings_vbox.addLayout(s2)

        # 구분선 2
        div2 = QFrame(); div2.setObjectName("section_divider"); div2.setFrameShape(QFrame.HLine)
        settings_vbox.addWidget(div2)

        # ━━━━━━━━ 섹션 3: 분할 매매 전략 ━━━━━━━━
        h3 = QLabel("분할 매매 전략")
        h3.setObjectName("section_header_purple")
        settings_vbox.addWidget(h3)

        s3 = QGridLayout()
        s3.setSpacing(6)
        s3.setColumnStretch(0, 0)
        s3.setColumnStretch(1, 0)
        s3.setColumnStretch(2, 0)
        s3.setColumnStretch(3, 0)
        s3.setColumnStretch(4, 0)
        s3.setColumnStretch(5, 0)
        s3.setColumnStretch(6, 1)

        # Row 0: 분할매수
        self.split_buy_cb = QCheckBox("분할매수")
        self.split_buy_cb.stateChanged.connect(self._mark_config_dirty)
        s3.addWidget(self.split_buy_cb, 0, 0)
        self.split_buy_rounds_spin = QSpinBox()
        self.split_buy_rounds_spin.setRange(2, 3)
        self.split_buy_rounds_spin.setSuffix("회")
        self.split_buy_rounds_spin.valueChanged.connect(self._mark_config_dirty)
        s3.addWidget(self.split_buy_rounds_spin, 0, 1)
        self.split_buy_ratio1 = QSpinBox()
        self.split_buy_ratio1.setRange(10, 90)
        self.split_buy_ratio1.setSuffix("% 1차")
        self.split_buy_ratio1.valueChanged.connect(self._mark_config_dirty)
        s3.addWidget(self.split_buy_ratio1, 0, 2)
        self.split_buy_ratio2 = QSpinBox()
        self.split_buy_ratio2.setRange(10, 90)
        self.split_buy_ratio2.setSuffix("% 2차")
        self.split_buy_ratio2.valueChanged.connect(self._mark_config_dirty)
        s3.addWidget(self.split_buy_ratio2, 0, 3)
        lbl = QLabel("확인상승:"); lbl.setObjectName("setting_label")
        s3.addWidget(lbl, 0, 4)
        self.split_buy_confirm = QDoubleSpinBox()
        self.split_buy_confirm.setRange(-10.0, 10.0)
        self.split_buy_confirm.setSingleStep(0.1)
        self.split_buy_confirm.setSuffix("% 확인")
        self.split_buy_confirm.setToolTip("양수: 상승확인 후 추매 | 음수: 하락 시 물타기")
        self.split_buy_confirm.valueChanged.connect(self._mark_config_dirty)
        s3.addWidget(self.split_buy_confirm, 0, 5)

        # Row 1: 분할매도
        self.split_sell_cb = QCheckBox("분할매도")
        self.split_sell_cb.stateChanged.connect(self._mark_config_dirty)
        s3.addWidget(self.split_sell_cb, 1, 0)
        lbl = QLabel("1구간:"); lbl.setObjectName("setting_label")
        s3.addWidget(lbl, 1, 1)
        self.split_sell_t1_pct = QDoubleSpinBox()
        self.split_sell_t1_pct.setRange(0.5, 30.0)
        self.split_sell_t1_pct.setSingleStep(0.1)
        self.split_sell_t1_pct.setSuffix("% @")
        self.split_sell_t1_pct.valueChanged.connect(self._mark_config_dirty)
        s3.addWidget(self.split_sell_t1_pct, 1, 2)
        self.split_sell_t1_ratio = QSpinBox()
        self.split_sell_t1_ratio.setRange(10, 90)
        self.split_sell_t1_ratio.setSuffix("%매도")
        self.split_sell_t1_ratio.valueChanged.connect(self._mark_config_dirty)
        s3.addWidget(self.split_sell_t1_ratio, 1, 3)
        lbl = QLabel("2구간:"); lbl.setObjectName("setting_label")
        s3.addWidget(lbl, 1, 4)
        self.split_sell_t2_pct = QDoubleSpinBox()
        self.split_sell_t2_pct.setRange(0.5, 30.0)
        self.split_sell_t2_pct.setSingleStep(0.1)
        self.split_sell_t2_pct.setSuffix("% @")
        self.split_sell_t2_pct.valueChanged.connect(self._mark_config_dirty)
        s3.addWidget(self.split_sell_t2_pct, 1, 5)
        self.split_sell_t2_ratio = QSpinBox()
        self.split_sell_t2_ratio.setRange(10, 90)
        self.split_sell_t2_ratio.setSuffix("%매도")
        self.split_sell_t2_ratio.valueChanged.connect(self._mark_config_dirty)
        s3.addWidget(self.split_sell_t2_ratio, 1, 6)

        settings_vbox.addLayout(s3)

        # ── 적용 버튼 ──
        apply_bar = QHBoxLayout()
        self.apply_status = QLabel("")
        self.apply_status.setStyleSheet(f"color: {COLORS['warning_orange']}; font-weight: bold;")
        self.btn_apply = QPushButton("✅ 적용하기")
        self.btn_apply.setFixedWidth(120)
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
        self.table.setColumnWidth(9, 58)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
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
        cond_clear_btn.setFixedWidth(80)
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
        self.bl_toggle_cb = QCheckBox("🔒 블랙리스트 활성화")
        self.bl_toggle_cb.setChecked(self.config_mgr.get("blacklist_enabled", True))
        self.bl_toggle_cb.stateChanged.connect(self._on_blacklist_toggle)
        self.bl_count_label = QLabel("0종목")
        self.bl_count_label.setStyleSheet("font-weight: bold;")
        bl_clear_btn = QPushButton("🗑 초기화")
        bl_clear_btn.setFixedWidth(80)
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
        bl_add_btn.setFixedWidth(70)
        bl_add_btn.clicked.connect(self._add_blacklist)
        bl_rm_btn = QPushButton("➖ 제거")
        bl_rm_btn.setFixedWidth(70)
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

        self.btn_exit = QPushButton("❌ 안전 종료")
        self.btn_exit.setObjectName("btn_exit")
        self.btn_exit.clicked.connect(self._confirm_exit)

        btn_layout.addWidget(self.btn_start, stretch=7)
        btn_layout.addWidget(self.btn_exit, stretch=3)
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
            "split_sell_targets": [
                {"pct": round(self.split_sell_t1_pct.value(), 2), "ratio": self.split_sell_t1_ratio.value()},
                {"pct": round(self.split_sell_t2_pct.value(), 2), "ratio": self.split_sell_t2_ratio.value()},
            ],
            # 마지막 선택 계좌(모의/실) — 자동 복원을 위해 유지
            "last_account_mock": self.config_mgr.get("last_account_mock", ""),
            "last_account_real": self.config_mgr.get("last_account_real", ""),

        }
        self.config_mgr.save(config)

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
        self.shutdown_cb.setCurrentText(c.get("shutdown_opt", "프로그램만 종료 (VPS용)"))
        self.minimize_to_tray_cb.setChecked(c.get("minimize_to_tray", False))

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
        tgts = c.get("split_sell_targets", [{"pct": 2.0, "ratio": 50}, {"pct": 4.0, "ratio": 50}])
        if len(tgts) >= 1:
            self.split_sell_t1_pct.setValue(tgts[0].get("pct", 2.0))
            self.split_sell_t1_ratio.setValue(tgts[0].get("ratio", 50))
        if len(tgts) >= 2:
            self.split_sell_t2_pct.setValue(tgts[1].get("pct", 4.0))
            self.split_sell_t2_ratio.setValue(tgts[1].get("ratio", 50))
        self._block_signals(False)

    def _block_signals(self, block: bool):
        for w in [self.invest_type_cb, self.invest_spin, self.profit_spin,
                  self.loss_spin, self.max_hold_spin, self.max_loss_spin,
                  self.ts_use_cb, self.ts_activation_spin, self.ts_drop_spin,
                  self.timecut_cb, self.shutdown_cb, self.order_type_cb, self.minimize_to_tray_cb,
                  self.split_buy_cb, self.split_buy_rounds_spin, self.split_buy_ratio1,
                  self.split_buy_ratio2, self.split_buy_confirm,
                  self.split_sell_cb, self.split_sell_t1_pct, self.split_sell_t1_ratio,
                  self.split_sell_t2_pct, self.split_sell_t2_ratio]:
            w.blockSignals(block)

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

    def _on_account_changed(self):
        if self.account_cb.currentIndex() < 0:
            return
        acc = self.account_cb.currentData()
        self._save_last_account(acc)
        self.ipc_server.send_command("REQ_DEPOSIT", f"{acc}^{self.pw_input.text()}")

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

        # [Fix #10] target_account 보호 검증 — 지정된 계좌만 허용
        target_acc = self._get_target_account()
        if target_acc:
            selected_acc = self.account_cb.currentData() or ""
            if selected_acc and selected_acc != target_acc:
                mode = "모의투자" if self.is_mock else "실계좌"
                QMessageBox.critical(
                    self, "⛔ 계좌 불일치",
                    f"현재 선택된 계좌({selected_acc[:4]}****)가\n"
                    f"{mode} 허용 계좌({target_acc[:4]}****)와 일치하지 않습니다.\n\n"
                    f"secrets.json의 {'mock' if self.is_mock else 'real'}_target_account를 확인하세요."
                )
                return

        selected = []
        for i in range(self.condition_list.count()):
            item = self.condition_list.item(i)
            if item.checkState() == Qt.Checked:
                selected.append(f"{item.data(Qt.UserRole)}^{item.text()}")

        if not selected:
            QMessageBox.warning(self, "경고", "최소 1개의 조건식을 선택해주세요.")
            return

        self.account_cb.setEnabled(False)
        self.condition_list.setEnabled(False)
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
        self.ipc_server.send_command("SHUTDOWN_ENGINE", "장 마감 자동 종료")

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
            try:
                app = QApplication.instance()
                if app:
                    app.quit()
                    return
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


def run_ui():
    log_file = os.path.join(LOGS_DIR, f"ui_{datetime.datetime.now().strftime('%Y%m%d')}.log")
    kt_logger = logging.getLogger("ktrader")
    kt_logger.setLevel(logging.INFO)
    if not kt_logger.handlers:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        kt_logger.addHandler(fh)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = TradingUI()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    run_ui()