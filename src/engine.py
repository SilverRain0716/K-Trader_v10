"""
K-Trader - 매매 엔진 (백엔드 프로세스)
[v10.4 수정사항 — 코드 리뷰 기반 안정화]
  - Critical(C1): _on_chejan 매수취소 시 취소 수량 역산 수정 (원주문-누적체결 기반)
  - High(H1): __version__ "8.0.0"→"10.4.0" 통일 (utils.py)
  - High(H2): MarketCalendar cache_path를 get_app_dir() 기반 절대경로로 변경
  - High(H3): 지수 히스토리 list → deque(maxlen=400) 교체 (레이스 컨디션 방지)
  - High(H4): _tick_log/_signal_history/_condition_log → deque(maxlen) 교체
  - High(H5): SM 추적 종목 GetCommRealData 이중 호출 방지 (_sm_cached_price 캐싱)
  - Fix(M1): REQ_DEPOSIT IPC 명령 split('^') 방어 코딩
  - Fix(M2): _sync_routine 내 today 4회 중복 계산 → 1회 통합
  - Fix(M4): DEFAULT_CONFIG에서 v9.x TickMonitor 데드 설정 제거 (config_manager.py)
  - Fix(M5): 연말 마지막 영업일을 휴장일에 오등록하는 버그 제거 (market_calendar.py)
[v10.3 수정사항 — 스코어 체계 전면 재설계]
  - Breaking: 단일 스코어(buy+danger 통합) → buy_score 단독 (DANGER 매도 완전 폐기)
  - Breaking: 6개 지표 합산 스코어 → 3가지 AND 조건 (매수비율 + 대량빈도 + 상대임계)
  - Breaking: 틱 기반 10틱 윈도우 → 시간 기반 15초 윈도우
  - Breaking: baseline(OPT10085 TR 닻) 폐기 — TR 호출 제거
  - Breaking: DANGER 매도 전체 삭제 (Gate 0, _handle_smartmoney_danger, _execute_danger_sell)
  - Breaking: BUY_A/BUY_B 2단계 → BUY 단일 신호
  - Breaking: 히스테리시스(슈미트 트리거) 폐기 — 조건 충족 시 즉시 매수
  - Feature: 시간 기반 15초 윈도우 + 5분 이동평균 대비 상대 임계값 (+15%p)
  - Feature: 대량 틱 = 종목별 상위 10%(p90) 동적 계산
  - Feature: 시총 50조 이상(MEGA) → SM 감시 + 조건식 매수 완전 제외
  - Retain: 가격 기반 매도(손절/익절/TS/타임컷) 전부 유지 (변경 없음)
  - Retain: v10.2 버그 수정 전부 유지 (C4/C5/C6/H1/H7/M1~M6)
[v10.2 수정사항]
  - Critical(C4): 잔고조회 완료 전 매매 차단 — _portfolio_synced 플래그로 크래시 후 보유한도 무력화 방지
  - Critical(C5): SM 한도 초과 시 즉시매수 폴백 차단 — _pending_buy에서 제거 + 실시간 해제
  - Critical(C6): 크래시 후 is_manual=True 복원 방지 — is_trading 중 잔고조회 시 봇관리로 편입
  - Critical(C2/C3): DANGER 2단계 매도 수정 — 신규주문 대신 1단계 취소 후 시장가 재발행
  - High(H1): SM 매수 시 블랙리스트 체크 추가
  - High(H4): _on_receive_tr_condition 인덴트 정리
  - High(H7): _on_receive_tr_condition 대량 편입 제한 (max_watch×2) + C4 가드
  - Fix(M1): _log() 메서드 의도 주석 (propagate=False와 logger.info 공존 이유)
  - Fix(M2): _signal_history를 __init__에서 초기화 (hasattr/getattr 방어 제거)
  - Fix(M3): 미체결 취소 hoga_gb "03"→"00" 통일
  - Fix(M4): 분할매도 손절 경로에 _cancel_unfilled_buy_orders 추가
  - Fix(M5): cleanup_expired 타임아웃 해제 시 set_cooldown=False (재편입 즉시 허용)
  - Fix(M6): BASE_DIR 이중 정의 제거 (frozen-aware 정의 유지)
  - Fix(C1): 파일 주석 DANGER_GRACE_SEC=10초→5초 (실제 상수는 이미 5초)
[v10.1 수정사항]
  - Critical: 미체결 매수 주문 취소 (매도 전 _cancel_unfilled_buy_orders — 유령 포지션 방지)
  - Critical: SM 매수 시점 지수필터 재검사 (_handle_smartmoney_buy → _is_index_ok)
  - Feature: 종목 무게 분류(Tier) — 시총+거래대금 기반 SMALL/MID/LARGE 자동 분류
  - Feature: Tier별 동적 BIG_TICK_THRESHOLD + 상대적 보정 (avg_tick × 2.5배)
  - Feature: 매수 후 DANGER 면역기간 (DANGER_GRACE_SEC=5초)
  - Feature: DANGER 히스테리시스 갭 확대 (-0.30/-0.20 → Tier별, 기본 -0.40/-0.15)
  - Feature: DANGER→NEUTRAL 전환 후 쿨다운 (DANGER_COOLDOWN_SEC=5초)
  - Feature: 조건식 재편입 쿨다운 (REENTRY_COOLDOWN_SEC=30초, 매도완료는 면제)
  - Feature: 장 시작 지수 워밍업 (INDEX_WARMUP_SEC=60초간 SM 매수 차단)
  - Fix: SM 로그 중복 출력 (propagate=False)
[v10.0 수정사항]
  - Feature: SmartMoneyTracker 엔진 — TickMonitor 완전 교체
  - Feature: 프로그램 매매 역추산 (OPT10085 TR 닻 + 시간 정규화)
  - Feature: 호가 잠식률/역잠식률 분석 (타입 41 구독)
  - Feature: 6개 지표 합산 스코어 → BUY_A/BUY_B/DANGER/NEUTRAL 신호 등급
  - Feature: 히스테리시스(슈미트 트리거) 기반 신호 안정화
  - Feature: TWAP/VWAP 기계적 패턴 감지 (최소금액 + 변동계수 필터)
  - Fix: Gate 0 (DANGER) 분할매도 우선순위 버그 — 최상단 배치
  - Fix: 매도 스코어 비대칭 해소 — 대량 연속 매도 + 호가 역잠식률 추가
[v8.0 수정사항]
  - Feature: KOSPI/KOSDAQ 지수 실시간 수신 및 IPC 상태 전달
  - Feature: 지수 필터 — 설정 임계값 미만 시 조건식 매수 차단
  - Feature: 지수 필터 대상 선택 (KOSPI / KOSDAQ / 둘 다(AND) / 둘 중 하나(OR))
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
from collections import deque
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
from src.utils import safe_int, calc_sell_cost, get_user_data_dir, get_app_dir, resolve_db_path, __version__, COMMISSION_RATE, TAX_RATE, MOCK_FEE_RATE
from src.ipc import Engine_IPCClient

logger = logging.getLogger("ktrader")
# [v10.2/M6] BASE_DIR 이중 정의 제거 — 49~52줄의 frozen-aware 정의를 유지
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


# ============================================================
# [v10.3] SmartMoneyTracker — buy_score 전용 매수 판정 엔진
#   - 단일 스코어(buy+danger 통합) → buy_score 단독 (DANGER 매도 폐기)
#   - 틱 기반 10틱 윈도우 → 시간 기반 15초 윈도우
#   - baseline(OPT10085 TR 닻) 폐기
#   - 매도는 가격 기반(손절/익절/TS/타임컷)에만 의존
# ============================================================

# ── [v10.3] buy_score 판정 상수 ──────────────────────────────
BUY_WINDOW_SEC          = 15      # 매수비율/대량빈도 계산 윈도우 (초)
BUY_RATIO_RELATIVE_MIN  = 0.15    # 5분 이동평균 대비 매수비율 초과분 임계값 (+15%p)
BUY_RATIO_ABSOLUTE_MIN  = 0.70    # 매수비율 절대 하한 (70%)
BIG_BUY_FREQ_MIN        = 0.05    # 대량 매수 빈도 최소 (5%)
BUY_AVG_WINDOW_SEC      = 300     # 매수비율 이동평균 윈도우 (5분 = 300초)
MIN_TICKS_FOR_SIGNAL    = 30      # 워밍업: 최소 틱 수 (15초 윈도우에 충분한 데이터)
SIGNAL_EXPIRE_SEC       = 180     # 기본 감시 타임아웃 (초)

# ── [v10.3] 대량 틱 기준 ─────────────────────────────────────
# 종목별 상위 10% 틱을 "대량"으로 판정 (동적 계산)
# 최소 50틱 축적 후 p90을 계산, 그 전에는 Tier 기본값 사용
BIG_TICK_WARMUP_COUNT   = 50      # 동적 p90 계산 최소 틱 수

# ── [v10.1/M1] 종목 무게 분류(Tier) 기준 ─────────────────────
# 시가총액 기준 (1차 분류)
TIER_LARGE_MCAP   = 1_000_000_000_000   # 1조원 이상 → LARGE
TIER_MID_MCAP     = 200_000_000_000     # 2,000억 이상 → MID, 미만 → SMALL
# 거래대금 보정 (2차): 한 단계 상향/하향
TIER_UP_VOLUME_KRW   = 50_000_000_000   # 500억 이상 → 한 단계 ↑
TIER_DOWN_VOLUME_KRW = 3_000_000_000    # 30억 미만  → 한 단계 ↓

# ── [v10.3] Tier별 대량 틱 기본값 (p90 계산 전 사용) ──────────
TIER_PARAMS = {
    "SMALL": {"big_tick_default": 30_000_000},
    "MID":   {"big_tick_default": 80_000_000},
    "LARGE": {"big_tick_default": 200_000_000},
}
TIER_DEFAULT = "MID"

# ── [v10.3] 대형 우량주 제외 ─────────────────────────────────
MEGA_CAP_EXCLUDE = 50_000_000_000_000   # 시총 50조 이상 → SM 감시 및 매수 제외

# ── [v10.1/H3] 조건식 재편입 쿨다운 ──────────────────────────
REENTRY_COOLDOWN_SEC   = 30.0   # 추적 해제 후 재편입 차단 시간 (초)

# ── [v10.1/H4] 장 시작 지수 워밍업 ───────────────────────────
INDEX_WARMUP_SEC       = 60.0   # 장 시작 후 SM 매수 차단 시간 (초)

# ── 호가 잠식률 (buy_score 보조 지표, 향후 활용) ──────────────
SWEEP_BUFFER_SIZE      = 5      # 호가 잠식률 이동평균 윈도우


class SmartMoneyTracker:
    """
    [v10.3] 스마트 머니 매수 신호 엔진 (buy_score 전용).

    조건식 편입 종목에 대해 실시간 체결 데이터를 분석하여
    매수 신호(BUY)를 생성합니다. DANGER 매도는 폐기되었으며,
    매도는 가격 기반(손절/익절/TS/타임컷)에 의존합니다.

    buy_score 판정 조건 (다중 AND):
      1) 15초 매수비율이 5분 이동평균 대비 +15%p 이상
      2) 15초 매수비율이 절대 70% 이상
      3) 대량 매수 빈도 ≥ 5% (대량 = 해당 종목 상위 10%)

    동작 흐름:
      1) 조건검색식 편입 → watch(code) → SetRealReg
      2) 실시간 체결(타입 20) → on_tick() → buy_score 재계산
      3) 실시간 호가잔량(타입 41) → on_orderbook() → 보조 지표 갱신
      4) buy_score 조건 충족 → signal = "BUY"
    """

    def __init__(self, code: str, name: str, cond_name: str, screen_no: str,
                 tier: str = None):
        self.code = code
        self.name = name
        self.cond_name = cond_name
        self.screen_no = screen_no

        # ── Tier 분류 ──
        self.tier = tier or TIER_DEFAULT
        tp = TIER_PARAMS.get(self.tier, TIER_PARAMS[TIER_DEFAULT])
        self._big_tick_default = tp["big_tick_default"]

        # ── 틱 버퍼 (시간 기반 윈도우용) ──
        # 각 틱: (timestamp_sec, qty, is_buy)
        self._tick_buffer = deque(maxlen=5000)   # 충분한 버퍼
        self._tick_count = 0

        # ── 매수비율 이동평균 (5분) ──
        # (timestamp_sec, buy_ratio) 튜플 리스트
        self._ratio_history = deque(maxlen=600)  # 최대 600초분

        # ── 호가 잠식률 (보조 지표) ──
        self._prev_ask_total = 0
        self._prev_bid_total = 0
        self._sweep_buffer = deque(maxlen=SWEEP_BUFFER_SIZE)

        # ── 신호 상태 ──
        self._signal = "NEUTRAL"     # "BUY" 또는 "NEUTRAL"
        self._buy_score_met = False  # buy_score 조건 충족 여부
        self._last_buy_ratio = 0.0
        self._last_big_buy_freq = 0.0
        self._last_relative = 0.0

        # ── 타이밍 ──
        self._start_ts = time.time()
        self._signal_history = deque(maxlen=100)  # [v10.4/H4] deque로 교체 (자동 잘라내기)

        # ── [v10.3 Fix] p90 임계값 캐싱 (매 틱 sorted() 방지) ──
        self._cached_big_threshold = self._big_tick_default
        self._cached_big_threshold_ts = 0.0  # 마지막 계산 시각

    # ── 외부에서 읽는 속성 ──────────────────────────────────
    @property
    def signal(self) -> str:
        """현재 신호: BUY / NEUTRAL."""
        return self._signal

    @property
    def signal_strength(self) -> float:
        """현재 매수비율 (디버그/로그용)."""
        return self._last_buy_ratio

    @property
    def is_warmed_up(self) -> bool:
        """워밍업 완료 여부."""
        return self._tick_count >= MIN_TICKS_FOR_SIGNAL

    @property
    def tick_count(self) -> int:
        return self._tick_count

    # ── 주식체결 (타입 20) 수신 ──────────────────────────────
    def on_tick(self, price: int, volume: int, is_buy: bool):
        """실시간 체결 틱 수신. buy_score 재계산."""
        now = time.time()
        self._tick_buffer.append((now, volume, is_buy))
        self._tick_count += 1
        self._evaluate_buy_score(now)

    # ── 호가잔량 (타입 41) 수신 ──────────────────────────────
    def on_orderbook(self, ask1_vol: int, ask2_vol: int, ask3_vol: int,
                     bid1_vol: int = 0, bid2_vol: int = 0, bid3_vol: int = 0):
        """호가잔량 수신. 잠식률 갱신 (보조 지표)."""
        curr_ask = ask1_vol + ask2_vol + ask3_vol
        if self._prev_ask_total > 0:
            sweep = (self._prev_ask_total - curr_ask) / self._prev_ask_total
            self._sweep_buffer.append(sweep)
        self._prev_ask_total = curr_ask
        self._prev_bid_total = bid1_vol + bid2_vol + bid3_vol

    # ── [v10.3] buy_score 판정 (핵심) ────────────────────────
    def _evaluate_buy_score(self, now: float):
        """
        15초 윈도우 내 틱 데이터로 buy_score 3가지 조건을 평가.

        조건 (모두 AND):
          1) 매수비율(수량)이 5분 이동평균 대비 +15%p 이상
          2) 매수비율(수량)이 절대 70% 이상
          3) 대량 매수 빈도가 전체 틱 중 5% 이상
        """
        if not self.is_warmed_up:
            self._signal = "NEUTRAL"
            return

        # ── [v10.3 Fix] 15초 윈도우 내 틱 수집 — 역순 순회 최적화 ──
        # deque는 시간순 정렬이므로 최신(오른쪽)부터 역순으로 순회하다가
        # cutoff 미만인 시점에서 중단하면 전체 5000개를 순회하지 않아도 됨
        cutoff = now - BUY_WINDOW_SEC
        window_ticks = []
        for ts, qty, ib in reversed(self._tick_buffer):
            if ts < cutoff:
                break
            window_ticks.append((ts, qty, ib))

        if len(window_ticks) < 10:
            # [v10.3 Fix] 데이터 부족 시 디버그 변수 초기화 (UI 오표시 방지)
            self._last_buy_ratio = 0.0
            self._last_big_buy_freq = 0.0
            self._last_relative = 0.0
            self._signal = "NEUTRAL"
            return

        # ── 조건 1+2: 매수비율 (수량 가중) ──
        total_qty = sum(qty for _, qty, _ in window_ticks)
        buy_qty = sum(qty for _, qty, ib in window_ticks if ib)
        buy_ratio = buy_qty / total_qty if total_qty > 0 else 0.5

        # 5분 이동평균 갱신 (1초 간격으로 기록)
        if not self._ratio_history or (now - self._ratio_history[-1][0]) >= 1.0:
            self._ratio_history.append((now, buy_ratio))

        # 5분 이동평균 계산
        avg_cutoff = now - BUY_AVG_WINDOW_SEC
        recent_ratios = [r for ts, r in self._ratio_history if ts >= avg_cutoff]
        avg_5m = sum(recent_ratios) / len(recent_ratios) if recent_ratios else 0.5

        relative = buy_ratio - avg_5m

        # ── 조건 3: 대량 매수 빈도 ──
        big_threshold = self._get_big_tick_threshold(now)
        big_buy_count = sum(1 for _, qty, ib in window_ticks if qty >= big_threshold and ib)
        big_buy_freq = big_buy_count / len(window_ticks)

        # ── 디버그용 저장 ──
        self._last_buy_ratio = buy_ratio
        self._last_big_buy_freq = big_buy_freq
        self._last_relative = relative

        # ── 3가지 조건 AND 판정 ──
        prev_signal = self._signal
        cond1 = relative >= BUY_RATIO_RELATIVE_MIN         # 5분 대비 +15%p
        cond2 = buy_ratio >= BUY_RATIO_ABSOLUTE_MIN        # 절대 70%
        cond3 = big_buy_freq >= BIG_BUY_FREQ_MIN           # 대량 5%

        if cond1 and cond2 and cond3:
            self._signal = "BUY"
            self._buy_score_met = True
        else:
            self._signal = "NEUTRAL"
            self._buy_score_met = False

        # 신호 변경 기록
        if self._signal != prev_signal:
            self._on_signal_change(prev_signal, self._signal)

    def _get_big_tick_threshold(self, now: float = None) -> int:
        """대량 틱 기준: 50틱 이상이면 상위 10%(p90), 아니면 Tier 기본값.

        [v10.3 Fix] 3초 캐싱 — 매 틱마다 5000개 sorted() 방지.
        p90 값은 틱 몇 개로는 거의 변하지 않으므로 3초면 충분.
        """
        if now is None:
            now = time.time()
        # 캐시가 3초 이내면 재사용
        if (now - self._cached_big_threshold_ts) < 3.0:
            return self._cached_big_threshold
        if self._tick_count >= BIG_TICK_WARMUP_COUNT:
            qtys = sorted([qty for _, qty, _ in self._tick_buffer])
            if qtys:
                p90_idx = int(len(qtys) * 0.90)
                self._cached_big_threshold = max(1, qtys[min(p90_idx, len(qtys) - 1)])
                self._cached_big_threshold_ts = now
                return self._cached_big_threshold
        return self._big_tick_default

    # ── 신호 변경 이벤트 ──────────────────────────────────────
    def _on_signal_change(self, old_signal: str, new_signal: str):
        now = time.time()
        snapshot = {
            "ts": now,
            "old": old_signal,
            "new": new_signal,
            "buy_ratio": round(self._last_buy_ratio, 4),
            "relative": round(self._last_relative, 4),
            "big_buy_freq": round(self._last_big_buy_freq, 4),
            "tick_count": self._tick_count,
        }
        self._signal_history.append(snapshot)

    # ── UI 표시용 상태 반환 ──────────────────────────────────
    def get_status(self) -> dict:
        return {
            "name": self.name,
            "cond_name": self.cond_name,
            "signal": self._signal,
            "buy_ratio": round(self._last_buy_ratio, 3),
            "relative": round(self._last_relative, 3),
            "big_buy_freq": round(self._last_big_buy_freq, 3),
            "tick_count": self._tick_count,
            "warmed_up": self.is_warmed_up,
            "tier": self.tier,
            "big_tick_threshold": self._get_big_tick_threshold(),
            "signal_history": self._signal_history[-10:],
        }


class SmartMoneyManager:
    """
    [v10.3] 전체 종목의 SmartMoneyTracker를 관리하는 매니저.

    - watch()     → SmartMoneyTracker 생성 + 등록
    - unwatch()   → 추적기 제거
    - is_watching() → 감시 여부 확인
    - cleanup_expired() → 타임아웃 정리

    v10.3 변경사항:
    - 신호가 BUY / NEUTRAL (DANGER 폐기, BUY_B 폐기)
    - baseline(OPT10085 TR 닻) 폐기
    - 시총 50조 이상(MEGA) → watch 자체 거부
    """

    def __init__(self, config_mgr):
        """
        SmartMoney 매니저 초기화.

        Args:
            config_mgr: ConfigManager 인스턴스 (파라미터 조회용)
        """
        self.config_mgr = config_mgr
        self._trackers = {}     # {code: SmartMoneyTracker}
        self._tick_log = deque(maxlen=200)  # [v10.4/H4] deque로 교체 (자동 잘라내기)
        # [v10.1/H3] 재편입 쿨다운: {code: cooldown_expire_timestamp}
        self._cooldown_until = {}
        # [v10.1/M1] 키움 kiwoom 객체 참조 (watch 시 시총 조회용, TradingEngine에서 설정)
        self._kiwoom = None

    # ── 전용 로거 ──────────────────────────────────────────
    @staticmethod
    def _tick_logger():
        """SmartMoney 전용 로그 파일 핸들러."""
        tl = logging.getLogger("ktrader.smartmoney")
        if not tl.handlers:
            log_dir = os.path.join(get_app_dir(), "logs")
            os.makedirs(log_dir, exist_ok=True)
            fh = logging.FileHandler(
                os.path.join(log_dir, f"smartmoney_{time.strftime('%Y%m%d')}.log"),
                encoding="utf-8",
            )
            fh.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
            tl.addHandler(fh)
            tl.setLevel(logging.INFO)
            # [v10.1/M3] 부모 로거 전파 차단 → engine.log 중복 출력 방지
            tl.propagate = False
        return tl

    def _log(self, msg: str):
        """SmartMoney 전용 로그 + 메인 로그 양쪽에 기록.

        [v10.2/M1] 의도적으로 propagate=False인 SM 로거와 메인 logger.info()를 모두 호출.
        - self._tick_logger().info() → smartmoney_YYYYMMDD.log 전용 파일
        - logger.info()            → engine_YYYYMMDD.log 메인 파일
        propagate=False를 삭제하면 메인 로그에 2중 출력됩니다. 삭제하지 마세요.
        """
        self._tick_logger().info(msg)
        logger.info(msg)
        entry = {"time": time.strftime("%H:%M:%S"), "msg": msg}
        self._tick_log.append(entry)

    # ── [v10.1/M1] 종목 무게 분류 ────────────────────────────
    def _classify_tier(self, code: str) -> str:
        """
        키움 마스터 정보로 종목 무게(Tier)를 분류.
        TR 추가 호출 없이 GetMasterLastPrice + GetMasterListedStockCnt로 시총 추정.

        Returns: "SMALL" / "MID" / "LARGE" / "MEGA" (50조 이상 → SM 제외 대상)
        """
        tier = TIER_DEFAULT
        if not self._kiwoom:
            return tier
        try:
            last_price = abs(int(self._kiwoom.dynamicCall(
                "GetMasterLastPrice(QString)", code) or "0"))
            listed_cnt = abs(int(self._kiwoom.dynamicCall(
                "GetMasterListedStockCnt(QString)", code) or "0"))
            mcap = last_price * listed_cnt  # 시가총액 추정
            # [v10.3] 대형 우량주 제외
            if mcap >= MEGA_CAP_EXCLUDE:
                return "MEGA"
            if mcap >= TIER_LARGE_MCAP:
                tier = "LARGE"
            elif mcap >= TIER_MID_MCAP:
                tier = "MID"
            else:
                tier = "SMALL"
        except Exception:
            pass
        return tier

    def _adjust_tier_by_volume(self, code: str, tier: str, daily_volume_krw: int) -> str:
        """
        [v10.1/M1] 당일 거래대금으로 Tier를 1단계 보정.
        첫 틱 수신 시 FID 14(누적거래대금)로 호출.
        """
        if daily_volume_krw >= TIER_UP_VOLUME_KRW:
            if tier == "SMALL":
                return "MID"
            elif tier == "MID":
                return "LARGE"
        elif daily_volume_krw < TIER_DOWN_VOLUME_KRW:
            if tier == "LARGE":
                return "MID"
            elif tier == "MID":
                return "SMALL"
        return tier

    # ── 감시 등록/해제 ──────────────────────────────────────
    def watch(self, code: str, name: str, cond_name: str, screen_no: str,
              change_rate: float = 0.0) -> bool:
        """
        [v10.3] 종목 SmartMoney 추적 등록.
        감시한도 초과 시 등락률이 가장 낮은 종목을 교체(우선순위 기반).

        Args:
            code: 종목코드
            name: 종목명
            cond_name: 조건검색식 이름
            screen_no: 실시간 구독 화면번호
            change_rate: 등락률(%) — 우선순위 판정용

        Returns:
            True: 등록 성공, False: MEGA/쿨다운 등 구조적 거부
        """
        # [v10.1/H3] 재편입 쿨다운 체크
        if code in self._cooldown_until:
            if time.time() < self._cooldown_until[code]:
                return False  # 쿨다운 중 → 조용히 거부
            else:
                del self._cooldown_until[code]

        if code in self._trackers:
            return True  # 이미 추적 중

        # [v10.1/M1] Tier 분류
        tier = self._classify_tier(code)

        # [v10.3] 시총 50조 이상 → SM 감시 제외
        if tier == "MEGA":
            self._log(f"[SM] 🚫 {name}({code}) 시총 50조+ (MEGA) → SM 감시 제외")
            return False

        max_watch = self.config_mgr.get("tick_monitor_max_watch", 30)

        # [v10.3] 감시한도 초과 시 등락률 최저 종목 교체
        if len(self._trackers) >= max_watch:
            # 현재 감시 중인 종목 중 등락률이 가장 낮은 종목 찾기
            lowest_code = None
            lowest_rate = float('inf')
            for tc, tt in self._trackers.items():
                rate = getattr(tt, '_change_rate', 0.0)
                if rate < lowest_rate:
                    lowest_rate = rate
                    lowest_code = tc
            # 새 종목의 등락률이 기존 최저보다 높으면 교체
            if lowest_code and change_rate > lowest_rate:
                self._log(
                    f"[SM] 🔄 감시 교체: {self._trackers[lowest_code].name}({lowest_code}, "
                    f"{lowest_rate:+.1f}%) → {name}({code}, {change_rate:+.1f}%)"
                )
                self.unwatch(lowest_code, "등락률 우선순위 교체", set_cooldown=False)
            else:
                self._log(
                    f"[SM] ⚠️ {name}({code}, {change_rate:+.1f}%) 등록 불가: "
                    f"추적 한도 {max_watch}개, 최저 {lowest_rate:+.1f}%보다 낮음"
                )
                return False

        tracker = SmartMoneyTracker(code, name, cond_name, screen_no, tier=tier)
        tracker._change_rate = change_rate  # 우선순위 판정용 등락률 저장
        self._trackers[code] = tracker
        self._log(f"[SM] 👁️ {name}({code}) 추적 시작 (조건식: {cond_name}, Tier: {tier}, 등락률: {change_rate:+.1f}%)")
        return True

    def unwatch(self, code: str, reason: str = "", set_cooldown: bool = True):
        """
        종목 추적 해제.

        Args:
            set_cooldown: True이면 재편입 쿨다운 설정 (매도 완료 시에는 False)
        """
        if code in self._trackers:
            t = self._trackers[code]
            self._log(f"[SM] ❌ {t.name}({code}) 추적 해제 ({reason})")
            del self._trackers[code]
            # [v10.1/H3] 재편입 쿨다운 설정 (매도완료 제외)
            if set_cooldown:
                self._cooldown_until[code] = time.time() + REENTRY_COOLDOWN_SEC

    def is_watching(self, code: str) -> bool:
        """종목 추적 여부 확인."""
        return code in self._trackers

    def get_tracker(self, code: str):
        """종목별 추적기 반환 (없으면 None)."""
        return self._trackers.get(code)

    # ── 외부 인터페이스 (기존 TickMonitor 호환) ───────────────
    @property
    def watched_codes(self) -> dict:
        """UI 표시용 전체 추적 상태 반환."""
        return {code: t.get_status() for code, t in self._trackers.items()}

    @property
    def tick_log(self) -> list:
        """UI 표시용 로그."""
        return list(self._tick_log)

    # ── 타임아웃 정리 (엔진 sync에서 호출) ────────────────────
    def cleanup_expired(self, protected_codes: set = None) -> list:
        """
        [v10.3] 감시 정리. 타임아웃 폐기 — 조건식 이탈로만 해제.

        장중 계속 감시하며, 조건식에서 이탈하면 _on_real_condition("D")에서 unwatch.
        이 메서드는 하위 호환성을 위해 유지하되, 타임아웃으로 인한 해제는 하지 않습니다.

        Returns:
            list: 해제된 종목코드 리스트 (v10.3에서는 항상 빈 리스트)
        """
        return []


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
        self._orderable_from_tr = 0  # [Fix v9.1] TR에서 받아온 원본 주문가능금액
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

        # [v8.0] 지수 실시간 데이터
        self.kospi_rate = 0.0    # KOSPI 등락율(%)
        self.kospi_price = 0     # KOSPI 현재 지수
        self.kosdaq_rate = 0.0   # KOSDAQ 등락율(%)
        self.kosdaq_price = 0    # KOSDAQ 현재 지수
        # 지수 히스토리 (차트용, 당일 장중 1분봉 축적)
        self._kospi_history = deque(maxlen=400)   # [v10.4/H3] deque로 교체
        self._kosdaq_history = deque(maxlen=400)  # [v10.4/H3] deque로 교체
        self._kospi_history_last_min  = -1  # KOSPI 마지막 기록 분
        self._kosdaq_history_last_min = -1  # KOSDAQ 마지막 기록 분
        self._pending_sell_qty = {}
        self._condition_log = deque(maxlen=200)  # [v10.4/H4] deque로 교체
        self._bl_cache = {}       # {code: name} 블랙리스트 UI 표시용 캐시
        self._bl_tags = {}        # {code: "자동"/"수동"} 블랙리스트 등록 유형 태그
        self._traded_today = {}   # {code: {"name": str, "reason": str}} 당일 매매 완료 종목 (BL 모드 UI용)
        self._bl_manual_released = set()  # 모드2에서 수동 해제된 코드 (재등록 방지)
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

        # [v10.0] SmartMoney 추적 매니저 초기화
        self.tick_monitor = SmartMoneyManager(self.config_mgr)
        # [v10.1/M1] 키움 객체 참조 설정 (시총 조회용)
        self.tick_monitor._kiwoom = self.kiwoom

        # [v10.1/H4] 장 시작 시각 기록 (지수 워밍업용)
        self._market_open_ts = 0.0

        # [v10.2/C4] 잔고 동기화 완료 플래그 — 최초잔고조회 TR 응답 전까지 매매 차단
        # 크래시 후 재시작 시 portfolio가 비어있는 상태에서 조건식 편입이 먼저 도착하면
        # 보유한도 체크가 무력화되어 초과 매수가 발생하는 문제 방지
        self._portfolio_synced = False

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

        # TradingEngine.__init__ 내부 이벤트 연결 부분에 추가
        self.kiwoom.OnReceiveTrCondition.connect(self._on_receive_tr_condition)
      
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
                        self._bl_tags = data.get("blacklist_tags", {})
                        logger.info(f"✅ [상태] 블랙리스트 {len(saved_bl)}종목 복원 (당일)")
                    # [v9.0] 당일 매매 종목 + 수동해제 셋 복원
                    self._traded_today = data.get("traded_today", {})
                    self._bl_manual_released = set(data.get("bl_manual_released", []))
                else:
                    logger.info(f"🔄 [상태] 날짜 변경 감지 ({saved_date} → {today}) → 블랙리스트 초기화")
                    self.blacklist = set()
                    self._bl_cache = {}
                    self._bl_tags = {}
                    self._traded_today = {}
                    self._bl_manual_released = set()

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
                    "blacklist_tags": dict(getattr(self, '_bl_tags', {})),
                    "traded_today": dict(getattr(self, '_traded_today', {})),
                    "bl_manual_released": list(getattr(self, '_bl_manual_released', set())),
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ bot_state 저장 실패: {e}")

    def _calc_unrealized_profit(self) -> int:
        unrealized = 0
        for code, data in list(self.portfolio.items()):  # [Fix #4]
            if data.get('qty', 0) > 0 and data.get('buy_price', 0) > 0:
                unrealized += calc_sell_cost(data['buy_price'], data['current_price'], data['qty'], self.is_mock)
        return unrealized

    def _net_yield(self, buy_price: int, sell_price: int, qty: int) -> float:
        """
        [Fix v8.2] 수수료/세금 포함 순수익률 계산.
        엔진의 모든 매도 판정(익절/손절/TS)과 UI 표시가 이 기준으로 통일됩니다.
        """
        if buy_price <= 0 or qty <= 0:
            return 0.0
        invested = buy_price * qty
        net_pnl = calc_sell_cost(buy_price, sell_price, qty, self.is_mock)
        return (net_pnl / invested) * 100

    def _log_condition_signal(self, code: str, name: str, cond_name: str, result: str, reason: str = ""):
        """조건식 편입 기록을 남깁니다 (UI 실시간 표시 + DB 영구 저장)."""
        entry = {
            'time': time.strftime('%H:%M:%S'),
            'code': code,
            'name': name,
            'cond_name': cond_name,
            'result': result,
            'reason': reason,
        }
        self._condition_log.append(entry)
        # DB 영구 저장
        try:
            self.db.log_condition_signal(code, name, cond_name, result, reason)
        except Exception as e:
            logger.error(f"❌ [DB] 조건식 로그 저장 오류: {e}")

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

            # [v10.1/H4] 장 시작 시각 기록
            self._market_open_ts = time.time()

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

            # [v8.0] 지수 실시간 재등록 (장 시작 시 세션 갱신으로 끊길 수 있어 매일 재등록)
            # [Fix v8.1] 개별 화면번호로 등록
            try:
                self.kiwoom.dynamicCall(
                    "SetRealReg(QString, QString, QString, QString)",
                    "0098", "0001", "10;11;12;20", "0"
                )
                self.kiwoom.dynamicCall(
                    "SetRealReg(QString, QString, QString, QString)",
                    "0099", "1001", "10;11;12;20", "0"
                )
                logger.info("✅ [v8.0] 지수 실시간 재등록 완료 (장 시작 시)")
            except Exception as e:
                logger.error(f"❌ [v8.0] 지수 실시간 재등록 실패: {e}")

            # [Fix v8.1] 장 시작 시 TR 폴백으로 즉시 지수값 갱신
            try:
                self.tr_scheduler.request_tr(
                    rqname="지수조회_KOSPI", trcode="opt20001", next_str=0,
                    screen_no=self._next_tr_screen(),
                    inputs={"업종코드": "001"}
                )
                self.tr_scheduler.request_tr(
                    rqname="지수조회_KOSDAQ", trcode="opt20001", next_str=0,
                    screen_no=self._next_tr_screen(),
                    inputs={"업종코드": "101"}
                )
            except Exception as e:
                logger.error(f"❌ [v8.1] 장 시작 지수 TR 갱신 실패: {e}")

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
        # [Fix v9.1] orderable_amount 이중 차감 버그 수정:
        #   기존: orderable_amount(이미 체결 차감 반영) - locked_deposit → 매 sync마다 누적 차감
        #   수정: TR 원본값(_orderable_from_tr) 기준으로 locked만 차감, 체결 차감은 별도 추적
        try:
            # TR 원본값이 있으면 그 기준으로 locked만 차감
            if hasattr(self, '_orderable_from_tr') and self._orderable_from_tr > 0:
                self.orderable_amount = max(0, int(self._orderable_from_tr) - int(self.locked_deposit))
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

        # [Fix v8.1] 장중 60초마다 지수 TR 폴백 갱신
        # SetRealReg로 업종 실시간이 안 올 경우를 대비한 안전망
        if market_phase in ("REGULAR", "PRE_MARKET"):
            last_idx_ts = getattr(self, '_last_index_tr_ts', 0)
            if now_ts - last_idx_ts > 60:
                self._last_index_tr_ts = now_ts
                try:
                    self.tr_scheduler.request_tr(
                        rqname="지수갱신_KOSPI", trcode="opt20001", next_str=0,
                        screen_no=self._next_tr_screen(),
                        inputs={"업종코드": "001"}
                    )
                    self.tr_scheduler.request_tr(
                        rqname="지수갱신_KOSDAQ", trcode="opt20001", next_str=0,
                        screen_no=self._next_tr_screen(),
                        inputs={"업종코드": "101"}
                    )
                except Exception as e:
                    logger.debug(f"[v8.1] 지수 TR 갱신 요청 오류: {e}")

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
            "blacklist_mode": self.config_mgr.get("blacklist_mode", 1),
            "blacklist_tags": dict(getattr(self, "_bl_tags", {})),
            "traded_today": dict(getattr(self, "_traded_today", {})),
            "stock_lookup": getattr(self, "_stock_lookup", {}),
            # [v8.0] 지수 실시간 데이터
            "kospi_price":   self.kospi_price,
            "kospi_rate":    self.kospi_rate,
            "kosdaq_price":  self.kosdaq_price,
            "kosdaq_rate":   self.kosdaq_rate,
            "kospi_history":  list(self._kospi_history),
            "kosdaq_history": list(self._kosdaq_history),
            # [v10.0] SmartMoney 추적 상태
            "tick_monitor_watched": self.tick_monitor.watched_codes,
            "tick_monitor_log": self.tick_monitor.tick_log,
            "smartmoney_signals": {code: t.get_status()
                                   for code, t in self.tick_monitor._trackers.items()},
        }
        self.ipc_client.send_state(state)
        self.db.write_engine_state(state)

        # ── 자정 P&L 리셋 (AWS 24시간 운영 대응) ──────────────────────────
        # today_realized_profit은 누적 합산이므로, 날짜가 바뀌면 DB에서 오늘 기준으로 재로드합니다.
        # [v10.4/M2] today는 상단에서 이미 계산되었으므로 재사용
        try:
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

                # ── 블랙리스트 초기화 (당일 매매 종목은 다음날 해제) ──────────
                if self.blacklist:
                    cleared = len(self.blacklist)
                    self.blacklist.clear()
                    self._bl_cache = {}
                    self._bl_tags = {}
                    self._save_bot_state()
                    logger.info(f"🔄 [자정 리셋] 블랙리스트 {cleared}종목 초기화 완료")
                self._traded_today = {}
                self._bl_manual_released = set()
        except Exception as e:
            logger.error(f"❌ [자정 리셋] 오류: {e}")

        # ── 8:50 AM 장 시작 전 최종 재연결 안전망 ──────────────────────────
        # 키움 서버 점검(08:00~08:20) 후 재연결이 실패한 상태로 남아 있을 경우를 대비,
        # 8시 50분에 한 번 더 강제 재연결을 시도해 9시 장 시작에 대비합니다.
        try:
            now_dt = datetime.datetime.now()
            # [v10.4/M2] today는 상단에서 이미 계산되었으므로 재사용
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
        # [v10.4/M2] today는 상단에서 이미 계산되었으므로 재사용
        try:
            if self.calendar.is_eod_shutdown() and self._shutdown_report_sent_date != today:
                self._shutdown_report_sent_date = today
                logger.info("📊 [마감] 장 마감 감지 → 마감 리포트 전송")
                self._send_daily_report("장 마감 자동 종료")
                shutdown_opt = self.config_mgr.get("shutdown_opt", "프로그램 종료 안함")
                if shutdown_opt != "프로그램 종료 안함":
                    logger.info(f"🔴 [마감] shutdown_opt='{shutdown_opt}' → 엔진 종료 시작")
                    # [Fix] 엔진 종료 전 UI에 EOD 신호 전송
                    # sys.exit(0)이 PyInstaller+PyQt5 환경에서 비정상 exit code로
                    # 전달되어 UI가 크래시로 오인하는 문제 방지
                    try:
                        self._eod_shutdown_signaled = True
                        self.ipc_client.send_state({"eod_shutdown": True})
                        time.sleep(0.5)  # UI가 신호 수신할 시간 확보
                    except Exception:
                        pass
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

        # [v10.0] SmartMoney 타임아웃 정리 (틱이 안 오는 종목 안전망)
        try:
            expired_codes = self.tick_monitor.cleanup_expired(
                protected_codes=set(self.portfolio.keys())
            )
            for code in expired_codes:
                # [v10.0 Fix] 보유 중인 종목은 실시간 구독 해제 금지!
                # SM 타임아웃이어도 portfolio에 있으면 시세 구독은 유지해야
                # TS/손절/가격갱신이 정상 동작합니다.
                if code not in self.portfolio:
                    try:
                        self.kiwoom.dynamicCall("SetRealRemove(QString, QString)", "ALL", code)
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"❌ [SM] 타임아웃 정리 오류: {e}")

        # [Fix v9.1] BUY_REQ 유령 항목 정리
        # 매수 주문 발행 시 portfolio에 qty=0, status='BUY_REQ'로 등록하는데,
        # 체결이 안 오면(거부, 타임아웃 등) 유령 항목으로 잔류하는 버그 수정.
        # 60초 내 체결 미수신 시 자동 정리.
        try:
            buy_req_timeout = 60  # 초
            stale_buy_reqs = []
            for code, data in list(self.portfolio.items()):
                if data.get('status') == 'BUY_REQ' and data.get('qty', 0) == 0:
                    req_ts = data.get('last_price_ts', data.get('buy_req_ts', 0))
                    if req_ts and (now - req_ts) > buy_req_timeout:
                        stale_buy_reqs.append(code)
            for code in stale_buy_reqs:
                data = self.portfolio[code]
                name = data.get('name', code)
                locked = data.get('locked_amount', 0)
                self.locked_deposit = max(0, self.locked_deposit - locked)
                screen_no = data.get('screen_no', 'ALL')
                try:
                    self.kiwoom.dynamicCall("SetRealRemove(QString, QString)", screen_no, code)
                except Exception:
                    pass
                del self.portfolio[code]
                logger.warning(f"🧹 [정리] {name}({code}) BUY_REQ 유령 항목 제거 (체결 미수신 {buy_req_timeout}초 초과, locked 복구: {locked:,}원)")
        except Exception as e:
            logger.error(f"❌ [정리] BUY_REQ 유령 항목 정리 오류: {e}")

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
            # [v10.4/M1] split 안전성: '^'가 없거나 값이 부족한 경우 방어
            parts = args.split('^', 1)
            if len(parts) < 2:
                logger.error(f"❌ [IPC] REQ_DEPOSIT 형식 오류: '{args}' (계좌^비밀번호 필요)")
                return
            self.account, pw = parts[0], parts[1]
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
                    old_cfg = copy.deepcopy(self.config_mgr.config)
                    self.config_mgr.save(new_cfg)
                    self.config_mgr.config = new_cfg

                    # [Fix v8.1] 변경된 키 로깅 (디버그용)
                    changed = [k for k in new_cfg if old_cfg.get(k) != new_cfg.get(k)]
                    if changed:
                        logger.info(f"✅ [엔진] 설정 적용 완료(APPLY_SETTINGS): 변경={changed}")
                    else:
                        logger.info("✅ [엔진] 설정 적용 완료(APPLY_SETTINGS): 변경 없음")

                    # [Fix v8.1] 분할매도 설정 변경 시 기존 포트 동기화
                    # split_sell_enabled가 꺼졌으면 기존 포트의 split_sell dict 제거
                    if not new_cfg.get("split_sell_enabled", False):
                        for code, pdata in list(self.portfolio.items()):
                            if pdata.get('split_sell'):
                                del pdata['split_sell']
                                logger.info(f"🔄 [설정] {pdata.get('name',code)} 분할매도 해제 (설정 변경)")
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
                self._bl_tags[code] = "수동"
                logger.info(f"🚫 [블랙리스트] 추가: {name}({code})")
                self.db.log_blacklist("추가", code, name, "수동 추가")
                self._save_bot_state()

        elif cmd == "REMOVE_BLACKLIST":
            code = args.strip()
            name = self._bl_cache.get(code, code)
            self.blacklist.discard(code)
            self._bl_cache.pop(code, None)
            self._bl_tags.pop(code, None)
            # [v9.0] 모드2: 수동 해제 시 재등록 방지 셋에 추가
            bl_mode = self.config_mgr.get("blacklist_mode", 1)
            if bl_mode == 2:
                self._bl_manual_released.add(code)
            logger.info(f"✅ [블랙리스트] 제거: {name}({code})")
            self.db.log_blacklist("제거", code, name, "수동 제거")
            self._save_bot_state()

        elif cmd == "CLEAR_BLACKLIST":
            cnt = len(self.blacklist)
            for c, n in list(self._bl_cache.items()):
                self.db.log_blacklist("초기화", c, n, "전체 초기화")
            self.blacklist.clear()
            self._bl_cache.clear()
            self._bl_tags.clear()
            logger.info(f"🗑️ [블랙리스트] 전체 초기화 ({cnt}종목)")
            self._save_bot_state()

        elif cmd == "UPDATE_CONDITIONS":
            # 가동 중 조건식 추가/제거
            # args 형식: "idx1^name1;idx2^name2;..."  (현재 체크된 전체 목록)
            try:
                new_conds = {}
                for cond in args.split(';'):
                    if '^' in cond:
                        idx, name = cond.split('^', 1)
                        new_conds[name] = idx.strip()

                current_names = set(self.active_conditions)
                new_names = set(new_conds.keys())

                # 제거된 조건식 → SendConditionStop + pending_buy 정리
                for name in current_names - new_names:
                    cond_obj = next((c for c in self.condition_list if c['name'] == name), None)
                    if cond_obj:
                        try:
                            self.kiwoom.dynamicCall("SendConditionStop(QString, QString, int)",
                                                   "0300", name, int(cond_obj['idx']))
                        except Exception as e:
                            logger.warning(f"⚠️ [조건식] SendConditionStop 실패: {name} — {e}")
                    # 해당 조건식의 pending_buy 즉시 취소
                    cancelled = [code for code, info in list(self._pending_buy.items())
                                 if info.get('cond_name') == name]
                    for code in cancelled:
                        info = self._pending_buy.pop(code, None)
                        if info:
                            try:
                                self.kiwoom.dynamicCall("SetRealRemove(QString, QString)",
                                                       info['screen_no'], code)
                            except Exception:
                                pass
                        self.locked_deposit = max(0, self.locked_deposit - info.get('locked_amount', 0) if info else self.locked_deposit)
                        logger.info(f"🗑️ [조건식] {name} 제거 → {code} 매수대기 취소")
                    self.active_conditions = [c for c in self.active_conditions if c != name]
                    logger.info(f"🔴 [조건식] 감시 중단: {name}")

                # 추가된 조건식 → SendCondition
                for name in new_names - current_names:
                    idx = new_conds[name]
                    try:
                        self.kiwoom.dynamicCall("SendCondition(QString, QString, int, int)",
                                               self._next_real_screen(), name, int(idx), 1)
                        self.active_conditions.append(name)
                        logger.info(f"🟢 [조건식] 감시 추가: {name}")
                    except Exception as e:
                        logger.error(f"❌ [조건식] SendCondition 실패: {name} — {e}")

            except Exception as e:
                logger.error(f"❌ [UPDATE_CONDITIONS] 처리 오류: {e}")

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

        elif cmd == "TOGGLE_MANUAL":
            code = args.strip()
            if code in self.portfolio:
                data = self.portfolio[code]
                was_manual = data.get('is_manual', True)
                data['is_manual'] = not was_manual
                name = data.get('name', code)
                if data['is_manual']:
                    # 봇 관리 → 수동으로 전환
                    self._bot_bought_codes.discard(code)
                    logger.info(f"👤 [수동전환] {name}({code}) → 수동 관리 (익절/손절 해제)")
                else:
                    # 수동 → 봇 관리로 전환
                    self._bot_bought_codes.add(code)
                    # 고점 초기화 (현재가 기준으로 TS 추적 시작)
                    data['high_price'] = max(data.get('buy_price', 0), data.get('current_price', 0))
                    logger.info(f"🤖 [봇전환] {name}({code}) → 봇 관리 (익절/손절 활성)")
                self._save_bot_state()

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

            # [v8.0] 지수 실시간 등록 — 각 코드를 별도 화면번호로 등록
            # [Fix v8.1] 세미콜론 멀티등록 대신 개별 등록 (안정성 향상)
            # 코드: "0001"=KOSPI, "1001"=KOSDAQ
            try:
                self.kiwoom.dynamicCall(
                    "SetRealReg(QString, QString, QString, QString)",
                    "0098", "0001", "10;11;12;20", "0"
                )
                self.kiwoom.dynamicCall(
                    "SetRealReg(QString, QString, QString, QString)",
                    "0099", "1001", "10;11;12;20", "0"
                )
                logger.info("✅ [v8.0] 지수 실시간 등록 완료 (KOSPI=0098, KOSDAQ=0099)")
            except Exception as e:
                logger.error(f"❌ [v8.0] 지수 실시간 등록 실패: {e}")

            # [Fix v8.1] 지수 TR 폴백: SetRealReg가 업종 코드에 이벤트를 발생시키지 않을 수 있으므로
            # opt20001 (업종현재가요청) TR을 한 번 요청해서 초기 지수값을 확보합니다.
            try:
                self.tr_scheduler.request_tr(
                    rqname="지수조회_KOSPI", trcode="opt20001", next_str=0,
                    screen_no=self._next_tr_screen(),
                    inputs={"업종코드": "001"}
                )
                self.tr_scheduler.request_tr(
                    rqname="지수조회_KOSDAQ", trcode="opt20001", next_str=0,
                    screen_no=self._next_tr_screen(),
                    inputs={"업종코드": "101"}
                )
                logger.info("✅ [v8.1] 지수 TR 초기 조회 요청 완료 (KOSPI=001, KOSDAQ=101)")
            except Exception as e:
                logger.error(f"❌ [v8.1] 지수 TR 초기 조회 실패: {e}")

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
            self._orderable_from_tr = self.orderable_amount  # [Fix v9.1] TR 원본값 보존 (이중 차감 방지)
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
                    # [v10.2/C6] is_manual 판정 개선
                    # 기존: _bot_bought_codes에 없으면 무조건 is_manual=True
                    # 문제: 크래시 후 재시작 시 매수/매도 사이클을 거친 종목이
                    #       _bot_bought_codes에서 빠져있어 is_manual=True → 손절/익절 미작동
                    # 수정: is_trading 상태에서 잔고에 있는 종목은 봇 관리로 간주하고
                    #       _bot_bought_codes에도 추가. 사용자가 수동 전환은 UI에서 가능.
                    if self.is_trading and code not in self._bot_bought_codes:
                        # 매매 가동 중 잔고조회 = 크래시 복구 가능성 → 봇 관리로 편입
                        self._bot_bought_codes.add(code)
                        logger.info(f"🔄 [C6] {data['name']}({code}) _bot_bought_codes에 추가 (크래시 복구)")
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

                # [v10.2/C4] 잔고 동기화 완료 → 매매 허용
                self._portfolio_synced = True
                holding_count = len([c for c, d in self.portfolio.items() if d.get('qty', 0) > 0])
                logger.info(f"✅ [C4] 잔고 동기화 완료: 보유 {holding_count}종목 → 매매 허용")

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
            # [Fix] 키움 실제 손익과 DB 누적값 불일치 시 키움 값으로 보정
            # 키움 opt10074가 실제 체결 기준이므로 더 신뢰도 높음
            # 단, 차이가 10원 이하면 부동소수점 오차로 보고 무시
            if self.broker_today_realized_profit is not None:
                diff = abs(self.broker_today_realized_profit - self.today_realized_profit)
                if diff > 10:
                    logger.warning(
                        f"⚠️ [엔진] 당일 실현손익 불일치: 키움={self.broker_today_realized_profit:+,} / "
                        f"DB기준={self.today_realized_profit:+,} → 키움 값으로 보정"
                    )
                    self.today_realized_profit = self.broker_today_realized_profit

        # [v10.3] OPT10085 프로그램매매 닻 — 폐기 (baseline 삭제)
        # 기존 "프로그램닻_" rqname 응답은 더 이상 발생하지 않음

        # [Fix v8.1] 지수 TR 응답 핸들러 (opt20001 업종현재가요청)
        elif rqname in ("지수조회_KOSPI", "지수조회_KOSDAQ", "지수갱신_KOSPI", "지수갱신_KOSDAQ"):
            try:
                raw_price = self.kiwoom.dynamicCall(
                    "GetCommData(QString, QString, int, QString)", trcode, rqname, 0, "현재가")

                # [Fix v8.2] 등락율 필드명 — 키움 opt20001은 필드명이 환경마다 다를 수 있음
                # 가능한 필드명을 순서대로 시도
                raw_rate = ""
                for rate_field in ("등락율", "등락률", "전일대비등락률", "전일대비등락율"):
                    raw_rate = self.kiwoom.dynamicCall(
                        "GetCommData(QString, QString, int, QString)", trcode, rqname, 0, rate_field).strip()
                    if raw_rate:
                        break

                # 전일대비 필드도 가져와서 등락율 직접 계산 폴백
                raw_diff = self.kiwoom.dynamicCall(
                    "GetCommData(QString, QString, int, QString)", trcode, rqname, 0, "전일대비")

                price_str = raw_price.strip().replace(',', '').replace('+', '').replace(' ', '')
                rate_str = raw_rate.replace(',', '').replace('+', '').replace(' ', '').strip() if raw_rate else ""
                diff_str = raw_diff.strip().replace(',', '').replace('+', '').replace(' ', '') if raw_diff else ""

                price = abs(float(price_str)) if price_str else 0
                rate = float(rate_str) if rate_str else 0.0

                # [Fix v8.2] 등락율이 0이고 전일대비가 있으면 직접 계산
                if rate == 0.0 and diff_str and price > 0:
                    try:
                        diff_val = float(diff_str)
                        prev_price = price - diff_val
                        if prev_price > 0:
                            rate = (diff_val / prev_price) * 100
                    except (ValueError, ZeroDivisionError):
                        pass

                # 디버그: 처음 5회는 raw 값 전체 로깅
                _tr_idx_cnt = getattr(self, '_tr_idx_log_cnt', 0)
                if _tr_idx_cnt < 5:
                    self._tr_idx_log_cnt = _tr_idx_cnt + 1
                    logger.info(
                        f"[지수TR디버그] {rqname}: 현재가='{raw_price.strip()}' "
                        f"등락율='{raw_rate}' 전일대비='{raw_diff.strip()}' → price={price}, rate={rate:.2f}"
                    )

                if price > 0:
                    is_kospi = "KOSPI" in rqname
                    if is_kospi:
                        self.kospi_price = price
                        self.kospi_rate = rate
                    else:
                        self.kosdaq_price = price
                        self.kosdaq_rate = rate

                    # 히스토리 축적
                    now = datetime.datetime.now()
                    cur_min = now.hour * 60 + now.minute
                    ts_str = now.strftime("%H:%M")
                    if is_kospi and cur_min != self._kospi_history_last_min:
                        self._kospi_history_last_min = cur_min
                        self._kospi_history.append((ts_str, price, rate))
                    elif not is_kospi and cur_min != self._kosdaq_history_last_min:
                        self._kosdaq_history_last_min = cur_min
                        self._kosdaq_history.append((ts_str, price, rate))

                    label = "KOSPI" if is_kospi else "KOSDAQ"
                    logger.info(f"📊 [지수TR] {label} = {price:,.2f} ({rate:+.2f}%)")
            except Exception as e:
                logger.error(f"❌ [지수TR] {rqname} 파싱 오류: {e}")


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
    def _is_index_ok(self) -> bool:
        """
        [v8.0] 지수 필터 체크.
        - index_filter_enabled=False 이면 항상 True (필터 비활성)
        - [Fix v8.1] 지수 데이터 미수신(price==0) 상태에서는:
          * 장 시작 전(PRE_MARKET): 통과 (아직 데이터 없는 게 정상)
          * 장중(REGULAR): 통과 (TR 폴백으로 데이터 확보 시도 중)
          * 데이터 수신 후 rate==0.0 → 보합이므로 threshold 비교로 판정
        - target: "kospi" / "kosdaq" / "both"(AND) / "either"(OR)
        """
        cfg = self.config_mgr.config
        if not cfg.get("index_filter_enabled", False):
            return True

        threshold = cfg.get("index_filter_threshold", -2.0)
        target = cfg.get("index_filter_target", "both")

        # 지수 데이터가 아직 수신 안 됨 (price가 0) → 통과 (TR 폴백이 곧 갱신할 것)
        # 데이터가 수신되었으면 (price > 0) → rate 기준으로 판정
        kospi_ok  = (self.kospi_price == 0) or (self.kospi_rate >= threshold)
        kosdaq_ok = (self.kosdaq_price == 0) or (self.kosdaq_rate >= threshold)

        if target == "kospi":
            return kospi_ok
        elif target == "kosdaq":
            return kosdaq_ok
        elif target == "either":   # OR: 둘 중 하나라도 통과
            return kospi_ok or kosdaq_ok
        else:                      # "both" (AND, 기본): 둘 다 통과
            return kospi_ok and kosdaq_ok

    # ── 조건검색 및 실시간 ──────────────────────────
    def _on_real_condition(self, code, event_type, cond_name, cond_idx):
        stock_name = self.kiwoom.dynamicCall("GetMasterCodeName(QString)", code) or code

        if not self.is_trading:
            logger.debug(f"🚫 [조건식] {stock_name}({code}) 스킵: 매매 미가동 상태")
            return
        # [v10.2/C4] 잔고 동기화 완료 전 매매 차단
        # 크래시 후 재시작 시 portfolio가 비어있으면 보유한도 체크가 무력화됨
        if not self._portfolio_synced:
            logger.info(f"🚫 [조건식] {stock_name}({code}) 스킵: 잔고 동기화 미완료 (C4)")
            self._log_condition_signal(code, stock_name, cond_name, "스킵", "잔고 동기화 대기 중")
            return
        if event_type != "I":
            # [v9.0] 편출(D) 시 틱 감시 해제 (보유 중이 아닌 경우만)
            if event_type == "D" and self.tick_monitor.is_watching(code):
                self.tick_monitor.unwatch(code, "조건식 이탈")
                if code not in self.portfolio:
                    try:
                        self.kiwoom.dynamicCall("SetRealRemove(QString, QString)", "ALL", code)
                    except Exception:
                        pass
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
        # [v10.3] 시총 50조 이상(MEGA) → 조건식 편입 자체를 무시
        if self.tick_monitor._kiwoom:
            tier = self.tick_monitor._classify_tier(code)
            if tier == "MEGA":
                logger.info(f"🚫 [조건식] {stock_name}({code}) 스킵: 시총 50조+ (MEGA)")
                self._log_condition_signal(code, stock_name, cond_name, "스킵", "시총 50조+ 제외")
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

        # [v8.0] 지수 필터
        # [v10.1] SM 모드에서는 지수필터가 watch 등록을 차단하지 않음
        # → 감시는 열어두되 매수 시점에서 _handle_smartmoney_buy()가 재검사 (C2)
        tick_mon_enabled = self.config_mgr.get_condition_param(cond_name, "tick_monitor_enabled")
        if not self._is_index_ok() and not tick_mon_enabled:
            # 비SM 모드(즉시매수)에서만 지수필터로 차단
            cfg = self.config_mgr.config
            threshold = cfg.get("index_filter_threshold", -2.0)
            reason = (
                f"지수필터 차단 (KOSPI {self.kospi_rate:+.2f}% / "
                f"KOSDAQ {self.kosdaq_rate:+.2f}% | 기준 {threshold:+.1f}%)"
            )
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
                                self._pending_buy[code]['screen_no'], code, "10;13;15;71", "1")

        # [v10.0] SmartMoney 모드 분기 (tick_mon_enabled는 위에서 이미 조회됨)
        if tick_mon_enabled:
            # SmartMoney 모드: 추적기 생성, 신호 발생까지 매수 보류
            screen_no = self._pending_buy[code]['screen_no']
            # [v10.3] 등락률 조회 → 감시 우선순위 판정용
            try:
                raw_rate = self.kiwoom.dynamicCall("GetCommRealData(QString, int)", code, 12)
                change_rate = float(raw_rate.strip()) if raw_rate and raw_rate.strip() else 0.0
            except Exception:
                change_rate = 0.0
            if self.tick_monitor.watch(code, stock_name, cond_name, screen_no, change_rate=change_rate):
                # SmartMoney에 등록 성공 → _pending_buy에서 제거 (즉시매수 방지)
                del self._pending_buy[code]

                # [v10.0] 호가잔량(타입 41) 추가 구독 — 체결(20) + 호가(41)
                try:
                    self.kiwoom.dynamicCall("SetRealReg(QString, QString, QString, QString)",
                                           screen_no, code, "20;41", "1")
                except Exception as e:
                    logger.error(f"❌ [SM] {code} 호가잔량 구독 실패: {e}")

                # [v10.3] OPT10085 baseline 폐기 — TR 호출 불필요

                logger.info(f"👁️ [SM] {stock_name}({code}) 편입 → SmartMoney 추적 시작 (조건식: {cond_name})")
                self._log_condition_signal(code, stock_name, cond_name, "👁️ SM추적", "스마트머니 분석 중")
            else:
                # [v10.2/C5] 감시 한도 초과 → 즉시매수 폴백 차단
                # SM 모드의 의도(분석 후 매수)를 유지하기 위해 _pending_buy에서도 제거
                info = self._pending_buy.pop(code, None)
                if info:
                    try:
                        self.kiwoom.dynamicCall("SetRealRemove(QString, QString)", info.get('screen_no', 'ALL'), code)
                    except Exception:
                        pass
                logger.info(f"🚫 [SM] {stock_name}({code}) SM 감시 한도 초과 → 매수 보류 (조건식: {cond_name})")
                self._log_condition_signal(code, stock_name, cond_name, "스킵", "SM한도초과 → 매수보류")
        else:
            # 기존 즉시매수 모드
            logger.info(f"✅ [조건식] {stock_name}({code}) 편입 → 매수 대기열 등록 (조건식: {cond_name})")
            self._log_condition_signal(code, stock_name, cond_name, "⏳ 대기", "체결가 수신 대기 중")

    # [v10.2 추가] 프로그램 재시작 시 기존 편입 종목 복구용
    def _on_receive_tr_condition(self, screen_no, code_list, cond_name, cond_index, next_val):
        if not code_list:
            return

        # [v10.2/C4] 잔고 동기화 완료 전이면 편입 처리 차단
        if not self._portfolio_synced:
            codes = [c for c in code_list.split(';') if c]
            logger.warning(
                f"🚫 [조건식] '{cond_name}' 초기 종목 {len(codes)}개 수신 → "
                f"잔고 동기화 미완료로 전체 스킵 (C4)"
            )
            return

        # 종목 코드 분리 (안전하게 빈 값 필터링)
        codes = [c for c in code_list.split(';') if c]

        # 이미 보유 중이거나 대기 중인 종목은 제외
        valid_codes = [c for c in codes if c not in self.portfolio and c not in self._pending_buy]

        # [v10.2/H7] 대량 편입 제한 — SM watch 한도의 2배까지만 처리
        # 수백 종목이 한꺼번에 들어오면 키움 API 과부하 → 크래시 유발 방지
        max_watch = self.config_mgr.get("tick_monitor_max_watch", 15)
        max_process = max_watch * 2
        if len(valid_codes) > max_process:
            logger.warning(
                f"⚠️ [조건식] '{cond_name}' 초기 종목 {len(valid_codes)}개 중 "
                f"{max_process}개만 처리 (H7 과부하 방지)"
            )
            valid_codes = valid_codes[:max_process]

        logger.info(f"📥 [조건식] '{cond_name}' 초기 종목 {len(codes)}개 수신, {len(valid_codes)}개 편입 예정")

        # ⭐️ 핵심: 키움 API 과부하(먹통) 방지를 위해 0.2초(200ms) 간격으로 분산 처리
        for i, code in enumerate(valid_codes):
            # lambda 변수 캡처를 통해 각 종목이 0.2초, 0.4초, 0.6초 뒤에 순차적으로 실행됨
            QTimer.singleShot(i * 200, lambda c=code, n=cond_name, idx=cond_index: self._on_real_condition(c, "I", n, idx))

    def _on_real_data(self, code, real_type, real_data):
        # [v8.0] 지수 실시간 수신 (KOSPI/KOSDAQ) — 종목 처리와 완전히 분리
        # [Fix v8.1] real_type 조건 완화: 코드 기반으로 먼저 분리
        if code in ("0001", "1001"):
            # 디버그: 처음 10회만 로깅 (real_type 확인용)
            _cnt = getattr(self, '_idx_real_log_cnt', 0)
            if _cnt < 10:
                self._idx_real_log_cnt = _cnt + 1
                logger.info(f"[지수실시간] code={code} real_type='{real_type}'")
            try:
                price_raw = self.kiwoom.dynamicCall("GetCommRealData(QString, int)", code, 10)
                rate_raw  = self.kiwoom.dynamicCall("GetCommRealData(QString, int)", code, 12)
                if not price_raw.strip() or not rate_raw.strip():
                    return  # 빈 데이터면 무시

                # [Fix v8.1] 부호(±) 처리 개선: 키움은 "+2580.5" 또는 "-1.25" 형식
                price_str = price_raw.replace(',', '').replace('+', '').replace(' ', '').strip()
                rate_str = rate_raw.replace(',', '').replace(' ', '').strip()
                # 부호 보존: rate_raw에 '-'가 있으면 음수
                price = abs(float(price_str)) if price_str else 0
                rate = float(rate_str) if rate_str else 0.0

                if price <= 0:
                    return  # 유효하지 않은 데이터

                if code == "0001":
                    self.kospi_price = price
                    self.kospi_rate  = rate
                else:
                    self.kosdaq_price = price
                    self.kosdaq_rate  = rate

                # 1분봉 히스토리 축적 (차트용) — KOSPI/KOSDAQ 각각 독립 관리
                now = datetime.datetime.now()
                cur_min = now.hour * 60 + now.minute
                ts_str = now.strftime("%H:%M")
                if code == "0001":
                    if cur_min != self._kospi_history_last_min:
                        self._kospi_history_last_min = cur_min
                        self._kospi_history.append((ts_str, price, rate))
                else:
                    if cur_min != self._kosdaq_history_last_min:
                        self._kosdaq_history_last_min = cur_min
                        self._kosdaq_history.append((ts_str, price, rate))
            except Exception as e:
                logger.debug(f"[v8.0] 지수 데이터 파싱 오류 ({code}): {e}")
            return
      
        # [v10.0] SmartMoney 추적 종목: 체결 틱 & 호가잔량 전달
        _sm_cached_price = 0  # [v10.4/H5] SM에서 파싱한 현재가 캐싱 (API 이중 호출 방지)
        if self.tick_monitor.is_watching(code):
            tracker = self.tick_monitor.get_tracker(code)
            if tracker is None:
                pass
            elif real_type == "주식체결":
                try:
                    tick_price = abs(safe_int(self.kiwoom.dynamicCall("GetCommRealData(QString, int)", code, 10)))
                    tick_vol_raw = safe_int(self.kiwoom.dynamicCall("GetCommRealData(QString, int)", code, 15))
                    is_buy_tick = (tick_vol_raw > 0)
                    tick_vol = abs(tick_vol_raw)

                    # [v10.1/M1] 첫 틱 수신 시 거래대금으로 Tier 보정
                    if tick_price > 0 and tracker.tick_count == 0:
                        try:
                            # [v10.1 Fix] FID 14(누적거래대금): 키움 API 기본 단위는 '원'
                            # 단, 일부 환경에서 만원 단위로 오는 경우가 있으므로
                            # sanity check: 값이 1억 미만이면 만원 단위로 간주하여 ×10,000 보정
                            raw_vol = abs(safe_int(self.kiwoom.dynamicCall(
                                "GetCommRealData(QString, int)", code, 14)))
                            if 0 < raw_vol < 100_000_000:
                                cum_vol_krw = raw_vol * 10_000  # 만원 단위 → 원
                            else:
                                cum_vol_krw = raw_vol  # 원 단위 그대로
                            if cum_vol_krw > 0:
                                new_tier = self.tick_monitor._adjust_tier_by_volume(
                                    code, tracker.tier, cum_vol_krw)
                                if new_tier != tracker.tier:
                                    old_tier = tracker.tier
                                    tracker.tier = new_tier
                                    tp = TIER_PARAMS.get(new_tier, TIER_PARAMS[TIER_DEFAULT])
                                    tracker._big_tick_default = tp["big_tick_default"]
                                    self.tick_monitor._log(
                                        f"[SM] 📊 {tracker.name}({code}) "
                                        f"Tier 보정: {old_tier}→{new_tier} "
                                        f"(거래대금={cum_vol_krw/100_000_000:.0f}억)")
                        except Exception:
                            pass

                    if tick_price > 0 and tick_vol > 0:
                        _sm_cached_price = tick_price  # [v10.4/H5] fall-through용 캐싱
                        prev_sig = tracker.signal
                        tracker.on_tick(tick_price, tick_vol, is_buy_tick)
                        new_sig = tracker.signal

                        # [v10.3] 신호 변경 시 로그 기록
                        if new_sig != prev_sig:
                            self.tick_monitor._log(
                                f"[SM] 🔔 {tracker.name}({code}) "
                                f"신호변경 {prev_sig}→{new_sig} "
                                f"(buy_ratio={tracker.signal_strength:.0%}, "
                                f"price={tick_price:,}, ticks={tracker.tick_count})"
                            )
                            try:
                                self.db.log_condition_signal(
                                    code, tracker.name, tracker.cond_name,
                                    f"SM:{new_sig}",
                                    f"ratio={tracker.signal_strength:.0%} "
                                    f"prev={prev_sig} price={tick_price:,}"
                                )
                            except Exception:
                                pass

                        # ── [v10.3] should_buy(): BUY 신호 시 매수 ──
                        if tracker.signal == "BUY" and code not in self.portfolio:
                            self._handle_smartmoney_buy(code, tracker, tick_price)

                        # [v10.3] DANGER 매도 폐기 — 가격 기반 매도만 사용

                except Exception as e:
                    logger.error(f"❌ [SM] {code} 틱 처리 오류: {e}")

            elif real_type == "주식호가잔량":
                try:
                    ask1 = abs(safe_int(self.kiwoom.dynamicCall("GetCommRealData(QString, int)", code, 61)))
                    ask2 = abs(safe_int(self.kiwoom.dynamicCall("GetCommRealData(QString, int)", code, 62)))
                    ask3 = abs(safe_int(self.kiwoom.dynamicCall("GetCommRealData(QString, int)", code, 63)))
                    bid1 = abs(safe_int(self.kiwoom.dynamicCall("GetCommRealData(QString, int)", code, 71)))
                    bid2 = abs(safe_int(self.kiwoom.dynamicCall("GetCommRealData(QString, int)", code, 72)))
                    bid3 = abs(safe_int(self.kiwoom.dynamicCall("GetCommRealData(QString, int)", code, 73)))
                    tracker.on_orderbook(ask1, ask2, ask3, bid1, bid2, bid3)
                except Exception as e:
                    logger.error(f"❌ [SM] {code} 호가 처리 오류: {e}")

            # SmartMoney 추적 중인 종목은 여기서 처리 완료 (portfolio에 있으면 fall-through)
            if code not in self.portfolio:
                return

        if code in self._pending_buy and real_type == "주식체결":
            curr_p = abs(safe_int(self.kiwoom.dynamicCall("GetCommRealData(QString, int)", code, 10)))
            if curr_p <= 0:
                logger.warning(f"🚫 [매수] {code} 스킵: 현재가 0원 수신 (데이터 이상)")
                return

            info = self._pending_buy.pop(code)
            stock_name = self.kiwoom.dynamicCall("GetMasterCodeName(QString)", code)
            cfg = self.config_mgr.config

            # [Fix v9.1] invest_type에 따라 투자금 계산 방식 분리
            # orderable_amount는 _sync_routine에서 이미 locked_deposit 차감 반영됨
            available = max(0, self.orderable_amount if self.orderable_amount > 0 else self.deposit)
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
                    c_name     = info.get('cond_name', '')  # [Fix] c_name 미정의 버그 수정
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
            # [v10.4/H5] SM 추적 중 이미 파싱한 가격이 있으면 재사용 (API 이중 호출 방지)
            curr_p = _sm_cached_price if _sm_cached_price > 0 else abs(safe_int(self.kiwoom.dynamicCall("GetCommRealData(QString, int)", code, 10)))
            self.portfolio[code]['current_price'] = curr_p
            self.portfolio[code]['last_price_ts'] = time.time()
            data = self.portfolio[code]

            if data['buy_price'] == 0 or data['qty'] <= 0 or data['status'] != 'HOLDING' or data.get('sell_ordered'):
                # [v7.5] 분할매수 확인 (HOLDING 상태 + buy_price 확정 후)
                try:
                    if data.get('split_buy') and data['buy_price'] > 0 and data['status'] == 'HOLDING':
                        self._check_split_buy(code, curr_p)
                except Exception as e:
                    logger.error(f"❌ [분할매수] {code} 오류: {e}")
                return

            # [Fix] is_manual 종목: 손절/TS는 항상 작동, 익절은 manual_manage_all 설정에 따라
            manage_manual = self.config_mgr.get("manual_manage_all", False)
            is_manual_only = data.get('is_manual') and not manage_manual
            if curr_p > data['high_price']:
                data['high_price'] = curr_p

            # [v7.5] 분할매수 확인
            try:
                if data.get('split_buy'):
                    self._check_split_buy(code, curr_p)
            except Exception as e:
                logger.error(f"❌ [분할매수] {code} 오류: {e}")

            # [Fix v8.2] 수수료/세금 포함 순수익률 기준으로 모든 매도 판정 통일
            qty = data['qty']
            yield_rate = self._net_yield(data['buy_price'], curr_p, qty)
            high_yield = self._net_yield(data['buy_price'], data['high_price'], qty)
            c_name = data.get('cond_name', '')

            ts_act = self.config_mgr.get_condition_param(c_name, "ts_activation") or 4.0
            ts_drop = self.config_mgr.get_condition_param(c_name, "ts_drop") or 0.75

            # [v10.3] Gate 0 (DANGER 매도) 폐기 — 가격 기반 매도(손절/익절/TS/타임컷)만 사용

            # [v10.3] ═══ Gate 3: 타임컷 — 진입 후 N초 경과 시 매도 ═══
            # SM 매수 종목에만 적용 (종가배팅 등 비SM 종목은 해당 없음)
            # [v10.3] score 기반 연장 폐기 — 고정 180초 타임컷
            if not data.get('is_manual') and data.get('_smartmoney_buy'):
                entry_ts = data.get('_smartmoney_entry_ts') or 0
                if entry_ts > 0:
                    elapsed = time.time() - entry_ts
                    base_timeout = 180  # 타임컷 (초)

                    if elapsed > base_timeout:
                        sellable = data['qty'] - self._pending_sell_qty.get(code, 0)
                        if sellable > 0 and not data.get('sell_ordered'):
                            reason = f"⏰ 타임컷 ({base_timeout}초)"
                            data['sell_ordered'] = True
                            data['_last_sell_reason'] = reason
                            logger.info(
                                f"⏰ [타임컷] {data.get('name', code)}({code}) "
                                f"{elapsed:.0f}초 경과 → {reason}"
                            )
                            self._execute_sell(code, reason, sellable)
                            return

            # [v7.7] 분할매도 처리 — TS 연계형
            # [Fix v8.1] 가동 중 split_sell_enabled를 끈 경우, 기존 포트에 남아있는
            # split_sell dict를 무시하고 전량매도 로직으로 fall-through합니다.
            ss = data.get('split_sell')
            split_sell_active = ss and bool(self.config_mgr.get("split_sell_enabled", False))
            if split_sell_active:
                try:
                    loss_pct   = self.config_mgr.get_condition_param(c_name, "loss") or -1.7
                    profit_pct = ss.get('profit_pct') or (self.config_mgr.get_condition_param(c_name, "profit") or 2.3)
                    offset     = ss.get('offset', 1.5)
                    ratio1     = ss.get('ratio1', 50)
                    t1_done    = ss.get('t1_done', False)
                    t2_done    = ss.get('t2_done', False)
                    pending    = self._pending_sell_qty.get(code, 0)
                    ts_use     = self.config_mgr.get_condition_param(c_name, "ts_use")

                    # ① 손절: 전량
                    if yield_rate <= loss_pct:
                        sellable = data['qty'] - pending
                        if sellable > 0:
                            # [v10.2/M4] 분할매수 미체결 취소 (유령 포지션 방지)
                            self._cancel_unfilled_buy_orders(code)
                            data['sell_ordered'] = True
                            data['_last_sell_reason'] = "🛑 손절"
                            self._execute_sell(code, "🛑 손절", sellable)
                        return

                    # ② 1차: 익절% 도달 → ratio1% 매도 (is_manual 종목은 manual_manage_all 켜야 작동)
                    if not t1_done and yield_rate >= profit_pct and not is_manual_only:
                        # [Fix v8.2] 분할매수 미완료 시 actual qty 기준으로 매도 수량 계산
                        # initial_qty는 분할매수 '계획' 총수량이므로, 2차 매수 전이면
                        # data['qty']가 initial_qty보다 작을 수 있음 → 실제 보유량 기준 사용
                        base_qty = min(ss.get('initial_qty') or data['qty'], data['qty'])
                        sq = max(1, int(base_qty * ratio1 / 100))
                        sq = min(sq, data['qty'] - pending)
                        if sq > 0:
                            ss['t1_done'] = True
                            data['sell_ordered'] = True   # [Fix Bug1] 1차 주문 중 중복 발행 방지
                            reason = f"🎯 분할1차 ({ratio1}% @ +{profit_pct:.1f}%)"
                            data['_last_sell_reason'] = reason
                            self._execute_sell(code, reason, sq)
                        return

                    # ③ 잔여 처리: 1차 체결 완료 후 (sell_ordered는 _on_chejan에서 False로 복구됨)
                    if t1_done and not t2_done:
                        sellable = data['qty'] - pending
                        if sellable <= 0:
                            return

                        # [Fix Bug2] ts_use는 명시적으로 bool 변환 (0/False/None 구분)
                        ts_use = bool(self.config_mgr.get_condition_param(c_name, "ts_use"))

                        if ts_use:
                            # TS ON: ts_act 도달 후 drop% 하락 시 잔여 전량 매도 (그 전까진 대기)
                            if high_yield >= ts_act:
                                if (data['high_price'] - curr_p) / data['high_price'] * 100 >= ts_drop:
                                    ss['t2_done'] = True
                                    data['sell_ordered'] = True
                                    reason = "📉 T.S 발동 (분할잔여)"
                                    data['_last_sell_reason'] = reason
                                    self._execute_sell(code, reason, sellable)
                        else:
                            # TS OFF: 익절%+offset 고정가 폴백 (is_manual 종목은 manual_manage_all 켜야 작동)
                            if yield_rate >= profit_pct + offset and not is_manual_only:
                                ss['t2_done'] = True
                                data['sell_ordered'] = True
                                reason = f"🎯 분할2차 (+{profit_pct + offset:.1f}%)"
                                data['_last_sell_reason'] = reason
                                self._execute_sell(code, reason, sellable)

                except Exception as e:
                    logger.error(f"❌ [분할매도] {code} 오류: {e}")
                return

            # 기존 전량매도 로직 (분할매도 비활성 시)
            # [Fix v8.1] 매도 판정 우선순위: ① 손절 → ② TS 발동 → ③ 익절
            # 기존 if/elif 체인에서 TS 조건(high_yield>=ts_act)이 True이면
            # drop 미충족 시에도 elif 익절에 도달 못 하는 버그 수정.
            reason = ""
            loss_pct = self.config_mgr.get_condition_param(c_name, "loss") or -1.7
            profit_pct = self.config_mgr.get_condition_param(c_name, "profit") or 2.3
            ts_use_normal = bool(self.config_mgr.get_condition_param(c_name, "ts_use"))

            # ① 손절: 최우선 (TS/익절보다 항상 먼저 판정)
            if yield_rate <= loss_pct:
                reason = "🛑 손절"
            # ② TS: 활성 + 고점수익률이 ts_act 이상 + 고점 대비 drop% 하락
            elif ts_use_normal and high_yield >= ts_act:
                drop_from_high = (data['high_price'] - curr_p) / data['high_price'] * 100 if data['high_price'] > 0 else 0
                if drop_from_high >= ts_drop:
                    reason = "📉 T.S 발동"
                # TS 활성 상태이지만 drop 미충족 → 매도 보류 (익절 라인 무시, TS가 보호)
            # ③ 익절: TS 비활성일 때만 작동 (TS ON이면 ②에서 이미 판정)
            elif not ts_use_normal and yield_rate >= profit_pct and not is_manual_only:
                reason = "🎯 익절"

            if reason:
                sellable = data['qty'] - self._pending_sell_qty.get(code, 0)
                if sellable > 0:
                    data['sell_ordered'] = True
                    data['_last_sell_reason'] = reason
                    # [v10.1/C1] 미체결 매수 먼저 취소
                    self._cancel_unfilled_buy_orders(code)
                    self._execute_sell(code, reason, sellable)

    # ── [v10.1/C1] 미체결 매수 주문 취소 ─────────────────────
    def _cancel_unfilled_buy_orders(self, code: str):
        """
        해당 종목의 미체결 매수 주문을 모두 취소.
        매도 주문 전에 반드시 호출하여 유령 포지션 방지.
        """
        for order_no, info in list(self.unexecuted_orders.items()):
            if info.get('code') == code and '+매수' in info.get('type', '') and info.get('qty', 0) > 0:
                try:
                    self.tr_scheduler.request_order(
                        rqname="매수취소", screen_no=self._next_tr_screen(),
                        acc_no=self.account, order_type=3,
                        code=code, qty=info['qty'], price=0,
                        hoga_gb="00", org_order_no=order_no  # [v10.1 Fix] 취소 시 "00" 명시
                    )
                    logger.info(f"🚫 [C1] {code} 미체결 매수 취소 발행 (주문번호={order_no}, 잔량={info['qty']}주)")
                except Exception as e:
                    logger.error(f"❌ [C1] {code} 매수취소 실패: {e}")

    # ── [v10.0] SmartMoney 매수 신호 처리 ──────────────────
    def _handle_smartmoney_buy(self, code: str, tracker, curr_price: int):
        """
        [v10.3] SmartMoneyTracker에서 BUY 신호 발생 시 매수 실행.

        2중 자물쇠:
          1. 미보유 AND 최대보유 미초과? → 여기서 확인
          2. signal이 BUY? → 호출 전에 확인됨

        BUY: 풀 비중(100%) 진입 (BUY_B 폐기)
        """
        name = tracker.name
        cond_name = tracker.cond_name
        screen_no = tracker.screen_no
        sig = tracker.signal
        cfg = self.config_mgr.config

        # ── 자물쇠 2: 기본 필터 ──
        if not self.is_trading or not self.calendar.is_trading_allowed():
            self.tick_monitor._log(f"[SM] 🚫 {name}({code}) 매수 스킵: 매매시간 외")
            return
        # [v10.2/C4] 잔고 동기화 미완료 시 매수 차단
        if not self._portfolio_synced:
            self.tick_monitor._log(f"[SM] 🚫 {name}({code}) 매수 스킵: 잔고 동기화 미완료 (C4)")
            return
        if code in self.portfolio:
            return  # 이미 보유 중
        # [v10.2/H1] 블랙리스트 체크 — watch 후 BL에 추가된 경우 매수 방지
        if code in self.blacklist and self.config_mgr.get("blacklist_enabled", True):
            self.tick_monitor._log(f"[SM] 🚫 {name}({code}) 매수 스킵: 블랙리스트")
            return
        if self._check_loss_limit():
            self.tick_monitor._log(f"[SM] 🚫 {name}({code}) 매수 스킵: 일일 손실한도 초과")
            return

        # [v10.1/C2] 매수 시점 지수필터 재검사
        if not self._is_index_ok():
            self.tick_monitor._log(f"[SM] 🚫 {name}({code}) 매수 스킵: 지수필터 차단 (매수 시점 재검사)")
            return

        # [v10.1/H4] 장 시작 지수 워밍업
        if self._market_open_ts > 0 and (time.time() - self._market_open_ts) < INDEX_WARMUP_SEC:
            self.tick_monitor._log(f"[SM] 🚫 {name}({code}) 매수 스킵: 장 시작 워밍업 ({INDEX_WARMUP_SEC:.0f}초)")
            return

        holding_count = len([c for c, d in list(self.portfolio.items()) if d['qty'] > 0])
        max_hold = cfg.get("max_hold", 5)
        if holding_count >= max_hold:
            self.tick_monitor._log(f"[SM] 🚫 {name}({code}) 매수 스킵: 보유한도 {holding_count}/{max_hold}")
            self.tick_monitor.unwatch(code, "보유한도 초과")
            try:
                self.kiwoom.dynamicCall("SetRealRemove(QString, QString)", screen_no or "ALL", code)
            except Exception:
                pass
            return

        if curr_price <= 0:
            self.tick_monitor._log(f"[SM] 🚫 {name}({code}) 매수 스킵: 현재가 0원")
            return

        # ── 투자금 계산 ──
        available = max(0, self.orderable_amount if self.orderable_amount > 0 else self.deposit)
        invest_type = cfg.get("invest_type", "비중(%)")
        invest_val = cfg.get("invest", 20)

        if invest_type == "비중(%)":
            inv_amt = available * invest_val / 100.0
        else:
            inv_amt = min(invest_val, available)

        total_qty = int(inv_amt // curr_price)
        if total_qty <= 0:
            reason = f"예수금 부족 (가용={available:,}, 현재가={curr_price:,})"
            self.tick_monitor._log(f"[SM] 🚫 {name}({code}) 매수 스킵: {reason}")
            return

        # ── [v10.3] 신호 확인 — BUY만 매수 ──
        if sig != "BUY":
            return

        qty = max(1, total_qty)
        signal_label = "🟢 BUY (매수비율+대량매수)"

        # ── 포트폴리오 등록 + 주문 발행 ──
        self.locked_deposit += curr_price * qty
        port_entry = {
            'name': name, 'buy_price': 0, 'current_price': curr_price, 'high_price': curr_price,
            'qty': 0, 'status': 'BUY_REQ', 'sell_ordered': False, 'screen_no': screen_no,
            'locked_amount': curr_price * qty, 'is_manual': False, 'cond_name': cond_name,
            'last_price_ts': time.time(),
            '_smartmoney_buy': True,
            '_smartmoney_entry_ts': time.time(),
        }

        # 분할매도 초기화 (기존 로직과 동일)
        try:
            if cfg.get("split_sell_enabled"):
                ratio1 = cfg.get("split_sell_ratio1", 50)
                offset = cfg.get("split_sell_offset", 1.5)
                profit_pct = self.config_mgr.get_condition_param(cond_name, "profit") or 2.3
                port_entry['split_sell'] = {
                    "initial_qty": total_qty,
                    "ratio1": ratio1, "offset": offset,
                    "t1_done": False, "t2_done": False,
                    "profit_pct": profit_pct,
                }
        except Exception as e:
            logger.error(f"❌ [SM매수] 분할매도 초기화 오류: {e}")

        self.portfolio[code] = port_entry

        order_screen = self._next_tr_screen()
        self.tr_scheduler.request_order(
            rqname="SM매수", screen_no=order_screen, acc_no=self.account,
            order_type=1, code=code, qty=qty, price=0,
            hoga_gb=cfg.get("order_type", "03"), org_order_no=""
        )
        self._bot_bought_codes.add(code)
        self._save_bot_state()

        order_detail = (
            f"[{signal_label}] {qty}주×{curr_price:,}={curr_price * qty:,}원 "
            f"(buy_ratio={tracker.signal_strength:.0%})"
        )
        logger.info(f"📈 [SM매수] {name}({code}) 주문 발행: {order_detail}")
        self._log_condition_signal(code, name, cond_name, "✅ SM매수", order_detail)
        self.tick_monitor._log(f"[SM] 📈 {name}({code}) {order_detail}")

    # [v10.3] _handle_smartmoney_danger 삭제 — DANGER 매도 폐기

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
            # [Fix v9.1] orderable_amount는 이미 locked 차감 반영
            available = max(0, self.orderable_amount if self.orderable_amount > 0 else self.deposit)
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
        p = self.portfolio[code]
        curr_p   = p.get('current_price', 0)
        buy_p    = p.get('buy_price', 0)
        high_p   = p.get('high_price', 0)
        # [Fix v8.2] 수수료/세금 포함 순수익률로 로그 표시
        pct      = self._net_yield(buy_p, curr_p, qty)
        high_pct = self._net_yield(buy_p, high_p, qty)
        logger.info(
            f"📤 [매도주문] {p.get('name','')}({code}) {reason} | "
            f"{qty}주 | 현재={curr_p:,} ({pct:+.2f}%) | 고점={high_p:,} ({high_pct:+.2f}%)"
        )
        self.tr_scheduler.request_order(
            rqname="실시간매도", screen_no=self._next_tr_screen(), acc_no=self.account,
            order_type=2, code=code, qty=qty, price=0,
            hoga_gb=self.config_mgr.get("order_type", "03"), org_order_no=""
        )
        self._pending_sell_qty[code] = self._pending_sell_qty.get(code, 0) + qty

    # [v10.3] _execute_danger_sell 삭제 — DANGER 매도 폐기

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
            # [v10.4 Fix/C1] 부분체결+잔량취소 시 locked_deposit 정확한 해소
            # 키움 체잔 FID 902(미체결수량)는 '취소 이벤트 시점의 잔여 미체결 수량'입니다.
            # - 전량취소: 902 = 원주문수량 (체결 없이 전부 취소)
            # - 부분체결 후 취소: 902 = 0 (이미 체결 완료된 잔량은 미체결이 아님)
            # 따라서 실제 취소된 수량은:
            #   접수 시 미체결수량(원주문수량) - 누적체결수량 으로 역산합니다.
            # unexec가 0이 아닌 경우는 키움이 '아직 취소 처리 안 된 잔량'을 보내는 것이므로
            # 원주문 정보 기반으로 계산하는 것이 더 안전합니다.
            orig_info = self.unexecuted_orders.get(order_no, {})
            orig_qty = orig_info.get('qty', 0)  # 접수 시 미체결수량 (= 원주문수량)
            cum_filled = self._order_exec_cum.get(order_no, 0)  # 누적 체결수량
            cancelled_qty = max(0, orig_qty - cum_filled)

            if cancelled_qty > 0 and code in self.portfolio:
                # 취소된 잔량의 예상 금액 = 현재가(또는 매수가) × 취소수량
                est_price = self.portfolio[code].get('current_price') or self.portfolio[code].get('buy_price', 0)
                unlock_amt = est_price * cancelled_qty
                self.locked_deposit = max(0, self.locked_deposit - unlock_amt)
                if hasattr(self, '_orderable_from_tr') and self._orderable_from_tr > 0:
                    self.orderable_amount = max(0, self._orderable_from_tr - self.locked_deposit)
                logger.info(
                    f"🔓 [매수취소] {code} 취소 {cancelled_qty}주 "
                    f"(원주문={orig_qty}, 체결={cum_filled}) → "
                    f"locked {unlock_amt:,}원 반환 (잔여 locked={self.locked_deposit:,})"
                )
            elif cancelled_qty == 0 and code in self.portfolio:
                # 전량 체결 후 취소 이벤트 (이미 체결 처리 완료) → locked 조정 불필요
                logger.debug(f"ℹ️ [매수취소] {code} 전량 체결 후 취소 이벤트 수신 (추가 처리 불필요)")
            if code in self.portfolio and self.portfolio[code]['qty'] == 0:
                self.kiwoom.dynamicCall("SetRealRemove(QString, QString)", self.portfolio[code].get('screen_no', "ALL"), code)
                del self.portfolio[code]
            self.unexecuted_orders.pop(order_no, None)
            self._order_exec_cum.pop(order_no, None)

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
                # [Fix v8.2] 평단가 계산: // 정수나눗셈의 절삭 오차 누적 방지 → round 사용
                total_cost = (p['buy_price'] * p['qty']) + (exec_price * exec_qty)
                new_qty = p['qty'] + exec_qty
                p['buy_price'] = round(total_cost / new_qty) if new_qty > 0 else exec_price
                p['qty'] = new_qty
                # [Fix v8.2] high_price: 체결가도 고려 (체결가가 현재 고점보다 높을 수 있음)
                p['high_price'] = max(p['high_price'], p['buy_price'], exec_price)
                cost = exec_price * exec_qty
                self.locked_deposit = max(0, self.locked_deposit - cost)
                # [Fix v9.1] 매수 체결: TR 원본값(_orderable_from_tr)에서 체결금액 차감
                #   _sync_routine에서 orderable = _orderable_from_tr - locked 으로 재계산하므로
                #   orderable_amount를 직접 차감하면 이중 차감됨.
                #   대신 TR 원본값을 차감하여 다음 TR 갱신까지 정합성 유지.
                if hasattr(self, '_orderable_from_tr'):
                    self._orderable_from_tr = max(0, self._orderable_from_tr - cost)
                self.orderable_amount = max(0, self._orderable_from_tr - self.locked_deposit) if hasattr(self, '_orderable_from_tr') and self._orderable_from_tr > 0 else max(0, self.orderable_amount)
                self.deposit_total = max(0, (self.deposit_total if self.deposit_total > 0 else self.deposit) - cost)
                self.deposit = max(0, self.deposit - cost)
                self.db.log_trade("매수", p.get('cond_name', ''), p['name'], code, exec_price, exec_qty, 0,
                    commission=int(exec_price * exec_qty * (MOCK_FEE_RATE if self.is_mock else COMMISSION_RATE)),
                    tax=0, order_type=self.config_mgr.get("order_type", "03"), is_mock=self.is_mock)
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

                # [v10.0] SmartMoney 매수 체결 시 로그
                if p.get('_smartmoney_buy') and self.tick_monitor.is_watching(code):
                    self.tick_monitor._log(
                        f"[SM] ✅ {p['name']}({code}) 매수 체결 "
                        f"(체결가={exec_price:,}, 수량={exec_qty}주)"
                    )

            elif "-매도" in buy_sell and exec_qty > 0:
                p = self.portfolio[code]
                realized = calc_sell_cost(p['buy_price'], exec_price, exec_qty, self.is_mock)
                self.today_realized_profit += realized

                # [Fix v9.1] 매도 체결 시 예수금 + 주문가능금액 복구
                # _orderable_from_tr도 복구하여 sync에서 재계산 시 정합성 유지
                try:
                    recovered = (p['buy_price'] * exec_qty) + realized
                    self.deposit = max(0, self.deposit + recovered)
                    self.deposit_total = max(0, self.deposit_total + recovered)
                    if hasattr(self, '_orderable_from_tr'):
                        self._orderable_from_tr = max(0, self._orderable_from_tr + recovered)
                    self.orderable_amount = max(0, self._orderable_from_tr - self.locked_deposit) if hasattr(self, '_orderable_from_tr') and self._orderable_from_tr > 0 else max(0, self.orderable_amount + recovered)
                    self.withdrawable_amount = max(0, self.withdrawable_amount + recovered)
                except Exception:
                    pass

                p['qty'] = max(0, p['qty'] - exec_qty)
                self._pending_sell_qty[code] = max(0, self._pending_sell_qty.get(code, 0) - exec_qty)
                buy_commission = int(p['buy_price'] * exec_qty * (MOCK_FEE_RATE if self.is_mock else COMMISSION_RATE))
                sell_commission = int(exec_price * exec_qty * (MOCK_FEE_RATE if self.is_mock else COMMISSION_RATE))
                tax = int(exec_price * exec_qty * (0 if self.is_mock else TAX_RATE))
                self.db.log_trade("매도", p.get('cond_name', ''), p['name'], code, exec_price, exec_qty, realized,
                    commission=buy_commission + sell_commission, tax=tax,
                    order_type=self.config_mgr.get("order_type", "03"), is_mock=self.is_mock,
                    sell_reason=p.get('_last_sell_reason', ''))

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
                    stock_name = p.get('name', code)
                    sell_reason = p.get('_last_sell_reason', '매도완료')
                    is_loss = '손절' in sell_reason

                    # [v10.0] 매도 완료 → SmartMoney 추적 해제
                    # [v10.1/H3] 매도 완료는 쿨다운 면제 (재편입 허용)
                    if self.tick_monitor.is_watching(code) or code in self.tick_monitor._trackers:
                        self.tick_monitor.unwatch(code, f"매도완료({sell_reason})", set_cooldown=False)
                        logger.info(f"🧹 [SM] {stock_name}({code}) 매도 완료 → 추적 해제")

                    # [v9.0] 당일 매매 완료 종목 기록 (모든 모드에서 UI 표시용)
                    self._traded_today[code] = {
                        "name": stock_name,
                        "reason": sell_reason,
                        "is_loss": is_loss,
                    }

                    # [v9.0] 블랙리스트 모드별 자동등록 분기
                    if not p.get('is_manual'):
                        bl_mode = self.config_mgr.get("blacklist_mode", 1)

                        if bl_mode == 1:
                            # 모드1: 손절 종목만 자동 등록
                            if is_loss:
                                self.blacklist.add(code)
                                self._bl_cache[code] = stock_name
                                self._bl_tags[code] = "자동(손절)"
                                self.db.log_blacklist("자동추가", code, stock_name, sell_reason)
                                logger.info(f"🚫 [BL모드1] {stock_name}({code}) 손절 → 자동 블랙리스트")

                        elif bl_mode == 2:
                            # 모드2: 전체 자동 등록 (수동 해제된 종목은 재등록 안 함)
                            if code not in self._bl_manual_released:
                                self.blacklist.add(code)
                                self._bl_cache[code] = stock_name
                                self._bl_tags[code] = "자동"
                                self.db.log_blacklist("자동추가", code, stock_name, sell_reason)
                                logger.info(f"🚫 [BL모드2] {stock_name}({code}) → 자동 블랙리스트")

                        # 모드3: 자동 등록 없음 (수동으로만)

                    self.kiwoom.dynamicCall("SetRealRemove(QString, QString)", p.get('screen_no', "ALL"), code)
                    del self.portfolio[code]
                    self._bot_bought_codes.discard(code)
                    self._save_bot_state()
                else:
                    # [Fix Bug1] 분할매도 1차 체결 후 잔여 포지션 감시 재개
                    # sell_ordered=True가 남아있으면 1293라인 early-return에 막혀
                    # 2차 TS/분할2차 로직이 영원히 실행되지 않는 버그 수정
                    p['status'] = 'HOLDING'
                    p['sell_ordered'] = False

        if unexec == 0 and order_no in self.unexecuted_orders:
            del self.unexecuted_orders[order_no]
            # [v10.3 Fix] 주문 완료 시 누적 체결량 추적 딕셔너리도 정리 (메모리 누수 방지)
            self._order_exec_cum.pop(order_no, None)

    def _check_unexecuted_orders(self):
        curr = time.time()
        for o_no, info in list(self.unexecuted_orders.items()):
            if curr - info['time'] > 60:
                o_type = 3 if "+매수" in info['type'] else 4
                self.tr_scheduler.request_order(
                    "미체결취소", self._next_tr_screen(), self.account,
                    o_type, info['code'], info['qty'], 0, "00", o_no  # [v10.2/M3] 취소 주문은 "00" 통일
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
