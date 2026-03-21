"""
K-Trader Master v7.0 - 백테스팅 엔진
[개선 #16] 과거 데이터 기반 전략 파라미터 최적화

사용법:
    python -m src.backtest --data prices.csv --profit 2.0 --loss -1.5

데이터 형식 (CSV):
    datetime, code, name, open, high, low, close, volume
"""
import csv
import logging
import argparse
import datetime
from dataclasses import dataclass
from typing import List, Dict

logger = logging.getLogger("ktrader")


@dataclass
class Bar:
    """하나의 봉(캔들) 데이터."""
    dt: datetime.datetime
    code: str
    name: str
    open: int
    high: int
    low: int
    close: int
    volume: int


@dataclass
class Position:
    """보유 포지션."""
    code: str
    name: str
    buy_price: int
    qty: int
    buy_time: datetime.datetime
    high_price: int = 0
    condition: str = ""

    def __post_init__(self):
        self.high_price = max(self.high_price, self.buy_price)


@dataclass
class TradeResult:
    """하나의 거래 결과."""
    code: str
    name: str
    buy_price: int
    sell_price: int
    qty: int
    buy_time: datetime.datetime
    sell_time: datetime.datetime
    pnl: int = 0
    reason: str = ""


@dataclass
class BacktestConfig:
    """백테스트 파라미터."""
    initial_capital: int = 10_000_000     # 초기 자본
    invest_pct: float = 20.0              # 종목당 투자 비중(%)
    max_hold: int = 5                     # 최대 동시 보유
    profit_target: float = 2.2            # 익절(%)
    loss_target: float = -1.7             # 손절(%)
    ts_use: bool = False                  # 트레일링 스탑 사용
    ts_activation: float = 4.0            # TS 활성화(%)
    ts_drop: float = 0.75                 # TS 하락 발동(%)
    commission_rate: float = 0.00015      # 수수료율
    tax_rate: float = 0.0020              # 거래세 (2025년~)


