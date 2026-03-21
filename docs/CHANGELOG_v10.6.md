# K-Trader v10.6.0 변경 이력

**날짜**: 2026-03-22
**작업**: 코드 리뷰 기반 수정 + 슬리피지 추적 + ML 피처 수집 인프라 구축

---

## 1. 코드 리뷰 수정 (v10.5.1 → v10.6.0)

전체 소스 13개 파일을 검토하여 발견된 결함을 수정했습니다.
Syntax Error 0건, 실행 차단급 결함 0건이었으며, 아래는 수정된 항목입니다.

### High (논리 오류/잠재적 문제)

| ID | 파일 | 내용 |
|----|------|------|
| H1 | engine.py:3149 | `run_engine()` 미사용 변수 `engine` — `# noqa: F841` + GC 방지 목적 주석 명시 |
| H2 | ipc.py:37 | `UI_IPCServer.run()` 모든 Exception에서 break → 소켓 오류만 break, 기타 로깅 후 continue |
| H3 | engine.py:2175 | 지수 실시간 파싱 raw `float()` → `safe_float()` 방어 적용 |
| H5 | engine.py:3064 | `_check_unexecuted_orders()` 매도취소 강제 정리 시 `_pending_sell_qty` 복구 + 상태 HOLDING 복원 추가 |

### Medium (개선 권장)

| ID | 파일 | 내용 |
|----|------|------|
| M1 | 6개 파일 | 미사용 import 정리 (backtest, setup_wizard, ui_dashboard, web_monitor) |
| M2 | ui_dashboard, web_monitor | placeholder 없는 f-string → 일반 문자열로 변경 |

### Low (스타일/가독성)

| ID | 파일 | 내용 |
|----|------|------|
| L2 | engine.py (6곳) | `__init__`에서 초기화된 `_orderable_from_tr`의 불필요한 `hasattr` 체크 전부 제거 |
| L3 | engine.py (8곳) | `__init__`에서 초기화된 `_bl_cache`, `_bl_tags` 등의 불필요한 `getattr` fallback 제거 |

---

## 2. 슬리피지 추적

**목적**: 주문 시점 가격(expected_price)과 실제 체결가(exec_price)의 차이를 기록하여,
주문 유형(시장가 `03` vs 최유리지정가 `06`) 최적화에 활용합니다.

### 변경 사항

**database.py**
- `trade_history` 테이블에 `expected_price` (INTEGER), `slippage_pct` (REAL) 컬럼 추가
- 기존 DB 자동 마이그레이션 (ALTER TABLE)
- `log_trade()` 시그니처에 `expected_price`, `slippage_pct` 매개변수 추가
- `get_slippage_stats(days)` 메서드 추가 — 주문유형별 평균/최대/최소 슬리피지 통계

**engine.py**
- `_on_chejan` 매수 체결 시: `current_price`(주문 시점) vs `exec_price`(체결가) 차이를 자동 계산
- `log_trade()` 호출에 슬리피지 데이터 전달
- 슬리피지 로그 출력 추가

### 계산식

```python
slippage_pct = ((exec_price - expected_price) / expected_price) * 100
# 양수 = 비싸게 체결 (불리), 음수 = 싸게 체결 (유리)
```

### SM 추적과의 충돌: 없음

슬리피지는 `_on_chejan` 체결 이벤트에서 읽기만 하는 로직입니다.
SM 매수 경로(`_handle_smartmoney_buy`)와 일반 매수 경로(`_on_real_data` → `_pending_buy`) 모두
`_on_chejan`의 동일한 매수 체결 분기에서 합류하므로, 한 곳에 추가하면 양쪽 다 커버됩니다.

---

## 3. ML 피처 수집 인프라

**목적**: 매수 시점의 시장 상태/SM 지표를 DB에 축적하여,
향후 오프라인 학습기(2단계)에서 "어떤 조건 조합이 수익으로 이어졌는가"를 학습할 수 있도록 합니다.

### 새 테이블: `trade_features`

