"""
K-Trader Master v7.0 - 스마트 마켓 캘린더
[개선 #1] 공공데이터포털 API 연동으로 휴장일 자동 업데이트
[개선 #2] 로컬 캐싱(holidays.json) 및 UI 연동 메서드 복구
[개선 #3] 누락 메서드 추가 (is_trading_allowed, is_eod_timecut, is_eod_shutdown)
"""
import datetime
import logging
import json
import os
import requests
import xml.etree.ElementTree as ET

logger = logging.getLogger("ktrader")


class MarketCalendar:
    def __init__(self, api_key: str = None, cache_path: str = "config/holidays.json"):
        self.api_key = api_key
        self.cache_path = cache_path
        self.holidays = set()
        self.delayed_days = set()

        self._load_cache()

        curr_year = datetime.date.today().year
        if not any(d.year == curr_year for d in self.holidays):
            logger.info(f"📅 [캘린더] {curr_year}년 휴장일 데이터를 API에서 조회합니다.")
            self.update_holidays_from_api(curr_year)

        if not self.holidays:
            self._set_default_holidays(curr_year)

    # [Fix #7] 2025~2030년 음력 명절 양력 변환 하드코딩 테이블.
    # 음력은 해마다 날짜가 달라 자동 계산이 어려우므로 테이블 방식 사용.
    # 설날 연휴 3일(전날·당일·다음날), 추석 연휴 3일 포함.
    _LUNAR_HOLIDAYS = {
        2025: [(1,  28), (1,  29), (1,  30),           # 설날 연휴
               (10,  5), (10,  6), (10,  7)],           # 추석 연휴
        2026: [(2,  16), (2,  17), (2,  18),            # 설날 연휴
               (9,  24), (9,  25), (9,  26)],           # 추석 연휴
        2027: [(2,   5), (2,   6), (2,   7),            # 설날 연휴
               (9,  14), (9,  15), (9,  16)],           # 추석 연휴
        2028: [(1,  25), (1,  26), (1,  27),            # 설날 연휴
               (10,  2), (10,  3), (10,  4)],           # 추석 연휴
        2029: [(2,  12), (2,  13), (2,  14),            # 설날 연휴
               (9,  21), (9,  22), (9,  23)],           # 추석 연휴
        2030: [(2,   2), (2,   3), (2,   4),            # 설날 연휴
               (9,  11), (9,  12), (9,  13)],           # 추석 연휴
    }

    def _set_default_holidays(self, year: int):
        defaults = [
            (1, 1), (3, 1), (5, 5), (6, 6), (8, 15), (10, 3), (10, 9), (12, 25)
        ]
        for m, d in defaults:
            self.holidays.add(datetime.date(year, m, d))
        self.holidays.add(datetime.date(year, 12, 31))

        # [Fix #7] 음력 명절(설날·추석 연휴) 추가 — API 키 없을 때도 적용
        for m, d in self._LUNAR_HOLIDAYS.get(year, []):
            self.holidays.add(datetime.date(year, m, d))
        if self._LUNAR_HOLIDAYS.get(year):
            logger.info(f"📅 [캘린더] {year}년 음력 명절 {len(self._LUNAR_HOLIDAYS[year])}일 기본 목록에 추가됨")
        else:
            logger.warning(f"⚠️ [캘린더] {year}년 음력 명절 테이블 미등록 — API 키로 갱신 권장")

    def _load_cache(self):
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.holidays.update({datetime.datetime.strptime(d, "%Y-%m-%d").date() for d in data})
                logger.info(f"✅ [캘린더] 캐시 로드 완료 ({len(self.holidays)}일)")
            except Exception as e:
                logger.error(f"❌ [캘린더] 캐시 로드 실패: {e}")

    def _save_cache(self):
        try:
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as f:
                sorted_dates = sorted([d.strftime("%Y-%m-%d") for d in self.holidays])
                json.dump(sorted_dates, f, indent=2)
        except Exception as e:
            logger.error(f"❌ [캘린더] 캐시 저장 실패: {e}")

    def update_holidays_from_api(self, year: int):
        if not self.api_key:
            logger.debug("ℹ️ [캘린더] API Key가 없어 내장 공휴일 목록을 사용합니다.")
            return

        url = "http://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getRestDeInfo"
        new_found = False

        try:
            for month in range(1, 13):
                params = {
                    'serviceKey': self.api_key,
                    'solYear': str(year),
                    'solMonth': f"{month:02d}"
                }
                resp = requests.get(url, params=params, timeout=10)
                if resp.status_code == 200:
                    root = ET.fromstring(resp.text)
                    for item in root.findall(".//item"):
                        # [Fix #7] find() 결과 None이면 AttributeError 방지
                        holiday_tag = item.find("isHoliday")
                        locdate_tag = item.find("locdate")
                        if holiday_tag is None or locdate_tag is None:
                            continue
                        if holiday_tag.text == "Y":
                            locdate = locdate_tag.text
                            dt = datetime.datetime.strptime(locdate, "%Y%m%d").date()
                            self.holidays.add(dt)
                            new_found = True

            last_day = datetime.date(year, 12, 31)
            while last_day.weekday() >= 5 or last_day in self.holidays:
                last_day -= datetime.timedelta(days=1)
            self.holidays.add(last_day)

            if new_found:
                self._save_cache()
                logger.info(f"🚀 [캘린더] {year}년 휴장일 업데이트 성공!")
        except Exception as e:
            logger.error(f"❌ [캘린더] API 업데이트 중 오류: {e}")

    def is_market_day(self, dt: datetime.date = None) -> bool:
        dt = dt or datetime.date.today()
        if dt.weekday() >= 5:
            return False
        return dt not in self.holidays

    def get_market_phase(self, now: datetime.datetime = None) -> str:
        now = now or datetime.datetime.now()

        if not self.is_market_day(now.date()):
            return "CLOSED"

        curr_time = now.time()
        is_delayed = now.date() in self.delayed_days
        start_h = 10 if is_delayed else 9
        end_h = 16 if is_delayed else 15

        if datetime.time(8, 0) <= curr_time < datetime.time(start_h, 0):
            return "PRE_MARKET"
        if datetime.time(start_h, 0) <= curr_time < datetime.time(end_h, 20):
            return "REGULAR"
        if datetime.time(end_h, 20) <= curr_time < datetime.time(end_h, 30):
            return "CLOSING_AUCTION"
        if datetime.time(end_h, 30) <= curr_time < datetime.time(end_h + 1, 0):
            return "POST_MARKET"

        return "CLOSED"

    def status_text(self, now: datetime.datetime = None) -> str:
        now = now or datetime.datetime.now()
        phase = self.get_market_phase(now)

        is_delayed = now.date() in self.delayed_days
        delay_msg = " (1시간 지연)" if is_delayed else ""

        labels = {
            "CLOSED": "🔴 휴장일/장 종료",
            "PRE_MARKET": f"🟡 장 시작 전{delay_msg}",
            "REGULAR": f"🟢 장 운영 중{delay_msg}",
            "CLOSING_AUCTION": "🟠 장 마감 동시호가",
            "POST_MARKET": "🔵 장후 시간외/정산"
        }
        return labels.get(phase, "⚪ 상태 확인 불가")

    def is_pre_market_open(self, now: datetime.datetime = None) -> bool:
        now = now or datetime.datetime.now()
        if not self.is_market_day(now.date()):
            return False
        return now.hour == 8 and now.minute >= 30

    def is_regular_market(self, now: datetime.datetime = None) -> bool:
        return self.get_market_phase(now) == "REGULAR"

    # ══════════════════════════════════════════════════════════
    #  [개선 #3] 엔진/UI에서 호출하는 누락 메서드 추가
    # ══════════════════════════════════════════════════════════

    def is_trading_allowed(self, now=None) -> bool:
        """
        매매 허용 시간인지 판단.
        정규장(09:00~15:20) 동안만 신규 진입을 허용합니다.
        동시호가(15:20~15:30) 이후에는 신규 진입 불가.
        datetime.datetime 또는 datetime.date 모두 허용.
        """
        now = now or datetime.datetime.now()
        # [검수 Fix] datetime.date가 전달되면 datetime.datetime으로 변환
        if isinstance(now, datetime.date) and not isinstance(now, datetime.datetime):
            now = datetime.datetime(now.year, now.month, now.day)
        if not self.is_market_day(now.date()):
            return False

        curr_time = now.time()
        is_delayed = now.date() in self.delayed_days
        start_h = 10 if is_delayed else 9
        end_h = 16 if is_delayed else 15

        # 정규장 시간 내에서만 매매 허용 (15:15까지 — 타임컷 5분 전 여유)
        return datetime.time(start_h, 0) <= curr_time < datetime.time(end_h, 15)

    def is_eod_timecut(self, now=None) -> bool:
        """
        타임컷(일괄 청산) 시점인지 판단.
        기본: 15:15 (지연일: 16:15)
        """
        now = now or datetime.datetime.now()
        if isinstance(now, datetime.date) and not isinstance(now, datetime.datetime):
            now = datetime.datetime(now.year, now.month, now.day)
        if not self.is_market_day(now.date()):
            return False

        is_delayed = now.date() in self.delayed_days
        cut_h = 16 if is_delayed else 15
        cut_m = 15

        return now.hour == cut_h and cut_m <= now.minute < cut_m + 5

    def is_eod_shutdown(self, now=None) -> bool:
        """
        장 마감 후 엔진 종료 시점인지 판단.
        기본: 15:40 (지연일: 16:40) — 장후 시간외 처리가 완료될 충분한 여유 확보
        """
        now = now or datetime.datetime.now()
        if isinstance(now, datetime.date) and not isinstance(now, datetime.datetime):
            now = datetime.datetime(now.year, now.month, now.day)
        if not self.is_market_day(now.date()):
            return False

        is_delayed = now.date() in self.delayed_days
        shutdown_h = 16 if is_delayed else 15
        shutdown_m = 40

        return now.hour == shutdown_h and now.minute >= shutdown_m