class Backtester:
    """
    정밀 백테스팅 엔진.
    Lookahead Bias(미래 참조 편향)를 제거하고, 장중 저가(Low)/고가(High)를 
    활용하여 실제 틱 단위 매매와 가장 유사한 환경을 시뮬레이션합니다.
    """

    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        self.capital = self.config.initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[TradeResult] = []
        
        # [수정 #3] 정확한 Equity Curve를 위한 전 종목 최신 가격 트래킹
        self.last_prices: Dict[str, int] = {}
        self.equity_curve: List[tuple] = []  # (datetime, equity)
        self._peak_equity = self.config.initial_capital
        self._max_drawdown = 0

    def _calc_net_profit(self, buy_price: int, sell_price: int, qty: int) -> int:
        """수수료/세금을 반영한 순손익(Net Profit)을 계산합니다 (백테스트용)."""
        gross = (sell_price - buy_price) * qty
        buy_commission = int(buy_price * qty * self.config.commission_rate)
        sell_commission = int(sell_price * qty * self.config.commission_rate)
        tax = int(sell_price * qty * self.config.tax_rate)
        return int(gross - buy_commission - sell_commission - tax)


    def run(self, bars: List[Bar], signals: Dict[str, List[datetime.datetime]] = None):
        """
        백테스트 실행.
        bars: 시간순 정렬된 봉 데이터
        signals: {종목코드: [진입시점 리스트]} - None이면 모든 봉의 시가에 진입 시도
        """
        logger.info(f"🔬 [백테스트] 시작 | 자본: {self.capital:,}원 | 봉: {len(bars)}개")

        for bar in bars:
            # 시장 최신 가격 업데이트
            self.last_prices[bar.code] = bar.close

            # 1) 보유 종목 장중 가격 평가 및 청산 판단 (저가/고가 터치 확인)
            self._evaluate_positions(bar)

            # 2) 진입 시그널 체크 (청산 후 진입 가능하도록 순서 보장)
            if signals:
                if bar.code in signals and bar.dt in signals[bar.code]:
                    self._try_entry(bar)
            else:
                self._try_entry(bar)

            # 3) 자산 곡선 정밀 기록
            # 보유 중인 모든 종목의 '마지막 알려진 가격'을 기반으로 평가액 합산
            holdings_value = sum(
                p.qty * self.last_prices.get(p.code, p.buy_price) 
                for p in self.positions.values()
            )
            equity = self.capital + holdings_value
            self.equity_curve.append((bar.dt, equity))
            
            if equity > self._peak_equity:
                self._peak_equity = equity
            
            dd = (self._peak_equity - equity) / self._peak_equity * 100
            if dd > self._max_drawdown:
                self._max_drawdown = dd

        # 미청산 포지션 강제 청산
        if self.positions:
            logger.info(f"[백테스트] 미청산 {len(self.positions)}종목 강제 청산 (종가 기준)")
            for code in list(self.positions.keys()):
                pos = self.positions[code]
                # [수정 #4] 고가(high)가 아닌 마지막 종가로 현실적으로 청산
                last_price = self.last_prices.get(code, pos.buy_price)
                self._close_position(pos, last_price, bars[-1].dt if bars else datetime.datetime.now(), "종료 강제청산")

        return self.get_report()

    def _try_entry(self, bar: Bar):
        """진입 시도."""
        cfg = self.config
        if bar.code in self.positions:
            return
        if len(self.positions) >= cfg.max_hold:
            return

        invest_amt = self.capital * cfg.invest_pct / 100.0
        qty = int(invest_amt // bar.close) if bar.close > 0 else 0
        if qty <= 0:
            return

        cost = bar.close * qty
        if cost > self.capital:
            return

        self.capital -= cost
        self.positions[bar.code] = Position(
            code=bar.code, name=bar.name, buy_price=bar.close,
            qty=qty, buy_time=bar.dt
        )

    def _evaluate_positions(self, bar: Bar):
        """
        보유 종목 평가.
        [수정 #2] 장중 발생한 최악의 상황(저가 이탈)을 먼저 체크하여 환상 수익 차단.
        """
        if bar.code not in self.positions:
            return

        pos = self.positions[bar.code]
        cfg = self.config

        # 1. 고가 갱신 (장중 고가 터치)
        if bar.high > pos.high_price:
            pos.high_price = bar.high

        # 장중 변동률 사전 계산
        low_yield = (bar.low - pos.buy_price) / pos.buy_price * 100
        high_yield = (pos.high_price - pos.buy_price) / pos.buy_price * 100

        reason = ""
        sell_price = bar.close # 기본값

        # 2. 보수적 시나리오: 동일 봉 내에서 손절가와 익절가를 모두 터치했다면 손절이 먼저 터졌다고 가정
        if low_yield <= cfg.loss_target:
            reason = f"손절 ({cfg.loss_target:.1f}%)"
            # 손절 라인 터치 시점의 가격 (슬리피지 가정)
            sell_price = pos.buy_price * (1 + cfg.loss_target / 100)
            
        elif cfg.ts_use and high_yield >= cfg.ts_activation:
            # 고점 대비 하락폭 계산 (현재 봉의 저가 기준)
            drop_from_high = (pos.high_price - bar.low) / pos.high_price * 100
            if drop_from_high >= cfg.ts_drop:
                reason = f"T.S 발동 ({high_yield:.1f}% → 고점대비 {drop_from_high:.1f}% 하락)"
                # TS 발동 라인 터치 가격
                sell_price = pos.high_price * (1 - cfg.ts_drop / 100)
                
        elif bar.high >= pos.buy_price * (1 + cfg.profit_target / 100):
            reason = f"익절 ({cfg.profit_target:.1f}%)"
            # 익절 라인 터치 가격
            sell_price = pos.buy_price * (1 + cfg.profit_target / 100)

        # 3. 매도 조건에 부합하면 즉시 청산
        if reason:
            self._close_position(pos, int(sell_price), bar.dt, reason)

    def _close_position(self, pos: Position, sell_price: int, sell_time, reason: str):
        """포지션 청산 및 자본금 정산."""
        # 순손익(Net Profit): 수수료/세금이 모두 차감된 값
        pnl = self._calc_net_profit(pos.buy_price, sell_price, pos.qty)
        
        # [수정 #1] 자본금 복구 로직 오류 수정
        # 원금(buy_price * qty) + 순손익(pnl)을 더해주어야 세금이 정확히 계좌에 반영됨
        self.capital += (pos.buy_price * pos.qty) + pnl
        
        self.trades.append(TradeResult(
            code=pos.code, name=pos.name, buy_price=pos.buy_price,
            sell_price=sell_price, qty=pos.qty, buy_time=pos.buy_time,
            sell_time=sell_time, pnl=pnl, reason=reason
        ))
        del self.positions[pos.code]

    def get_report(self) -> dict:
        """백테스트 결과 리포트."""
        if not self.trades:
            return {"error": "거래 없음"}

        wins = [t for t in self.trades if t.pnl > 0]
        losses = [t for t in self.trades if t.pnl <= 0]
        total_pnl = sum(t.pnl for t in self.trades)

        return {
            "initial_capital": self.config.initial_capital,
            "final_capital": int(self.capital),
            "total_return_pct": round((self.capital - self.config.initial_capital) / self.config.initial_capital * 100, 2),
            "total_pnl": total_pnl,
            "total_trades": len(self.trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / len(self.trades) * 100, 1) if self.trades else 0,
            "avg_pnl": int(total_pnl / len(self.trades)) if self.trades else 0,
            "avg_win": int(sum(t.pnl for t in wins) / len(wins)) if wins else 0,
            "avg_loss": int(sum(t.pnl for t in losses) / len(losses)) if losses else 0,
            "best_trade": max(t.pnl for t in self.trades),
            "worst_trade": min(t.pnl for t in self.trades),
            "max_drawdown_pct": round(self._max_drawdown, 2),
            "profit_factor": round(
                sum(t.pnl for t in wins) / abs(sum(t.pnl for t in losses)), 2
            ) if losses and sum(t.pnl for t in losses) != 0 else float('inf'),
        }

    @staticmethod
    def load_bars_from_csv(filepath: str) -> List[Bar]:
        """CSV에서 봉 데이터 로드."""
        bars = []
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                bars.append(Bar(
                    dt=datetime.datetime.strptime(row['datetime'], '%Y-%m-%d %H:%M:%S'),
                    code=row['code'],
                    name=row.get('name', ''),
                    open=int(float(row['open'])),
                    high=int(float(row['high'])),
                    low=int(float(row['low'])),
                    close=int(float(row['close'])),
                    volume=int(float(row['volume'])),
                ))
        return bars

    @staticmethod
    def print_report(report: dict):
        """리포트 출력."""
        if "error" in report:
            print(f"\n❌ 백테스트 실패: {report['error']}")
            return
            
        print("\n" + "=" * 50)
        print("  📊 K-Trader v6.0 정밀 백테스트 리포트")
        print("=" * 50)
        
        # 보기 좋게 순서 정렬
        keys_order = [
            "initial_capital", "final_capital", "total_return_pct", "total_pnl", 
            "max_drawdown_pct", "total_trades", "wins", "losses", "win_rate", 
            "profit_factor", "avg_win", "avg_loss", "best_trade", "worst_trade"
        ]
        
        for k in keys_order:
            if k not in report: continue
            v = report[k]
            label = k.replace('_', ' ').title()
            
            if "pct" in k or k == "win_rate":
                print(f"  {label}: {v}%")
            elif isinstance(v, float) and "factor" in k:
                print(f"  {label}: {v}")
            elif isinstance(v, int) and abs(v) > 1000:
                print(f"  {label}: {v:+,}원")
            else:
                print(f"  {label}: {v}")
        print("=" * 50 + "\n")


# 파라미터 그리드 서치
def grid_search(bars: List[Bar], profit_range, loss_range):
    """익절/손절 파라미터 그리드 서치."""
    print(f"\n🚀 그리드 서치 시작 (조합 {len(profit_range) * len(loss_range)}개)...")
    results = []
    
    for p in profit_range:
        for l in loss_range:
            cfg = BacktestConfig(profit_target=p, loss_target=l)
            bt = Backtester(cfg)
            report = bt.run(bars)
            
            if "error" in report: continue
            
            results.append({
                'profit': p, 'loss': l,
                'total_pnl': report.get('total_pnl', 0),
                'win_rate': report.get('win_rate', 0),
                'max_dd': report.get('max_drawdown_pct', 0),
            })
            print(f"  익절={p:+.1f}% 손절={l:+.1f}% → PnL={report.get('total_pnl', 0):+,} 승률={report.get('win_rate', 0):.0f}% MDD={report.get('max_dd', 0):.1f}%")

    if results:
        best = max(results, key=lambda x: x['total_pnl'])
        print(f"\n🏆 [최적 파라미터] 익절={best['profit']:+.1f}% / 손절={best['loss']:+.1f}% → 누적수익 {best['total_pnl']:+,}원 (MDD {best['max_dd']:.1f}%)")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="K-Trader 정밀 백테스터")
    parser.add_argument("--data", required=True, help="가격 데이터 CSV 경로")
    parser.add_argument("--profit", type=float, default=2.2, help="익절(%)")
    parser.add_argument("--loss", type=float, default=-1.7, help="손절(%)")
    parser.add_argument("--grid", action="store_true", help="그리드 서치 실행")
    args = parser.parse_args()

    bars = Backtester.load_bars_from_csv(args.data)

    if args.grid:
        # 그리드 서치: 익절 1.0~5.0 (0.5단위), 손절 -3.0~-0.5 (0.5단위)
        grid_search(
            bars,
            profit_range=[x / 10 for x in range(10, 51, 5)],
            loss_range=[x / 10 for x in range(-30, -4, 5)]
        )
    else:
        cfg = BacktestConfig(profit_target=args.profit, loss_target=args.loss)
        bt = Backtester(cfg)
        report = bt.run(bars)
        bt.print_report(report)