```sql
CREATE TABLE trade_features (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id INTEGER,
    date TEXT, time TEXT,
    stock_code TEXT, stock_name TEXT, cond_name TEXT,
    -- SM 신호 지표 (매수 시점 스냅샷)
    buy_ratio REAL,          -- 15초 매수비율
    big_buy_freq REAL,       -- 대량매수 빈도
    relative REAL,           -- 5분 평균 대비 상대값
    tick_count INTEGER,      -- 워밍업 틱 수
    tier TEXT,               -- 종목 무게 (SMALL/MID/LARGE)
    -- 시장 컨텍스트
    kospi_rate REAL,         -- KOSPI 등락률
    kosdaq_rate REAL,        -- KOSDAQ 등락률
    change_rate REAL,        -- 종목 당일 등락률
    hour_minute TEXT,        -- 매수 시각 (HH:MM)
    holding_count INTEGER,   -- 현재 보유 종목 수
    -- 체결 품질
    expected_price INTEGER,  -- 주문 시점 가격
    exec_price INTEGER,      -- 실제 체결가
    slippage_pct REAL,       -- 슬리피지 (%)
    -- 매수 경로
    is_sm_buy INTEGER,       -- SM 매수 여부 (1/0)
    -- 결과 (매도 완료 시 업데이트)
    result_pnl INTEGER,      -- 실현손익 (원)
    result_pct REAL,         -- 수익률 (%)
    result_reason TEXT,      -- 매도 사유
    result_hold_sec REAL     -- 보유 시간 (초)
);
```

### 데이터 흐름

```
매수 주문 시
  ├─ SM 매수: tracker 지표(buy_ratio, big_buy_freq, relative...) + 시장 컨텍스트 → port_entry['_sm_features']
  └─ 일반 매수: 시장 컨텍스트만 → port_entry['_sm_features']
       ↓
매수 체결 시 (_on_chejan)
  └─ _sm_features + exec_price + slippage → db.log_trade_features()
       ↓
매도 완료 시 (_on_chejan, qty <= 0)
  └─ result_pnl, result_pct, result_reason, hold_sec → db.update_trade_result()
```

### 추가된 DB 메서드

| 메서드 | 용도 |
|--------|------|
| `log_trade_features(code, name, cond_name, features)` | 매수 체결 시 피처 저장, row id 반환 |
| `update_trade_result(code, pnl, pct, reason, hold_sec)` | 매도 완료 시 결과 업데이트 |
| `get_trade_features(days, completed_only)` | ML 학습용 데이터 일괄 조회 |

---

## 4. 데이터 축적 → ML 학습 로드맵

### 현재 위치: 1단계 완료

```
[1단계] 피처 수집 인프라 ✅ ← 오늘 완료
   │
   ├── 2~3주 실전 운영으로 데이터 축적
   │
[2단계] 오프라인 학습기
   │  - 장 종료 후 trade_features 데이터로 모델 훈련
   │  - LightGBM 또는 로지스틱 회귀
   │  - "어떤 피처 조합이 수익으로 이어졌는가" 학습
   │  - 백테스트 성격이라 실매매와 완전 분리, 안전
   │
[3단계] 실시간 필터 연동
   │  - 학습된 모델을 엔진에 로드
   │  - _handle_smartmoney_buy에서 매수 직전 신뢰도 체크
   │  - 신뢰도 60% 미만 신호 필터링
   │  - 기존 SM 로직 위에 필터 한 겹 추가 (교체 아님)
   │
[반복] 매일 장 종료 후 모델 갱신 → 다음 날 적용
```

### 2단계 상세 (다음 구현 예정)

**파일**: `src/ml_trainer.py` (신규)

**동작**:
1. `db.get_trade_features(days=90, completed_only=True)` 로 학습 데이터 로드
2. 피처 전처리 (hour_minute → 숫자, tier → one-hot 등)
3. 목표 변수: `result_pnl > 0` (수익 여부, 이진 분류)
4. LightGBM 학습 + 교차 검증
5. 모델 저장: `{app_dir}/data/buy_filter_model.pkl`
6. 피처 중요도 리포트 생성

