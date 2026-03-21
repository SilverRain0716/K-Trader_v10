"""
K-Trader Master - 유틸리티 모듈
[개선] 모의투자/실계좌 수수료 동적 스위칭 로직 추가
"""
import datetime
import logging

__version__ = "10.5.0"

logger = logging.getLogger("ktrader")


def safe_int(val, default=0):
    """
    안전한 정수 변환. 
    키움 API 반환값의 쉼표/공백/플러스 기호 처리 및 소수점 문자열("10.0") 방어.
    """
    try:
        if isinstance(val, str):
            val = val.replace(',', '').replace('+', '').replace(' ', '').strip()
            if not val or val == '-':
                return default
            # "10.0" 같은 소수점 포함 문자열의 ValueError 방지를 위해 float을 거쳐 int로 변환
            return int(float(val))
        return int(val)
    except (ValueError, TypeError) as e:
        logger.debug(f"safe_int 변환 실패: {val!r} → default={default} ({e})")
        return default


def safe_float(val, default=0.0):
    """
    안전한 실수 변환.
    키움 API의 퍼센트(%) 기호 및 플러스(+) 기호 예외 처리 추가.
    NaN/Inf 결과도 default로 대체하여 손익 계산 오염 방지. [검수Fix]
    """
    import math
    try:
        if isinstance(val, str):
            val = val.replace(',', '').replace('+', '').replace('%', '').replace(' ', '').strip()
            if not val or val == '-':
                return default
        result = float(val)
        # NaN 또는 무한대는 계산식을 오염시키므로 default로 대체
        if math.isnan(result) or math.isinf(result):
            return default
        return result
    except (ValueError, TypeError) as e:
        logger.debug(f"safe_float 변환 실패: {val!r} → default={default} ({e})")
        return default


def format_krw(amount):
    """금액을 한국 원화 형식으로 포맷 (0원 표기 개선)."""
    if amount > 0:
        return f"+{amount:,}원"
    elif amount < 0:
        return f"{amount:,}원"
    return "0원"


def format_yield(rate):
    """수익률을 포맷."""
    if rate == 0:
        return "0.00%"
    return f"{rate:+.2f}%"


def now_str(fmt="%Y-%m-%d %H:%M:%S"):
    """현재 시간 문자열."""
    return datetime.datetime.now().strftime(fmt)


def today_str(fmt="%Y-%m-%d"):
    """오늘 날짜 문자열."""
    return datetime.datetime.now().strftime(fmt)


# ── 앱 데이터 디렉토리 허브 (엔진/UI/웹모니터 공용) ────────────
def get_app_dir() -> str:
    """
    K-Trader 쓰기 가능 앱 데이터 루트 디렉토리.
      Windows : %LOCALAPPDATA%\\K-Trader
      Linux/Mac: ~/.k-trader
    환경변수 KTRADER_APP_DIR 으로 경로 오버라이드 가능 (VPS/테스트 환경 대응).
    """
    import os
    import sys
    env_dir = os.environ.get("KTRADER_APP_DIR", "").strip()
    if env_dir:
        return env_dir
    if sys.platform == "win32":
        localappdata = os.environ.get(
            "LOCALAPPDATA",
            os.path.join(os.path.expanduser("~"), "AppData", "Local"),
        )
        return os.path.join(localappdata, "K-Trader")
    return os.path.join(os.path.expanduser("~"), ".k-trader")


def get_user_data_dir() -> str:
    """버전/폴더가 달라도 유지되는 사용자 데이터 디렉토리."""
    import os
    env_dir = os.environ.get("KTRADER_DATA_DIR", "").strip()
    if env_dir:
        return env_dir
    return os.path.join(get_app_dir(), "data")


def resolve_db_path(base_dir: str = "") -> str:
    """
    DB 경로 결정. 구버전 경로에서 자동 마이그레이션.
    마이그레이션 우선순위:
      1) ~/KTraderMaster/data/   (v7.4 이하 사용자 경로)
      2) base_dir/data/          (개발 환경 / 구형 설치 경로)
    """
    import os
    import shutil
    user_data_dir = get_user_data_dir()
    os.makedirs(user_data_dir, exist_ok=True)
    target = os.path.join(user_data_dir, "ktrader_history.db")
    if not os.path.exists(target):
        legacy_candidates = [
            os.path.join(os.path.expanduser("~"), "KTraderMaster", "data", "ktrader_history.db"),
        ]
        if base_dir:
            legacy_candidates.append(os.path.join(base_dir, "data", "ktrader_history.db"))
        for legacy in legacy_candidates:
            try:
                if os.path.exists(legacy):
                    shutil.copy2(legacy, target)
                    logger.info(f"✅ [DB] 마이그레이션: {legacy} → {target}")
                    break
            except Exception as e:
                logger.warning(f"⚠️ [DB] 마이그레이션 실패(계속 진행): {e}")
    return target


# 세금/수수료 설정 (2026년 기준, bot_config.json에서 오버라이드 가능)
COMMISSION_RATE = 0.00015   # 키움증권 실계좌 온라인 매매 수수료 (0.015%)
TAX_RATE = 0.0020           # 실계좌 거래세 (매도 시 0.20%) [권고#7 주석 수정: 0.18% → 0.20%]
MOCK_FEE_RATE = 0.0035      # 모의투자 통합 가상 수수료 (통상 0.35%)


def calc_sell_cost(buy_price, sell_price, qty, is_mock=False,
                   commission_rate=None, tax_rate=None, mock_fee_rate=None):
    """
    매도 시 실현손익 계산.
    [개선] is_mock 파라미터를 추가하여 모의투자와 실계좌의 수수료 차이를 반영합니다.
    commission_rate/tax_rate/mock_fee_rate: 외부에서 오버라이드 가능 (None이면 기본값 사용)
    """
    gross = (sell_price - buy_price) * qty
    
    if is_mock:
        rate = mock_fee_rate if mock_fee_rate is not None else MOCK_FEE_RATE
        total_fee = int(sell_price * qty * rate)
        net = gross - total_fee
    else:
        c_rate = commission_rate if commission_rate is not None else COMMISSION_RATE
        t_rate = tax_rate if tax_rate is not None else TAX_RATE
        buy_commission = int(buy_price * qty * c_rate)
        sell_commission = int(sell_price * qty * c_rate)
        tax = int(sell_price * qty * t_rate)
        net = gross - buy_commission - sell_commission - tax
        
    return int(net)
