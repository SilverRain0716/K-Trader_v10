"""
K-Trader - 매매 엔진 (백엔드 프로세스)
[v7.1 수정사항]
  - Fix #1: 실계좌 TR 조회 시 비밀번호/매체구분 누락 해결
  - Fix #2: 계좌 비밀번호를 인스턴스에 저장하여 후속 TR에서 재사용
  - Fix #3: Notifier에 is_mock 정보 전달 (모의/실계좌 구분 알림)
  - Fix #4: invest_type(비중/금액) 구분 로직 추가
  - Fix #5: _build_account_inputs() 헬퍼로 TR 입력값 중복 제거
"""
import sys
import os
import copy
import json
import time
import datetime
import logging
import traceback
from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.QAxContainer import QAxWidget
from PyQt5.QtCore import QTimer, QObject

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
from src.utils import safe_int, calc_sell_cost, get_user_data_dir, get_app_dir, resolve_db_path, __version__
from src.ipc import Engine_IPCClient

logger = logging.getLogger("ktrader")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# [Item 1] 로그는 쓰기 가능한 앱 데이터 디렉토리에 저장
LOGS_DIR = os.path.join(get_app_dir(), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)


class TRScheduler(QObject):
    """
    키움증권 API 호출 속도 제한 스케줄러.

    [Item 3] TR 큐와 ORDER 큐를 분리하여 조회 지연이 주문을 막는 병목 해소.
      - TR 큐   : CommRqData  — 250ms 간격 (키움 제한: 5회/초)
      - ORDER 큐: SendOrder   — 100ms 간격 (별도 제한)
                                SELL(매도·취소) 우선, BUY(매수·취소) 후순위
    두 타이머는 독립적으로 동작하므로 손절 주문이 TR 조회에 밀리지 않는다.
    """

    def __init__(self, kiwoom):
        super().__init__()
        self.kiwoom = kiwoom

        self.tr_queue    = []   # TR 조회 전용 큐
        self.order_queue = []   # 주문 전용 큐 (우선순위 정렬)

        self._last_tr_call_ts    = 0.0
        self._last_order_call_ts = 0.0

        # TR 타이머: 250ms (키움 CommRqData 제한 준수)
        self.tr_timer = QTimer(self)
        self.tr_timer.timeout.connect(self._process_tr)
        self.tr_timer.start(250)

        # ORDER 타이머: 100ms (SendOrder 는 TR 보다 제한이 완화됨)
        self.order_timer = QTimer(self)
        self.order_timer.timeout.connect(self._process_order)
        self.order_timer.start(100)

    # ── 외부 호출 API (기존 호출부 변경 없음) ─────────────────────
    def request_tr(self, rqname, trcode, next_str, screen_no, inputs):
        self.tr_queue.append({
            'rqname': rqname, 'trcode': trcode,
            'next': next_str, 'screen_no': screen_no, 'inputs': inputs,
        })

    def request_order(self, rqname, screen_no, acc_no, order_type,
                      code, qty, price, hoga_gb, org_order_no):
        """
        order_type: 1=매수, 2=매도, 3=매수취소, 4=매도취소
        매도(2)·매도취소(4) → priority 0 (선처리)
        매수(1)·매수취소(3) → priority 1 (후처리)
        """
        priority = 0 if order_type in (2, 4) else 1
        item = {
            'priority': priority,
            'args': [rqname, screen_no, acc_no, order_type,
                     code, qty, price, hoga_gb, org_order_no],
        }
        # 우선순위 순서로 삽입 (SELL 이 항상 BUY 앞)
        for i, existing in enumerate(self.order_queue):
            if priority < existing['priority']:
                self.order_queue.insert(i, item)
                return
        self.order_queue.append(item)

    # ── 내부 처리 ─────────────────────────────────────────────────
    def _process_tr(self):
        if not self.tr_queue:
            return
        if time.time() - self._last_tr_call_ts < 0.25:
            return
        req = self.tr_queue.pop(0)
        for k, v in req['inputs'].items():
            self.kiwoom.dynamicCall("SetInputValue(QString, QString)", k, v)
        self.kiwoom.dynamicCall(
            "CommRqData(QString, QString, int, QString)",
            req['rqname'], req['trcode'], req['next'], req['screen_no'],
        )
        self._last_tr_call_ts = time.time()

    def _process_order(self):
        if not self.order_queue:
            return
        if time.time() - self._last_order_call_ts < 0.10:
            return
        item = self.order_queue.pop(0)
        self.kiwoom.dynamicCall(
            "SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
            item['args'],
        )
        self._last_order_call_ts = time.time()