**실행 방식**:
```bash
python main.py trainer          # 수동 실행
# 또는 장 마감 후 자동 실행 (shutdown_opt 연동)
```

### 3단계 상세 (2단계 검증 후)

**engine.py 변경**: `_handle_smartmoney_buy()`에 3줄 추가

```python
# 모델 로드 (엔진 시작 시 1회)
self._buy_filter = load_model(f"{app_dir}/data/buy_filter_model.pkl")

# 매수 직전 필터 (기존 코드 변경 없음, 추가만)
if self._buy_filter:
    confidence = self._buy_filter.predict_proba(features)
    if confidence < self.config_mgr.get("ml_min_confidence", 0.6):
        self.tick_monitor._log(f"[ML] 🚫 {name}({code}) 신뢰도 {confidence:.0%} < 임계값 → 매수 스킵")
        return
```

---

## 5. 아키텍처 리팩토링 계획 (SaaS 전환 시점)

> 현재는 실전 매매 안정성이 우선이므로, 리팩토링은 SaaS 전환이 결정된 시점에
> 테스트 코드와 함께 진행합니다.

### 현재 문제: God Class

`TradingEngine` 클래스 하나가 3,200줄이며, 최소 8가지 역할이 섞여 있습니다:
- 키움 연결/인증/재연결
- 예수금/주문가능금액 관리
- 포지션 관리 (portfolio, locked_deposit)
- 주문 발행/체결 처리
- 매도 판정 (손절/TS/익절/타임컷)
- 조건식 편입/이탈
- 지수 실시간 수신/필터
- IPC 상태 전송/리포트

### 목표 구조

```
src/
├── engine.py              ← 300줄 (오케스트레이터, 이벤트 라우팅만)
├── connection.py          ← 키움 연결/인증/재연결
├── portfolio_manager.py   ← 포지션 관리, 잔고 동기화, locked_deposit
├── order_executor.py      ← 매수/매도 주문 발행, 체결 처리
├── sell_decision.py       ← 손절/TS/익절/타임컷 판정 로직
├── condition_handler.py   ← 조건식 편입/이탈, SM 연동
├── index_filter.py        ← 지수 실시간 수신/필터
├── deposit_tracker.py     ← 예수금/주문가능금액 관리
├── state_reporter.py      ← IPC 상태 전송, 리포트 생성
├── feature_collector.py   ← 슬리피지/ML 피처 수집
└── event_bus.py           ← 이벤트 기반 모듈 간 통신
```

### 리팩토링 전제조건 (실행하기 전에 반드시)

1. **테스트 코드 먼저 작성** — 현재 동작을 테스트로 고정한 후 분해
2. **SaaS 전환 결정** — 멀티 계좌/멀티 전략이 실제로 필요해진 시점
3. **ML 파이프라인 안정화** — 2~3단계가 검증되어 피처 흐름이 확정된 후

### 효과 (리팩토링 완료 시)

| 관점 | 현재 (God Class) | 분해 후 |
|------|-----------------|--------|
| 버그 수정 | 3,200줄 전체 문맥 파악 필요 | 해당 모듈 300~400줄만 확인 |
| 테스트 | 실전 매매로만 검증 | 단위 테스트로 사전 검증 |
| 기능 추가 | 기존 블록에 끼워넣기 | 새 모듈 + 이벤트 구독 |
| SaaS 전환 | 대규모 재작성 | 인스턴스 분리로 자연 확장 |
| 협업 | 단일 파일 충돌 빈번 | 모듈별 독립 작업 |

### 지금 할 수 있는 소규모 개선 (리팩토링 없이)

리팩토링 전이라도 위험 없이 가독성을 올릴 수 있는 작업들:
- `_on_chejan` 매수/매도 블록 → `_handle_buy_filled()`, `_handle_sell_filled()` 메서드 추출
- `_sync_routine` 내 독립 블록들 → 개별 프라이빗 메서드로 추출
- `_on_real_data` SM/portfolio/pending_buy 분기 → 메서드 추출

이 작업들은 클래스 구조를 바꾸지 않고 메서드만 분리하는 것이라
기존 동작에 영향 없이 진행 가능합니다.