class TradingEngine(QMainWindow):
    def __init__(self, ipc_port):
        super().__init__()
        logger.info("🔥 [엔진] 매매 엔진 프로세스 가동 시작 (하이브리드 모드)")

        # [Item 1] config/DB 경로를 쓰기 가능한 앱 데이터 디렉토리로 통일
        _app_cfg = os.path.join(get_app_dir(), "config")
        os.makedirs(_app_cfg, exist_ok=True)
        self.db = Database(resolve_db_path())
        self.config_mgr = ConfigManager(_app_cfg)
        self.config_mgr.load()
        self.secrets = SecretManager(_app_cfg).load()
        self.calendar = MarketCalendar(api_key=self.secrets.get("calendar_api_key"))
        self._last_market_phase = self.calendar.get_market_phase()
        self._market_open_notified_date = None

        # UI 정확성(A단계) 지원용 타임스탬프
        self._last_state_ts = None

        self.kiwoom = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")
        self.tr_scheduler = TRScheduler(self.kiwoom)

        # 상태 변수
        self.current_status = "LOGGING_IN"
        self.is_mock = False  # 모의투자 여부 (로그인 시 자동 감지)
        self._reconnect_count = 0          # 키움 재연결 시도 횟수
        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setSingleShot(True)
        self._reconnect_timer.timeout.connect(self._do_reconnect)
        self._pre_market_reconnect_date = None  # 8:50 강제 재연결 하루 1회 플래그
        self._midnight_reset_date = None       # 자정 P&L 리셋 (24시간 운영 대응)
        
        self.account = ""
        self.account_password = ""  # [Fix #2] 비밀번호 저장용
        self.deposit = 0
        # 추가 예수금 표시(총예수금/주문가능/출금가능)
        self.deposit_total = 0
        self.orderable_amount = 0
        self.withdrawable_amount = 0
        self._deposit_last_ok_ts = time.time()  # [Fix #4] None → TypeError 방지, 초기값은 현재 시각
        self.locked_deposit = 0
        self.today_realized_profit = self.db.get_today_trade_summary().get('realized_profit', 0)
        self.broker_today_realized_profit = None
        self._loss_limit_triggered = False

        self.portfolio = {}
        self.orderbook = {}
        self.blacklist = set()
        self.unexecuted_orders = {}
        self._order_exec_cum = {}  # 주문번호별 누적 체결수량 추적(부분체결 대응)
        self._pending_buy = {}
        self._pending_sell_qty = {}
        self._condition_log = []  # 조건식 편입 기록 (UI 표시용, 최근 200건)
        self._bl_cache = {}       # {code: name} 블랙리스트 UI 표시용 캐시
        self._stock_lookup = {}   # 종목코드 조회 결과

        self.account_list = []
        self.condition_list = []
        self.active_conditions = []
        self.tr_screen_no = 999
        self.real_screen_no = 149
        self.is_trading = False
        self._cond_reregistered_date = None   # 장 시작 시 조건식 재등록 1회 플래그
        self._last_deposit_refresh_ts = 0     # 예수금 주기적 갱신 타이머
        self._shutdown_report_sent_date = None  # [Fix #1] 마감 리포트 중복 발송 방지

        # [Fix #3] Notifier는 로그인 후 is_mock 확정되면 세팅
        self.notifier = Notifier(self.secrets)

        # IPC 클라이언트 (UI와 초고속 통신)
        self.ipc_client = Engine_IPCClient(ipc_port)
        self.ipc_client.command_received.connect(self._process_command)
        self.ipc_client.start()

        self._bot_bought_codes = self._load_bot_state()

        # 이벤트 연결
        self.kiwoom.OnEventConnect.connect(self._on_login)
        self.kiwoom.OnReceiveTrData.connect(self._on_tr_data)
        self.kiwoom.OnReceiveConditionVer.connect(self._on_condition_ver)
        self.kiwoom.OnReceiveRealCondition.connect(self._on_real_condition)
        self.kiwoom.OnReceiveRealData.connect(self._on_real_data)
        self.kiwoom.OnReceiveChejanData.connect(self._on_chejan)

        # 타이머 설정
        self.sync_timer = QTimer(self)
        self.sync_timer.timeout.connect(self._sync_routine)
        self.sync_timer.start(500)

        self.order_timer = QTimer(self)
        self.order_timer.timeout.connect(self._check_unexecuted_orders)
        self.order_timer.start(5000)

        self.recon_timer = QTimer(self)
        self.recon_timer.timeout.connect(self._request_reconciliation)
        self.recon_timer.start(180000)

        self.hourly_timer = QTimer(self)
        self.hourly_timer.timeout.connect(self._send_hourly_report)
        # 다음 정시까지 남은 시간으로 첫 실행 정렬
        now = datetime.datetime.now()
        secs_to_next_hour = 3600 - (now.minute * 60 + now.second)
        QTimer.singleShot(secs_to_next_hour * 1000, self._start_hourly_timer)

        self.kiwoom.dynamicCall("CommConnect()")

    # ── 헬퍼 ──────────────────────────────────────
    def _next_tr_screen(self):
        self.tr_screen_no = 1000 if self.tr_screen_no > 1099 else self.tr_screen_no + 1
        return str(self.tr_screen_no)

    def _next_real_screen(self):
        self.real_screen_no = 150 if self.real_screen_no > 399 else self.real_screen_no + 1
        return f"0{self.real_screen_no}"

    def _build_account_inputs(self, extra: dict = None) -> dict:
        """
        [Fix #5] 계좌번호 + 비밀번호 + 매체구분을 포함하는 기본 TR 입력값 빌더.
        실계좌에서는 비밀번호와 매체구분이 필수이며, 모의투자에서는 있어도 무해합니다.
        """
        inputs = {
            "계좌번호": self.account,
            "비밀번호": self.account_password,
            "비밀번호입력매체구분": "00",
        }
        if extra:
            inputs.update(extra)
        return inputs

    def _load_bot_state(self) -> set:
        path = os.path.join(get_user_data_dir(), "bot_state.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

                # [Fix] 블랙리스트는 당일 데이터만 복원 — 날짜가 바뀌면 초기화
                saved_date = data.get("date", "")
                today = datetime.date.today().isoformat()
                if saved_date == today:
                    saved_bl = data.get("blacklist", [])
                    if saved_bl:
                        self.blacklist = set(saved_bl)
                        saved_names = data.get("blacklist_names", {})
                        self._bl_cache = {c: saved_names.get(c, c) for c in saved_bl}
                        logger.info(f"✅ [상태] 블랙리스트 {len(saved_bl)}종목 복원 (당일)")
                else:
                    logger.info(f"🔄 [상태] 날짜 변경 감지 ({saved_date} → {today}) → 블랙리스트 초기화")
                    self.blacklist = set()
                    self._bl_cache = {}

                return set(data.get("bot_bought_codes", []))
        except Exception:
            return set()

    def _save_bot_state(self):
        path = os.path.join(get_user_data_dir(), "bot_state.json")
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            codes = [c for c, d in list(self.portfolio.items()) if not d.get('is_manual', False)]  # [Fix #4]
            with open(path, "w", encoding="utf-8") as f:
                json.dump({
                    "date": datetime.date.today().isoformat(),
                    "bot_bought_codes": codes,
                    "blacklist": list(self.blacklist),
                    "blacklist_names": dict(getattr(self, '_bl_cache', {})),
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ bot_state 저장 실패: {e}")

    def _calc_unrealized_profit(self) -> int:
        unrealized = 0
        for code, data in list(self.portfolio.items()):  # [Fix #4]
            if data.get('qty', 0) > 0 and data.get('buy_price', 0) > 0:
                unrealized += calc_sell_cost(data['buy_price'], data['current_price'], data['qty'], self.is_mock)
        return unrealized

    def _log_condition_signal(self, code: str, name: str, cond_name: str, result: str, reason: str = ""):
        """조건식 편입 기록을 남깁니다 (UI 실시간 표시용)."""
        entry = {
            'time': time.strftime('%H:%M:%S'),
            'code': code,
            'name': name,
            'cond_name': cond_name,
            'result': result,    # "매수주문" / "스킵"
            'reason': reason,    # 스킵 사유 또는 주문 상세
        }
        self._condition_log.append(entry)
        # 최근 200건만 유지
        if len(self._condition_log) > 200:
            self._condition_log = self._condition_log[-200:]

    def _get_account_mode_text(self) -> str:
        """현재 계좌 모드 텍스트 반환."""
        return "🔵 모의투자" if self.is_mock else "🔴 실계좌"

    # ── 동기화 루틴 ──────────────────────────────────
    def _sync_routine(self):
        if time.time() - self.ipc_client.last_heartbeat > 60:
            logger.critical("💀 [엔진] UI 연결 단절. 자동 자폭합니다.")
            self._save_bot_state()
            sys.exit(0)

        # 장 시작 알림(엔진 기준, 하루 1회) + 조건식 재등록 + 예수금 갱신
        # [Fix #2] 각 단계를 독립 try-except로 분리하여, 한 단계 실패 시에도
        #          나머지 단계(특히 예수금 갱신)가 반드시 실행되도록 수정.
        try:
            phase = self.calendar.get_market_phase()
            today = datetime.date.today().isoformat()
        except Exception as e:
            logger.error(f"❌ [sync] 마켓 페이즈 조회 오류: {e}")
            phase = self._last_market_phase  # 직전 상태를 fallback으로 유지
            today = datetime.date.today().isoformat()

        # PRE_MARKET → REGULAR 전환 감지
        if self._last_market_phase == "PRE_MARKET" and phase == "REGULAR":

            # ① 장 시작 알림 (독립 try)
            try:
                if self._market_open_notified_date != today:
                    self._market_open_notified_date = today
                    self.notifier.discord(f"🟢 [장 시작] 정규장이 시작되었습니다. ({time.strftime('%H:%M:%S')})")
            except Exception as e:
                logger.error(f"❌ [sync] 장 시작 알림 오류: {e}")

            # ② 조건식 재등록 (독립 try — 실패해도 예수금 갱신은 반드시 진행)
            # [Fix C] 장 시작 전에 등록한 실시간 조건검색은 서버 세션 갱신으로 끊길 수 있습니다.
            try:
                if self._cond_reregistered_date != today and self.is_trading and self.active_conditions:
                    self._cond_reregistered_date = today
                    logger.info(f"🔄 [조건식] 장 시작 전환 감지 → 조건식 {len(self.active_conditions)}개 재등록")
                    for cond in self.condition_list:
                        if cond['name'] in self.active_conditions:
                            try:
                                self.kiwoom.dynamicCall("SendConditionStop(QString, QString, int)",
                                                       "0300", cond['name'], int(cond['idx']))
                            except Exception:
                                pass
                            try:
                                self.kiwoom.dynamicCall("SendCondition(QString, QString, int, int)",
                                                       self._next_real_screen(), cond['name'], int(cond['idx']), 1)
                                logger.info(f"  ✅ 재등록: {cond['name']} (idx={cond['idx']})")
                            except Exception as e:
                                logger.error(f"  ❌ 조건식 재등록 실패: {cond['name']} — {e}")
            except Exception as e:
                logger.error(f"❌ [sync] 조건식 재등록 오류: {e}")

            # ③ 장 시작 시 예수금 즉시 갱신 (독립 try — 항상 실행)
            # [Fix D] 장 시작 시 예수금 즉시 갱신
            try:
                if self.account and self.account_password:
                    self.tr_scheduler.request_tr(
                        rqname="예수금조회", trcode="opw00001", next_str=0, screen_no=self._next_tr_screen(),
                        inputs=self._build_account_inputs({"조회구분": "1"})
                    )
                    self._last_deposit_refresh_ts = time.time()
            except Exception as e:
                logger.error(f"❌ [sync] 장 시작 예수금 갱신 오류: {e}")

        # 상태 업데이트는 항상 실행 (try 바깥)
        self._last_market_phase = phase

        # ④ 장중 5분 간격 예수금 자동 갱신 (독립 try)
        # [Fix D] 장중 5분 간격 예수금 자동 갱신
        try:
            if phase == "REGULAR" and self.account and self.account_password:
                if time.time() - self._last_deposit_refresh_ts > 300:
                    self._last_deposit_refresh_ts = time.time()
                    self.tr_scheduler.request_tr(
                        rqname="예수금조회", trcode="opw00001", next_str=0, screen_no=self._next_tr_screen(),
                        inputs=self._build_account_inputs({"조회구분": "1"})
                    )
                    logger.debug("🔄 [예수금] 정기 갱신 요청 (5분 주기)")
        except Exception as e:
            logger.error(f"❌ [sync] 정기 예수금 갱신 오류: {e}")

        # 예수금/주문가능/출금가능 표시값 보정(항상 내부 상태와 일치하도록)
        try:
            base_cash = int(self.orderable_amount) if int(self.orderable_amount) > 0 else int(self.deposit)
            # 주문가능은 (현금 기준 - 락)으로 항상 재계산 (TR 값이 있으면 TR 우선)
            self.orderable_amount = max(0, base_cash - int(self.locked_deposit))
            # 총예수금/출금가능은 TR 값이 없을 때만 deposit을 사용
            self.deposit_total = int(self.deposit_total) if int(self.deposit_total) > 0 else int(self.deposit)
            self.withdrawable_amount = int(self.withdrawable_amount) if int(self.withdrawable_amount) > 0 else int(self.deposit)
        except Exception:
            pass

        # 가격/예수금 동기화 품질(=UI 정확성)용 메타데이터
        now_ts = time.time()
        price_stale_codes = []
        try:
            for c, d in list(self.portfolio.items()):  # [Fix #4] list()로 복사하여 반복 중 dict 변경 방어
                if d.get('qty', 0) > 0:
                    ts = d.get('last_price_ts')
                    if not ts or (now_ts - float(ts)) > 5.0:
                        price_stale_codes.append(c)
        except Exception:
            pass

        # [Fix E] 장중 보유종목 실시간 시세 구독 자동 복구
        # 30초 이상 가격 갱신이 없으면 구독이 끊긴 것으로 판단하고 재등록합니다.
        market_phase = self.calendar.get_market_phase()
        if market_phase == "REGULAR" and self.is_trading:
            for c, d in list(self.portfolio.items()):
                if d.get('qty', 0) > 0 and d.get('status') == 'HOLDING':
                    ts = d.get('last_price_ts')
                    if ts and (now_ts - float(ts)) > 30.0:
                        try:
                            real_scr = d.get('screen_no') or self._next_real_screen()
                            self.kiwoom.dynamicCall("SetRealReg(QString, QString, QString, QString)",
                                                   real_scr, c, "10;13;71", "1")
                            d['screen_no'] = real_scr
                            d['last_price_ts'] = now_ts  # 무한 재시도 방지 (30초 쿨다운)
                            logger.warning(f"🔄 [실시간] {d.get('name', c)}({c}) 시세 30초 미수신 → 구독 재등록")
                        except Exception as e:
                            logger.error(f"❌ [실시간] {c} 자동 복구 실패: {e}")

        state = {
            "ts": now_ts,
            "status": self.current_status,
            "is_mock": self.is_mock,
            "market_phase": market_phase,
            "market_phase_text": self.calendar.status_text(),
            "accounts": self.account_list,
            "conditions": self.condition_list,
            "deposit": self.deposit,
            "deposit_total": self.deposit_total,
            "orderable": self.orderable_amount,
            "withdrawable": self.withdrawable_amount,
            "deposit_stale": (time.time() - self._deposit_last_ok_ts > 120) if self._deposit_last_ok_ts else True,
            "price_stale": True if price_stale_codes else False,
            "price_stale_codes": price_stale_codes,
            "profit": self.today_realized_profit,
            "portfolio": copy.deepcopy(self.portfolio),
            "condition_log": list(self._condition_log),
            "blacklist": dict(getattr(self, "_bl_cache", {})),
            "blacklist_enabled": self.config_mgr.get("blacklist_enabled", True),
            "stock_lookup": getattr(self, "_stock_lookup", {}),
        }
        self.ipc_client.send_state(state)
        self.db.write_engine_state(state)

        # ── 자정 P&L 리셋 (AWS 24시간 운영 대응) ──────────────────────────
        # today_realized_profit은 누적 합산이므로, 날짜가 바뀌면 DB에서 오늘 기준으로 재로드합니다.
        try:
            today = datetime.date.today().isoformat()
            if self._midnight_reset_date != today:
                self._midnight_reset_date = today
                new_profit = self.db.get_today_trade_summary().get('realized_profit', 0)
                if new_profit != self.today_realized_profit:
                    logger.info(f"🌅 [자정 리셋] 일일 실현손익 초기화: {self.today_realized_profit:+,} → {new_profit:+,}")
                    self.today_realized_profit = new_profit
                self._loss_limit_triggered = False     # 손실 한도 플래그도 리셋
                self._shutdown_report_sent_date = None  # 마감 리포트 플래그 리셋
                self._cond_reregistered_date = None     # 조건식 재등록 플래그 리셋
                self._market_open_notified_date = None  # 장 시작 알림 플래그 리셋
        except Exception as e:
            logger.error(f"❌ [자정 리셋] 오류: {e}")

        # ── 8:50 AM 장 시작 전 최종 재연결 안전망 ──────────────────────────
        # 키움 서버 점검(08:00~08:20) 후 재연결이 실패한 상태로 남아 있을 경우를 대비,
        # 8시 50분에 한 번 더 강제 재연결을 시도해 9시 장 시작에 대비합니다.
        try:
            now_dt = datetime.datetime.now()
            today = datetime.date.today().isoformat()
            if (now_dt.hour == 8 and now_dt.minute == 50
                    and self._pre_market_reconnect_date != today):
                self._pre_market_reconnect_date = today  # 하루 1회만 실행
                if self.current_status in ("LOGIN_FAILED", "LOGGING_IN"):
                    logger.info("🔔 [엔진] 08:50 장 시작 전 강제 재연결 시도 (점검 후 안전망)")
                    self.notifier.discord("🔔 [08:50 안전망] 키움 미연결 상태 감지 → 강제 재연결 시도합니다.")
                    self._reconnect_timer.stop()   # 진행 중인 백오프 타이머 취소
                    self._do_reconnect()
                else:
                    logger.info(f"✅ [엔진] 08:50 점검: 이미 정상 연결 상태 ({self.current_status})")
        except Exception as e:
            logger.error(f"❌ [8:50 재연결] 오류: {e}")

        # [Fix #1] 장 마감 자동 리포트 & 종료 — shutdown_opt 무관하게 항상 리포트 먼저 전송
        try:
            today = datetime.date.today().isoformat()
            if self.calendar.is_eod_shutdown() and self._shutdown_report_sent_date != today:
                self._shutdown_report_sent_date = today
                logger.info("📊 [마감] 장 마감 감지 → 마감 리포트 전송")
                self._send_daily_report("장 마감 자동 종료")
                shutdown_opt = self.config_mgr.get("shutdown_opt", "프로그램 종료 안함")
                if shutdown_opt != "프로그램 종료 안함":
                    logger.info(f"🔴 [마감] shutdown_opt='{shutdown_opt}' → 엔진 종료 시작")
                    self._execute_shutdown("장 마감 자동 종료")
        except Exception as e:
            logger.error(f"❌ [마감] EOD 감지 오류: {e}")

        now = time.time()
        stale_pending = [code for code, info in self._pending_buy.items() if now - info['timestamp'] > 10.0]
        for code in stale_pending:
            info = self._pending_buy[code]
            elapsed = now - info['timestamp']
            stock_name = self.kiwoom.dynamicCall("GetMasterCodeName(QString)", code) or code
            reason = f"체결데이터 {elapsed:.0f}초 미수신"
            logger.warning(f"⏰ [매수] {code} 타임아웃 폐기: {reason} (조건식: {info.get('cond_name', '?')})")
            self._log_condition_signal(code, stock_name, info.get('cond_name', ''), "스킵", f"타임아웃({reason})")
            self.kiwoom.dynamicCall("SetRealRemove(QString, QString)", info.get('screen_no', 'ALL'), code)
            del self._pending_buy[code]

    # ── 알림 및 검증 ──────────────────────────────────
    def _send_daily_report(self, reason: str = "장 마감 자동 리포트"):
        """
        [Fix #1] 마감 리포트 전송 (shutdown_opt 무관하게 항상 실행).
        _shutdown_report_sent_date로 하루 1회 중복 발송 방지.
        """
        summary = self.db.get_today_trade_summary()
        self.notifier.notify_shutdown_report(
            reason=reason, deposit=self.deposit,
            realized_profit=self.today_realized_profit,
            unrealized_profit=self._calc_unrealized_profit(),
            portfolio=self.portfolio,
            buy_count=summary['buy_count'], buy_amount=summary['buy_amount'],
            sell_count=summary['sell_count'], sell_amount=summary['sell_amount'],
            wins=summary['wins'], losses=summary['losses'],
            is_mock=self.is_mock
        )

    def _send_hourly_report(self):
        if not self.is_trading or not self.calendar.is_regular_market():
            return
        self.notifier.notify_hourly_report(
            portfolio=self.portfolio, deposit=self.deposit,
            realized_profit=self.today_realized_profit,
            is_mock=self.is_mock
        )

    def _start_hourly_timer(self):
        """정시 정렬된 후 1시간 간격으로 타이머 시작."""
        self._send_hourly_report()
        self.hourly_timer.start(3600000)

    def _check_loss_limit(self):
        max_loss = self.config_mgr.get("max_loss", 0)
        if max_loss <= 0:
            return False

        if self.today_realized_profit < 0 and abs(self.today_realized_profit) >= max_loss:
            if not self._loss_limit_triggered:
                self._loss_limit_triggered = True
                self.notifier.notify_loss_limit(self.today_realized_profit, max_loss)
            return True
        return False

    def _request_reconciliation(self):
        if not self.is_trading or not self.account:
            return
        # [Fix #1] 실계좌 비밀번호 포함
        self.tr_scheduler.request_tr(
            rqname="정기잔고교차검증", trcode="opw00018", next_str=0, screen_no=self._next_tr_screen(),
            inputs=self._build_account_inputs({"조회구분": "1"})
        )

    # ── IPC 명령 처리 ──────────────────────────────
    def _process_command(self, cmd, args):
        if cmd == "REQ_DEPOSIT":
            self.account, pw = args.split('^')
            self.account_password = pw  # [Fix #2] 비밀번호를 인스턴스에 저장

            # [Fix #1] 실계좌 호환 - 비밀번호 + 매체구분 포함
            self.tr_scheduler.request_tr(
                rqname="예수금조회", trcode="opw00001", next_str=0, screen_no=self._next_tr_screen(),
                inputs=self._build_account_inputs({"조회구분": "2"})
            )
            self._last_deposit_refresh_ts = time.time()

        elif cmd == "APPLY_SETTINGS":
            # UI에서 변경한 설정을 즉시 엔진에 반영합니다.
            try:
                new_cfg = json.loads(args) if args else {}
                if isinstance(new_cfg, dict) and new_cfg:
                    self.config_mgr.save(new_cfg)
                    self.config_mgr.config = new_cfg
                    logger.info("✅ [엔진] 설정 적용 완료(APPLY_SETTINGS)")
            except Exception as e:
                logger.error(f"❌ [엔진] 설정 적용 실패(APPLY_SETTINGS): {e}")

        elif cmd == "START_TRADING":
            self.is_trading = True
            cond_names = []
            for cond in args.split(';'):
                if '^' in cond:
                    idx, name = cond.split('^')
                    self.kiwoom.dynamicCall("SendCondition(QString, QString, int, int)",
                                           self._next_real_screen(), name, int(idx), 1)
                    self.active_conditions.append(name)
                    cond_names.append(name)
            
            # 상태 변경
            self.current_status = "TRADING_MOCK" if self.is_mock else "TRADING_REAL"
            # [Fix #3] is_mock 정보 전달
            self.notifier.notify_trading_start(
                conditions=cond_names, portfolio=self.portfolio,
                deposit=self.deposit, realized_profit=self.today_realized_profit,
                is_mock=self.is_mock
            )

        elif cmd == "MANUAL_SELL":
            if args in self.portfolio and self.portfolio[args]['qty'] > 0:
                self.portfolio[args]['_last_sell_reason'] = "🖐️ 수동 매도"
                self._execute_sell(args, "🖐️ 수동 매도", self.portfolio[args]['qty'])

        elif cmd == "ADD_BLACKLIST":
            code = args.strip()
            if code and len(code) == 6:
                self.blacklist.add(code)
                try:
                    name = self.kiwoom.dynamicCall("GetMasterCodeName(QString)", code) or code
                except Exception:
                    name = code
                self._bl_cache[code] = name
                logger.info(f"🚫 [블랙리스트] 추가: {name}({code})")
                self._save_bot_state()

        elif cmd == "REMOVE_BLACKLIST":
            code = args.strip()
            self.blacklist.discard(code)
            self._bl_cache.pop(code, None)
            logger.info(f"✅ [블랙리스트] 제거: {code}")
            self._save_bot_state()

        elif cmd == "CLEAR_BLACKLIST":
            cnt = len(self.blacklist)
            self.blacklist.clear()
            self._bl_cache.clear()
            logger.info(f"🗑️ [블랙리스트] 전체 초기화 ({cnt}종목)")
            self._save_bot_state()

        elif cmd == "LOOKUP_STOCK":
            code = args.strip()
            try:
                name = self.kiwoom.dynamicCall("GetMasterCodeName(QString)", code) or ""
            except Exception:
                name = ""
            self._stock_lookup = {"code": code, "name": name}

        elif cmd == "TIME_CUT":
            for code, data in list(self.portfolio.items()):
                if data['qty'] > 0 and data['status'] == 'HOLDING' and not data.get('is_manual'):
                    data['_last_sell_reason'] = "⏰ 타임컷 일괄청산"
                    self._execute_sell(code, "⏰ 타임컷 일괄청산", data['qty'])

        elif cmd == "DISCONNECT":
            # 접속 끊기: 매매 중지 + 키움 연결 해제 (UI는 유지, 엔진 프로세스는 종료)
            # UI가 엔진을 재스폰하면 다시 연결됩니다.
            logger.info("🔌 [엔진] 사용자 요청으로 접속 해제 중...")
            self.is_trading = False
            try:
                for cond in self.condition_list:
                    try:
                        self.kiwoom.dynamicCall("SendConditionStop(QString, QString, int)",
                                               "0300", cond['name'], int(cond['idx']))
                    except Exception:
                        pass
                self.kiwoom.dynamicCall("CommTerminate()")
            except Exception as e:
                logger.warning(f"⚠️ [접속 해제] CommTerminate 오류 (무시): {e}")
            self._save_bot_state()
            self.ipc_client.stop()
            self.db.close()
            sys.exit(0)  # 엔진 종료 → UI가 감지 후 재스폰 대기 상태로 전환

        elif cmd == "SHUTDOWN_ENGINE":
            reason = args if args else "사용자 수동 종료"
            self._execute_shutdown(reason)

    def _execute_shutdown(self, reason: str):
        # [Fix #1] _sync_routine에서 이미 리포트를 보냈으면 중복 발송하지 않음
        today = datetime.date.today().isoformat()
        if getattr(self, '_shutdown_report_sent_date', None) != today:
            self._shutdown_report_sent_date = today
            self._send_daily_report(reason)
        self.notifier.drain_and_shutdown(timeout=15)
        self._save_bot_state()
        self.ipc_client.stop()
        self.db.close()
        sys.exit(0)

    # ── 키움 API 슬롯 ──────────────────────────────
    def _on_login(self, err_code):
        if err_code == 0:
            # [중요] 모의투자 vs 실서버 감지
            # GetLoginInfo("GetServerGubun"): "1"=모의, 그 외=실서버
            server_gubun = self.kiwoom.dynamicCall("GetLoginInfo(QString)", "GetServerGubun").strip()
            self.is_mock = (server_gubun == "1")
            
            mode_text = "🔵 [모의투자]" if self.is_mock else "🔴 [실계좌]"
            logger.info(f"✅ [엔진] 키움증권 로그인 성공 {mode_text}")
            self._reconnect_count = 0   # 재연결 성공 시 카운터 초기화
            self._reconnect_timer.stop()

            # [Fix #3] 로그인 시 모의/실계좌 구분 메시지
            self.notifier.discord(
                f"✅ **[K-Trader v{__version__}]** {mode_text} 키움증권 접속 완료\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"🖥️ 서버 구분: {'모의투자 서버' if self.is_mock else '실거래 서버 (실제 돈이 거래됩니다!)'}\n"
                f"⏰ 접속 시각: {time.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            accs = self.kiwoom.dynamicCall("GetLoginInfo(QString)", "ACCNO").strip(';').split(';')
            self.account_list = [a for a in accs if a]
            
            self.current_status = "READY_MOCK" if self.is_mock else "READY_REAL"
            self.kiwoom.dynamicCall("GetConditionLoad()")

            # [v7.5] 블랙리스트 캐시에서 종목명이 코드와 동일한 항목을 API로 보강
            try:
                for code in list(self._bl_cache.keys()):
                    if self._bl_cache[code] == code:
                        name = self.kiwoom.dynamicCall("GetMasterCodeName(QString)", code)
                        if name:
                            self._bl_cache[code] = name
            except Exception:
                pass
        else:
            self.current_status = "LOGIN_FAILED"

            # ── 점검/강제 단절 에러 → 프로그램 종료 (스케줄러가 재시작) ──────
            # -101: 사용자 정보교환 실패 (점검 중 단절)
            # -106: 통신 연결 종료 (키움 서버 점검)
            MAINTENANCE_ERRORS = (-101, -106)
            if err_code in MAINTENANCE_ERRORS:
                logger.warning(
                    f"⚠️ [엔진] 키움 점검/단절 감지 (err={err_code}) "
                    f"→ 프로그램 종료 후 스케줄러 재시작 대기"
                )
                self.notifier.notify_error(
                    "키움증권 연결 단절 → 프로그램 종료",
                    f"에러 코드: {err_code}\n"
                    f"점검으로 인한 단절입니다. 프로그램을 종료합니다.\n"
                    f"스케줄러가 자동으로 재시작합니다."
                )
                time.sleep(3)   # Discord 알림 전송 대기
                sys.exit(1)     # 종료 → Windows 스케줄러가 재시작
            # ──────────────────────────────────────────────────────────────────

            # 그 외 에러: 기존 지수 백오프 재연결 유지
            # 지수 백오프: 1회→30초, 2회→60초, 3회~→120초 후 재연결 시도
            delay_secs = min(30 * (2 ** min(self._reconnect_count, 2)), 120)
            self._reconnect_count += 1
            logger.warning(
                f"⚠️ [엔진] 키움 연결 실패/단절 (err={err_code}, "
                f"재연결 {self._reconnect_count}회차, {delay_secs}초 후 시도)"
            )
            self.notifier.notify_error(
                "키움증권 연결 단절",
                f"에러 코드: {err_code}\n{delay_secs}초 후 자동 재연결을 시도합니다."
            )
            self._reconnect_timer.start(delay_secs * 1000)

    def _do_reconnect(self):
        """키움 단절 후 지연 재연결 시도."""
        logger.info(f"🔄 [엔진] 키움 재연결 시도 ({self._reconnect_count}회차)...")
        try:
            self.kiwoom.dynamicCall("CommConnect()")
        except Exception as e:
            logger.error(f"❌ [엔진] CommConnect 재시도 실패: {e}")
            # 실패하면 다시 대기 후 재시도 (최대 120초)
            delay_secs = min(30 * (2 ** min(self._reconnect_count, 2)), 120)
            self._reconnect_count += 1
            self._reconnect_timer.start(delay_secs * 1000)

    def _on_condition_ver(self, ret, msg):
        if ret == 1:
            raw = self.kiwoom.dynamicCall("GetConditionNameList()").split(';')
            self.condition_list = [{'idx': c.split('^')[0], 'name': c.split('^')[1]} for c in raw if '^' in c]

    def _on_tr_data(self, screen_no, rqname, trcode, recordname, prev_next):
        self.kiwoom.dynamicCall("DisconnectRealData(QString)", screen_no)

        if rqname == "예수금조회":
            # 예수금/주문가능/출금가능을 각각 분리해서 읽습니다.
            # (UI 표시/알림/투자금 계산이 서로 다른 필드를 섞어 쓰면 불일치가 발생할 수 있음)
            raw_d2 = self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, 0, "d+2추정예수금")
            raw_ord = self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, 0, "주문가능금액")
            raw_wd  = self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, 0, "출금가능금액")
            raw_dep = self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, 0, "예수금")

            d2 = safe_int(raw_d2)
            ord_amt = safe_int(raw_ord)
            wd_amt = safe_int(raw_wd)
            dep = safe_int(raw_dep)

            # 가장 신뢰할 값: 주문가능금액(있으면) → d+2추정예수금 → 예수금
            base = ord_amt if ord_amt > 0 else (d2 if d2 > 0 else dep)

            self.deposit_total = d2 if d2 > 0 else base
            self.orderable_amount = ord_amt if ord_amt > 0 else base
            self.withdrawable_amount = wd_amt if wd_amt > 0 else base

            self.deposit = base
            self._deposit_last_ok_ts = time.time() if base > 0 else self._deposit_last_ok_ts

            if base == 0:
                logger.warning("⚠️ [엔진] 예수금/주문가능금액을 0원으로 인식했습니다. (비밀번호/시간대/조회 실패 가능)")
            else:
                logger.info(f"💡 [엔진] 예수금 동기화: 총(D+2)={self.deposit_total:,} / 주문가능={self.orderable_amount:,} / 출금가능={self.withdrawable_amount:,}")

            # [Fix #1] 잔고 조회에도 비밀번호 포함
            self.tr_scheduler.request_tr(
                rqname="최초잔고조회", trcode="opw00018", next_str=0, screen_no=self._next_tr_screen(),
                inputs=self._build_account_inputs({"조회구분": "1"})
            )

        elif rqname in ("최초잔고조회", "정기잔고교차검증"):
            rows = self.kiwoom.dynamicCall("GetRepeatCnt(QString, QString)", trcode, rqname)
            hts_port = {}
            for i in range(rows):
                code = self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, i, "종목번호").strip()[1:]
                name = self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, i, "종목명").strip()
                qty = safe_int(self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, i, "보유수량"))
                buy_p = safe_int(self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, i, "매입가"))
                curr_p = safe_int(self.kiwoom.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, i, "현재가"))
                if qty > 0:
                    hts_port[code] = {'name': name, 'qty': qty, 'buy_price': buy_p, 'current_price': curr_p}

            if rqname == "최초잔고조회":
                for code, data in hts_port.items():
                    is_manual = (code not in self._bot_bought_codes)
                    c_name = self.portfolio.get(code, {}).get('cond_name', "기존보유")
                    real_scr = self._next_real_screen()
                    self.portfolio[code] = {
                        'name': data['name'], 'buy_price': data['buy_price'], 'current_price': data['current_price'],
                        'qty': data['qty'], 'high_price': max(data['buy_price'], data['current_price']),
                        'status': 'HOLDING', 'sell_ordered': False, 'screen_no': real_scr,
                        'locked_amount': 0, 'is_manual': is_manual, 'cond_name': c_name
                    }
                    self.kiwoom.dynamicCall("SetRealReg(QString, QString, QString, QString)", real_scr, code, "10;13;71", "1")

                today = time.strftime("%Y%m%d")
                # [Fix #1] 당일실현손익 조회에도 비밀번호 포함
                self.tr_scheduler.request_tr(
                    rqname="당일실현손익조회", trcode="opt10074", next_str=0, screen_no=self._next_tr_screen(),
                    inputs=self._build_account_inputs({"시작일자": today, "종료일자": today})
                )
            else:
                self._reconcile_portfolio(hts_port)

        elif rqname == "당일실현손익조회":
            self.broker_today_realized_profit = safe_int(self.kiwoom.dynamicCall(
                "GetCommData(QString, QString, int, QString)", trcode, rqname, 0, "실현손익"))
            # UI/디스코드/DB는 DB 기반(또는 엔진 누적) 실현손익을 기준으로 표준화
            if (self.broker_today_realized_profit is not None) and (self.broker_today_realized_profit != self.today_realized_profit):
                logger.warning(f"⚠️ [엔진] 당일 실현손익 불일치: 키움={self.broker_today_realized_profit:+,} / DB기준={self.today_realized_profit:+,}")


    def _reconcile_portfolio(self, hts_port):
        for code in list(self.portfolio.keys()):
            if self.portfolio[code]['status'] != 'HOLDING':
                continue
            if code not in hts_port:
                self.kiwoom.dynamicCall("SetRealRemove(QString, QString)", self.portfolio[code]['screen_no'], code)
                del self.portfolio[code]
                self._bot_bought_codes.discard(code)

        for code, data in hts_port.items():
            if code not in self.portfolio:
                real_scr = self._next_real_screen()
                self.portfolio[code] = {
                    'name': data['name'], 'buy_price': data['buy_price'], 'current_price': data['current_price'],
                    'qty': data['qty'], 'high_price': max(data['buy_price'], data['current_price']),
                    'status': 'HOLDING', 'sell_ordered': False, 'screen_no': real_scr,
                    'locked_amount': 0, 'is_manual': True, 'cond_name': "수동/외부편입"
                }
                self.kiwoom.dynamicCall("SetRealReg(QString, QString, QString, QString)", real_scr, code, "10;13;71", "1")
            else:
                local_qty = self.portfolio[code]['qty']
                if local_qty != data['qty'] and self.portfolio[code]['status'] == 'HOLDING':
                    self.portfolio[code]['qty'] = data['qty']
                    self.portfolio[code]['buy_price'] = data['buy_price']
        self._save_bot_state()

    # ── 조건검색 및 실시간 ──────────────────────────
    def _on_real_condition(self, code, event_type, cond_name, cond_idx):
        stock_name = self.kiwoom.dynamicCall("GetMasterCodeName(QString)", code) or code

        if not self.is_trading:
            logger.debug(f"🚫 [조건식] {stock_name}({code}) 스킵: 매매 미가동 상태")
            return
        if event_type != "I":
            return  # 편출(D)은 정상 무시 — 로그 불필요

        if code in self.portfolio:
            reason = "이미 보유/주문 중"
            logger.info(f"🚫 [조건식] {stock_name}({code}) 스킵: {reason}")
            self._log_condition_signal(code, stock_name, cond_name, "스킵", reason)
            return
        if code in self.blacklist:
            if self.config_mgr.get("blacklist_enabled", True):
                reason = "당일 블랙리스트"
                logger.info(f"🚫 [조건식] {stock_name}({code}) 스킵: {reason}")
                self._log_condition_signal(code, stock_name, cond_name, "스킵", reason)
                return
            else:
                logger.info(f"ℹ️ [조건식] {stock_name}({code}) 블랙리스트이나 비활성 → 통과")
        if code in self._pending_buy:
            reason = "매수 대기열 중복"
            logger.info(f"🚫 [조건식] {stock_name}({code}) 스킵: {reason}")
            self._log_condition_signal(code, stock_name, cond_name, "스킵", reason)
            return
        if not self.calendar.is_trading_allowed():
            reason = "매매시간 외"
            logger.info(f"🚫 [조건식] {stock_name}({code}) 스킵: {reason}")
            self._log_condition_signal(code, stock_name, cond_name, "스킵", reason)
            return
        if self._check_loss_limit():
            reason = "일일 손실한도 초과"
            logger.info(f"🚫 [조건식] {stock_name}({code}) 스킵: {reason}")
            self._log_condition_signal(code, stock_name, cond_name, "스킵", reason)
            return

        config = self.config_mgr.config
        holding_count = len([c for c, d in list(self.portfolio.items()) if d['qty'] > 0])  # [Fix #4]
        max_hold = config.get("max_hold", 5)
        if holding_count >= max_hold:
            reason = f"보유한도 {holding_count}/{max_hold}"
            logger.info(f"🚫 [조건식] {stock_name}({code}) 스킵: {reason}")
            self._log_condition_signal(code, stock_name, cond_name, "스킵", reason)
            return

        self._pending_buy[code] = {'cond_name': cond_name, 'timestamp': time.time(), 'screen_no': self._next_real_screen()}
        self.kiwoom.dynamicCall("SetRealReg(QString, QString, QString, QString)",
                                self._pending_buy[code]['screen_no'], code, "10;13;71", "1")
        logger.info(f"✅ [조건식] {stock_name}({code}) 편입 → 매수 대기열 등록 (조건식: {cond_name})")
        self._log_condition_signal(code, stock_name, cond_name, "⏳ 대기", "체결가 수신 대기 중")

    def _on_real_data(self, code, real_type, real_data):
        if code in self._pending_buy and real_type == "주식체결":
            curr_p = abs(safe_int(self.kiwoom.dynamicCall("GetCommRealData(QString, int)", code, 10)))
            if curr_p <= 0:
                logger.warning(f"🚫 [매수] {code} 스킵: 현재가 0원 수신 (데이터 이상)")
                return

            info = self._pending_buy.pop(code)
            stock_name = self.kiwoom.dynamicCall("GetMasterCodeName(QString)", code)
            cfg = self.config_mgr.config

            # [Fix #4] invest_type에 따라 투자금 계산 방식 분리
            available = max(0, (self.orderable_amount if self.orderable_amount > 0 else self.deposit) - self.locked_deposit)
            invest_type = cfg.get("invest_type", "비중(%)")
            invest_val = cfg.get("invest", 20)

            if invest_type == "비중(%)":
                inv_amt = available * invest_val / 100.0
            else:
                inv_amt = min(invest_val, available)

            total_qty = int(inv_amt // curr_p)
            if total_qty <= 0:
                reason = f"예수금 부족 (가용={available:,}, 현재가={curr_p:,})"
                logger.warning(f"🚫 [매수] {stock_name}({code}) 스킵: 수량 0주 ({reason})")
                self._log_condition_signal(code, stock_name, info.get('cond_name', ''), "스킵", reason)
                self.kiwoom.dynamicCall("SetRealRemove(QString, QString)", info['screen_no'], code)
                return

            # [v7.5] 분할매수 처리
            split_state = None
            qty = total_qty
            try:
                if cfg.get("split_buy_enabled") and total_qty >= 2:
                    ratios = cfg.get("split_buy_ratios", [30, 70])
                    r1 = max(1, int(total_qty * ratios[0] / 100))
                    qty = r1  # 1차 수량
                    split_state = {
                        "total": total_qty, "entry_price": curr_p,
                        "rounds": [
                            {"qty": r1, "done": True, "pct": 0},
                            {"qty": total_qty - r1, "done": False, "pct": cfg.get("split_buy_confirm_pct", 1.0)},
                        ]
                    }
                    if len(ratios) >= 3 and cfg.get("split_buy_rounds", 2) >= 3:
                        r2 = max(1, int(total_qty * ratios[1] / 100))
                        r3 = total_qty - r1 - r2
                        split_state["rounds"] = [
                            {"qty": r1, "done": True, "pct": 0},
                            {"qty": r2, "done": False, "pct": cfg.get("split_buy_confirm_pct", 1.0)},
                            {"qty": max(1, r3), "done": False, "pct": cfg.get("split_buy_confirm_pct_3rd", 2.0)},
                        ]
                    logger.info(f"📊 [분할매수] {stock_name}({code}) 총{total_qty}주 → 1차:{qty}주")
            except Exception as e:
                logger.error(f"❌ [분할매수] 설정 오류, 전량매수로 진행: {e}")
                qty = total_qty
                split_state = None

            self.locked_deposit += curr_p * qty
            port_entry = {
                'name': stock_name, 'buy_price': 0, 'current_price': curr_p, 'high_price': curr_p,
                'qty': 0, 'status': 'BUY_REQ', 'sell_ordered': False, 'screen_no': info['screen_no'],
                'locked_amount': curr_p * qty, 'is_manual': False, 'cond_name': info['cond_name'],
                'last_price_ts': time.time()
            }
            if split_state:
                port_entry['split_buy'] = split_state
            # [v7.6] 분할매도 초기화 — TS 독립형 (Option C)
            try:
                if cfg.get("split_sell_enabled"):
                    ratio1     = cfg.get("split_sell_ratio1", 50)
                    offset     = cfg.get("split_sell_offset", 1.5)
                    profit_pct = self.config_mgr.get_condition_param(c_name, "profit") or 2.3
                    port_entry['split_sell'] = {
                        "initial_qty": total_qty,
                        "ratio1":      ratio1,      # 1차 매도 비중 (%)
                        "offset":      offset,      # 2차 트리거 = profit_pct + offset
                        "t1_done":     False,       # 1차 익절% 도달 여부
                        "t2_done":     False,       # 2차 (익절+offset%) 도달 여부
                        "profit_pct":  profit_pct,  # 1차 트리거 = 익절%
                    }
            except Exception as e:
                logger.error(f"❌ [분할매도] 초기화 오류: {e}")
            self.portfolio[code] = port_entry

            # [Critical Fix] 매수 주문은 반드시 TR 전용 화면번호를 사용해야 합니다.
            order_screen = self._next_tr_screen()
            self.tr_scheduler.request_order(
                rqname="실시간매수", screen_no=order_screen, acc_no=self.account,
                order_type=1, code=code, qty=qty, price=0,
                hoga_gb=cfg.get("order_type", "03"), org_order_no=""
            )
            self._bot_bought_codes.add(code)
            self._save_bot_state()
            if split_state:
                order_detail = f"[분할1차] {qty}주×{curr_p:,}={curr_p*qty:,}원 (계획:{total_qty}주)"
            else:
                order_detail = f"{qty}주×{curr_p:,}={curr_p*qty:,}원"
            logger.info(f"📈 [매수] {stock_name}({code}) 주문 발행: {order_detail} (조건식: {info['cond_name']})")
            self._log_condition_signal(code, stock_name, info['cond_name'], "✅ 매수주문", order_detail)
            return

        if code not in self.portfolio:
            return

        # '주식시세'에서도 현재가를 갱신해 UI가 멈춘 것처럼 보이는 문제를 방지합니다.
        # (체결 이벤트가 뜸한 종목은 '주식체결'만으로는 가격이 갱신되지 않을 수 있음)
        if real_type == "주식시세":
            curr_p = abs(safe_int(self.kiwoom.dynamicCall("GetCommRealData(QString, int)", code, 10)))
            if curr_p > 0:
                self.portfolio[code]['current_price'] = curr_p
                self.portfolio[code]['last_price_ts'] = time.time()
                # [Fix] SELL_REQ 상태 중에도 고점 갱신 허용 (TS 기준 고점 누락 방지)
                if self.portfolio[code].get('status') in ('HOLDING', 'SELL_REQ') and curr_p > self.portfolio[code].get('high_price', 0):
                    self.portfolio[code]['high_price'] = curr_p
            return

        if real_type == "주식체결":
            curr_p = abs(safe_int(self.kiwoom.dynamicCall("GetCommRealData(QString, int)", code, 10)))
            self.portfolio[code]['current_price'] = curr_p
            self.portfolio[code]['last_price_ts'] = time.time()
            data = self.portfolio[code]

            if data['buy_price'] == 0 or data['qty'] <= 0 or data['status'] != 'HOLDING' or data.get('sell_ordered') or data.get('is_manual'):
                # [v7.5] 분할매수 확인 (HOLDING 상태 + buy_price 확정 후)
                try:
                    if data.get('split_buy') and data['buy_price'] > 0 and data['status'] == 'HOLDING':
                        self._check_split_buy(code, curr_p)
                except Exception as e:
                    logger.error(f"❌ [분할매수] {code} 오류: {e}")
                return
            if curr_p > data['high_price']:
                data['high_price'] = curr_p

            # [v7.5] 분할매수 확인
            try:
                if data.get('split_buy'):
                    self._check_split_buy(code, curr_p)
            except Exception as e:
                logger.error(f"❌ [분할매수] {code} 오류: {e}")

            yield_rate = (curr_p - data['buy_price']) / data['buy_price'] * 100
            high_yield = (data['high_price'] - data['buy_price']) / data['buy_price'] * 100
            c_name = data.get('cond_name', '')

            ts_act = self.config_mgr.get_condition_param(c_name, "ts_activation") or 4.0
            ts_drop = self.config_mgr.get_condition_param(c_name, "ts_drop") or 0.75

            # [v7.6] 분할매도 처리 — TS 독립형 (Option C)
            # 로직:
            #   ① 손절(%):         전량 즉시 매도
            #   ② 익절%:           1차 비중(ratio1%)만 매도
            #   ③ 익절%+offset%:   잔여 전량 매도 (TS 없어도 작동)
            #   ④ TS 발동:         잔여 전량 매도 (①②③ 미충족 시)
            ss = data.get('split_sell')
            if ss:
                try:
                    loss_pct   = self.config_mgr.get_condition_param(c_name, "loss") or -1.7
                    profit_pct = ss.get('profit_pct') or (self.config_mgr.get_condition_param(c_name, "profit") or 2.3)
                    offset     = ss.get('offset', 1.5)
                    ratio1     = ss.get('ratio1', 50)
                    t1_done    = ss.get('t1_done', False)
                    t2_done    = ss.get('t2_done', False)
                    pending    = self._pending_sell_qty.get(code, 0)

                    # ① 손절: 전량
                    if yield_rate <= loss_pct:
                        sellable = data['qty'] - pending
                        if sellable > 0:
                            data['sell_ordered'] = True
                            data['_last_sell_reason'] = "🛑 손절"
                            self._execute_sell(code, "🛑 손절", sellable)
                        return

                    # ② 1차: 익절% 도달 → ratio1% 매도
                    if not t1_done and yield_rate >= profit_pct:
                        initial_qty = ss.get('initial_qty') or data['qty']
                        sq = max(1, int(initial_qty * ratio1 / 100))
                        sq = min(sq, data['qty'] - pending)
                        if sq > 0:
                            ss['t1_done'] = True
                            reason = f"🎯 분할1차 ({ratio1}% @ +{profit_pct:.1f}%)"
                            data['_last_sell_reason'] = reason
                            self._execute_sell(code, reason, sq)
                        return

                    # ③ 2차: 익절%+offset% 도달 → 잔여 전량 (TS 독립)
                    if t1_done and not t2_done and yield_rate >= profit_pct + offset:
                        sellable = data['qty'] - pending
                        if sellable > 0:
                            ss['t2_done'] = True
                            data['sell_ordered'] = True
                            reason = f"🎯 분할2차 (+{profit_pct + offset:.1f}%)"
                            data['_last_sell_reason'] = reason
                            self._execute_sell(code, reason, sellable)
                        return

                    # ④ TS 발동: t1 완료 여부와 무관하게 잔여 전량 매도
                    ts_use = self.config_mgr.get_condition_param(c_name, "ts_use")
                    if ts_use and not t2_done and high_yield >= ts_act:
                        if (data['high_price'] - curr_p) / data['high_price'] * 100 >= ts_drop:
                            sellable = data['qty'] - pending
                            if sellable > 0:
                                ss['t1_done'] = True   # 1차 미완료 상태에서 TS 발동 시 강제 완료 처리
                                ss['t2_done'] = True
                                data['sell_ordered'] = True
                                data['_last_sell_reason'] = "📉 T.S 발동"
                                self._execute_sell(code, "📉 T.S 발동", sellable)
                            return

                except Exception as e:
                    logger.error(f"❌ [분할매도] {code} 오류: {e}")
                return

            # 기존 전량매도 로직 (분할매도 비활성 시)
            reason = ""
            if self.config_mgr.get_condition_param(c_name, "ts_use") and high_yield >= ts_act:
                if (data['high_price'] - curr_p) / data['high_price'] * 100 >= ts_drop:
                    reason = "📉 T.S 발동"
            elif yield_rate >= (self.config_mgr.get_condition_param(c_name, "profit") or 2.3):
                reason = "🎯 익절"
            elif yield_rate <= (self.config_mgr.get_condition_param(c_name, "loss") or -1.7):
                reason = "🛑 손절"

            if reason:
                sellable = data['qty'] - self._pending_sell_qty.get(code, 0)
                if sellable > 0:
                    data['sell_ordered'] = True
                    data['_last_sell_reason'] = reason
                    self._execute_sell(code, reason, sellable)

    def _check_split_buy(self, code, curr_p):
        """[v7.5] 분할매수: 가격 확인 후 추가 매수."""
        data = self.portfolio.get(code)
        if not data or not data.get('split_buy'):
            return
        # [Fix] 매도 진행 중이거나 is_manual 종목은 추가 매수 금지
        if data.get('sell_ordered') or data.get('is_manual'):
            return
        sb = data['split_buy']
        ep = sb.get('entry_price', 0)
        if ep <= 0:
            return
        for i, rnd in enumerate(sb.get('rounds', [])):
            if rnd.get('done'):
                continue
            cpct = rnd.get('pct', 1.0)
            change_pct = (curr_p - ep) / ep * 100

            # 양수 pct: 상승확인 (change >= pct), 음수 pct: 물타기 (change <= pct)
            triggered = False
            if cpct >= 0:
                triggered = (change_pct >= cpct)
            else:
                triggered = (change_pct <= cpct)

            if not triggered:
                break  # 아직 미충족 → 다음 단계도 볼 필요 없음

            add_qty = rnd['qty']
            if add_qty <= 0:
                rnd['done'] = True
                continue
            available = max(0, (self.orderable_amount if self.orderable_amount > 0 else self.deposit) - self.locked_deposit)
            if curr_p * add_qty > available:
                logger.warning(f"⚠️ [분할매수] {data['name']}({code}) {i+1}차 예수금 부족")
                return
            rnd['done'] = True
            self.locked_deposit += curr_p * add_qty
            self.tr_scheduler.request_order(
                rqname="분할추가매수", screen_no=self._next_tr_screen(), acc_no=self.account,
                order_type=1, code=code, qty=add_qty, price=0,
                hoga_gb=self.config_mgr.get("order_type", "03"), org_order_no=""
            )
            direction = "물타기" if cpct < 0 else "확인"
            logger.info(f"📈 [분할매수] {data['name']}({code}) {i+1}차: {add_qty}주×{curr_p:,} ({direction}:{cpct:+.1f}%)")
            self._log_condition_signal(code, data['name'], data.get('cond_name',''), f"✅ 분할{i+1}차", f"{add_qty}주×{curr_p:,}")
            break  # 한 번에 한 단계만 실행

    def _execute_sell(self, code, reason, qty):
        self.portfolio[code]['status'] = 'SELL_REQ'
        self.tr_scheduler.request_order(
            rqname="실시간매도", screen_no=self._next_tr_screen(), acc_no=self.account,
            order_type=2, code=code, qty=qty, price=0,
            hoga_gb=self.config_mgr.get("order_type", "03"), org_order_no=""
        )
        self._pending_sell_qty[code] = self._pending_sell_qty.get(code, 0) + qty

    def _on_chejan(self, gubun, item_cnt, fid_list):
        if gubun != "0":
            return
        order_no = self.kiwoom.dynamicCall("GetChejanData(int)", 9203).strip()
        code = self.kiwoom.dynamicCall("GetChejanData(int)", 9001)[1:]
        status = self.kiwoom.dynamicCall("GetChejanData(int)", 913)
        buy_sell = self.kiwoom.dynamicCall("GetChejanData(int)", 905)
        unexec = safe_int(self.kiwoom.dynamicCall("GetChejanData(int)", 902))

        if status == "접수":
            self.unexecuted_orders[order_no] = {
                'code': code, 'time': time.time(), 'qty': unexec, 'type': buy_sell,
                'locked_amount': self.portfolio.get(code, {}).get('locked_amount', 0)
            }
        else:
            if order_no in self.unexecuted_orders:
                self.unexecuted_orders[order_no]['qty'] = unexec

        if status == "취소" and "+매수" in buy_sell:
            if code in self.portfolio and self.portfolio[code]['qty'] == 0:
                self.locked_deposit = max(0, self.locked_deposit - self.unexecuted_orders.get(order_no, {}).get('locked_amount', 0))
                self.kiwoom.dynamicCall("SetRealRemove(QString, QString)", self.portfolio[code].get('screen_no', "ALL"), code)
                del self.portfolio[code]
                self.unexecuted_orders.pop(order_no, None)

        elif status == "체결" and code in self.portfolio:
            exec_price = safe_int(self.kiwoom.dynamicCall("GetChejanData(int)", 910))
            cum_exec_qty = safe_int(self.kiwoom.dynamicCall("GetChejanData(int)", 911))
            # 키움 Chejan의 911(체결량)은 환경/이벤트에 따라 '이번 체결'이 아니라 '누적 체결'로 들어오는 경우가 있어
            # 주문번호 기준으로 이전 누적값을 기억해 델타(이번 체결수량)를 계산합니다.
            prev_cum = self._order_exec_cum.get(order_no, 0)
            if cum_exec_qty < prev_cum:
                prev_cum = 0
            exec_qty = max(0, cum_exec_qty - prev_cum) if cum_exec_qty > 0 else 0
            self._order_exec_cum[order_no] = cum_exec_qty

            if "+매수" in buy_sell and exec_qty > 0:
                p = self.portfolio[code]
                p['buy_price'] = ((p['buy_price'] * p['qty']) + (exec_price * exec_qty)) // (p['qty'] + exec_qty)
                p['qty'] += exec_qty
                p['high_price'] = max(p['high_price'], p['buy_price'])
                cost = exec_price * exec_qty
                self.locked_deposit = max(0, self.locked_deposit - cost)
                # 현금(주문가능/총예수금)을 체결 즉시 반영해 UI/알림 불일치를 막습니다.
                self.orderable_amount = max(0, (self.orderable_amount if self.orderable_amount > 0 else self.deposit) - cost)
                self.deposit_total = max(0, (self.deposit_total if self.deposit_total > 0 else self.deposit) - cost)
                self.withdrawable_amount = max(0, (self.withdrawable_amount if self.withdrawable_amount > 0 else self.deposit) - cost)
                self.deposit = self.orderable_amount
                self.db.log_trade("매수", p.get('cond_name', ''), p['name'], code, exec_price, exec_qty, 0)
                p['status'] = 'HOLDING'

                # [Fix] 분할매수 entry_price를 실제 체결가로 동기화
                # 주문 시점 curr_p(호가)와 실제 체결가(exec_price)가 다를 수 있어
                # 트리거 계산 기준을 실제 매수 평단가(buy_price)로 보정합니다.
                try:
                    sb = p.get('split_buy')
                    if sb and p['buy_price'] > 0:
                        sb['entry_price'] = p['buy_price']
                        # 1차 부분체결 대비: 2차 이후 round qty를 계획 총수량 기준으로 재계산
                        # 이미 done=True인 round의 실제 체결 수량 합산 후 미완료 round 재배분
                        done_qty = sum(r['qty'] for r in sb.get('rounds', []) if r.get('done'))
                        total_planned = sb.get('total', 0)
                        remaining_planned = max(0, total_planned - done_qty)
                        undone = [r for r in sb.get('rounds', []) if not r.get('done')]
                        if undone and remaining_planned > 0:
                            # 미완료 round가 하나면 남은 전량 배정, 둘 이상이면 비율 유지
                            if len(undone) == 1:
                                undone[0]['qty'] = remaining_planned
                            else:
                                total_undone_qty = sum(r['qty'] for r in undone)
                                if total_undone_qty > 0:
                                    for r in undone:
                                        r['qty'] = max(1, int(remaining_planned * r['qty'] / total_undone_qty))
                except Exception as e:
                    logger.error(f"❌ [분할매수] entry_price 동기화 오류: {e}")

                # [Critical Fix] 매수 체결 후 실시간 시세 구독 보장 (Safety Net)
                # 만약 이전 구독이 끊겼더라도, 여기서 재등록하면 가격 갱신이 보장됩니다.
                try:
                    real_scr = p.get('screen_no') or self._next_real_screen()
                    self.kiwoom.dynamicCall("SetRealReg(QString, QString, QString, QString)",
                                           real_scr, code, "10;13;71", "1")
                    p['screen_no'] = real_scr
                    logger.debug(f"🔄 [실시간] {p['name']}({code}) 매수체결 후 시세 구독 보장 (화면={real_scr})")
                except Exception as e:
                    logger.error(f"❌ [실시간] {code} 재등록 실패: {e}")

                # [Fix #3] is_mock 전달
                self.notifier.notify_buy(
                    stock_name=p['name'], code=code, price=exec_price, qty=exec_qty,
                    total_qty=p['qty'],
                    cond_name=p.get('cond_name', ''), deposit=self.orderable_amount,
                    is_mock=self.is_mock
                )

            elif "-매도" in buy_sell and exec_qty > 0:
                p = self.portfolio[code]
                realized = calc_sell_cost(p['buy_price'], exec_price, exec_qty, self.is_mock)
                self.today_realized_profit += realized

                # [Fix] 매도 체결 시 예수금 복구
                # 매수 시에는 (체결가*수량)만큼 예수금을 차감했기 때문에,
                # 매도 시에는 원금(buy_price*qty) + 순손익(realized)을 더해주면
                # 수수료/세금까지 반영된 현금 흐름이 됩니다.
                try:
                    self.deposit += (p['buy_price'] * exec_qty) + realized
                    if self.deposit < 0:
                        self.deposit = 0
                except Exception:
                    pass

                p['qty'] = max(0, p['qty'] - exec_qty)
                self._pending_sell_qty[code] = max(0, self._pending_sell_qty.get(code, 0) - exec_qty)
                self.db.log_trade("매도", p.get('cond_name', ''), p['name'], code, exec_price, exec_qty, realized)

                sell_reason = p.get('_last_sell_reason', '매도')
                # [Fix #3] is_mock 전달
                self.notifier.notify_sell(
                    stock_name=p['name'], code=code,
                    buy_price=p['buy_price'], sell_price=exec_price,
                    qty=exec_qty, pnl=realized, reason=sell_reason,
                    cond_name=p.get('cond_name', ''), deposit=self.orderable_amount,
                    is_mock=self.is_mock
                )

                if p['qty'] <= 0:
                    if not p.get('is_manual'):
                        self.blacklist.add(code)
                        self._bl_cache[code] = p.get('name', code)
                    self.kiwoom.dynamicCall("SetRealRemove(QString, QString)", p.get('screen_no', "ALL"), code)
                    del self.portfolio[code]
                    self._bot_bought_codes.discard(code)
                    self._save_bot_state()
                else:
                    p['status'] = 'HOLDING'

        if unexec == 0 and order_no in self.unexecuted_orders:
            del self.unexecuted_orders[order_no]

    def _check_unexecuted_orders(self):
        curr = time.time()
        for o_no, info in list(self.unexecuted_orders.items()):
            if curr - info['time'] > 60:
                o_type = 3 if "+매수" in info['type'] else 4
                self.tr_scheduler.request_order(
                    "미체결취소", self._next_tr_screen(), self.account,
                    o_type, info['code'], info['qty'], 0, "03", o_no
                )
                if o_type == 4 and info['code'] in self.portfolio:
                    code = info['code']
                    self.portfolio[code]['sell_ordered'] = False
                    self.portfolio[code]['status'] = 'HOLDING'

                    # [Fix] 매도 미체결 취소 시 pending sell 수량 복구
                    # (미체결 잔량만큼) pending을 줄여주지 않으면 이후 재매도가 막힐 수 있습니다.
                    try:
                        unexec_qty = int(info.get('qty', 0) or 0)
                        if unexec_qty > 0:
                            self._pending_sell_qty[code] = max(0, self._pending_sell_qty.get(code, 0) - unexec_qty)
                            if self._pending_sell_qty.get(code, 0) == 0:
                                self._pending_sell_qty.pop(code, None)
                    except Exception:
                        pass
                elif o_type == 3:
                    self.locked_deposit = max(0, self.locked_deposit - info.get('locked_amount', 0))
                del self.unexecuted_orders[o_no]


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


def run_engine(ipc_port):
    # 로그 로테이션: 30일 이상 된 로그 파일 자동 삭제
    _cleanup_old_logs(LOGS_DIR)

    # 엔진 로그 파일 (UI가 백그라운드 스폰해도 장애 원인 추적 가능)
    log_file = os.path.join(LOGS_DIR, f"engine_{time.strftime('%Y%m%d')}.log")
    kt_logger = logging.getLogger("ktrader")
    kt_logger.setLevel(logging.INFO)
    if not kt_logger.handlers:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        kt_logger.addHandler(fh)

    app = QApplication(sys.argv)
    engine = TradingEngine(ipc_port)
    sys.exit(app.exec_())


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    run_engine(port)