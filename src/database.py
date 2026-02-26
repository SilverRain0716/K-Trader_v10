"""
K-Trader Master v7.0 - 데이터베이스 모듈
[개선 #1] IPC 소켓 교체 완료 (폴링 테이블 제거)
[개선 #2] 순수 매매 기록(history) 및 통계 보관용으로 경량화
[개선 #3] 웹 모니터 및 종료 리포트 지원 메서드 추가
[개선 #4] 엔진 상태 파일(JSON) 기반 공유 메커니즘 추가
"""
import os
import sqlite3
import json
import logging
import datetime

logger = logging.getLogger("ktrader")


class Database:
    """SQLite WAL 모드 DB 관리자."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
        self._connect()
        self._init_tables()

        # 엔진 상태 공유 파일 (웹 모니터용)
        self._state_file = os.path.join(os.path.dirname(db_path), "engine_state.json")

    def _connect(self):
        try:
            self.conn = sqlite3.connect(self.db_path, timeout=10, isolation_level=None, check_same_thread=False)
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA busy_timeout=5000")
            logger.info("✅ [DB] SQLite 데이터베이스 연동 성공 (로깅 모드)")
        except sqlite3.Error as e:
            logger.critical(f"❌ [DB] 데이터베이스 연결 실패: {e}")
            raise

    def _init_tables(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trade_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    time TEXT NOT NULL,
                    trade_type TEXT NOT NULL,
                    condition_name TEXT,
                    stock_name TEXT,
                    stock_code TEXT,
                    exec_price INTEGER DEFAULT 0,
                    exec_qty INTEGER DEFAULT 0,
                    realized_profit INTEGER DEFAULT 0,
                    commission INTEGER DEFAULT 0,
                    tax INTEGER DEFAULT 0,
                    order_type TEXT DEFAULT '시장가'
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_summary (
                    date TEXT PRIMARY KEY,
                    total_trades INTEGER DEFAULT 0,
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0,
                    realized_profit INTEGER DEFAULT 0,
                    max_drawdown INTEGER DEFAULT 0,
                    avg_hold_seconds REAL DEFAULT 0
                )
            ''')
            logger.info("✅ [DB] 로깅 테이블 초기화 완료")
        except sqlite3.Error as e:
            logger.critical(f"❌ [DB] 테이블 생성 실패: {e}")
            raise

    # ── 매매 기록 ──────────────────────────────────
    def log_trade(self, trade_type, cond_name, name, code, price, qty, realized=0, commission=0, tax=0, order_type="시장가"):
        try:
            cursor = self.conn.cursor()
            now = datetime.datetime.now()
            today = now.strftime("%Y-%m-%d")
            t_str = now.strftime("%H:%M:%S")

            cursor.execute(
                """INSERT INTO trade_history
                   (date, time, trade_type, condition_name, stock_name, stock_code,
                   exec_price, exec_qty, realized_profit, commission, tax, order_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (today, t_str, trade_type, cond_name, name, code, price, qty, realized, commission, tax, order_type)
            )
            logger.info(f"📝 [DB] 거래 기록: {trade_type} {name}({code}) {qty}주 @{price:,} 손익={realized:+,}")
        except sqlite3.Error as e:
            logger.error(f"❌ [DB] 거래 기록 실패: {e}")

    # ── 매매 통계 ──────────────────────────────────
    def get_today_trades(self):
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT time, trade_type, condition_name, stock_name, exec_price, exec_qty, realized_profit "
                "FROM trade_history WHERE date = ? ORDER BY id", (today,)
            )
            return cursor.fetchall()
        except sqlite3.Error:
            return []

    def get_today_trade_summary(self) -> dict:
        """
        [개선 #3] 오늘의 매매 통계 요약 (종료 리포트용).
        반환: {'buy_count', 'buy_amount', 'sell_count', 'sell_amount', 'wins', 'losses', 'realized_profit'}
        """
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        try:
            cursor = self.conn.cursor()

            # 매수 통계
            cursor.execute(
                "SELECT COUNT(*), COALESCE(SUM(exec_price * exec_qty), 0) "
                "FROM trade_history WHERE date = ? AND trade_type = '매수'", (today,)
            )
            buy_row = cursor.fetchone()
            buy_count = buy_row[0] if buy_row else 0
            buy_amount = buy_row[1] if buy_row else 0

            # 매도 통계
            cursor.execute(
                """SELECT COUNT(*),
                    COALESCE(SUM(exec_price * exec_qty), 0),
                    SUM(CASE WHEN realized_profit > 0 THEN 1 ELSE 0 END),
                    SUM(CASE WHEN realized_profit <= 0 THEN 1 ELSE 0 END),
                    COALESCE(SUM(realized_profit), 0)
                FROM trade_history WHERE date = ? AND trade_type = '매도'""", (today,)
            )
            sell_row = cursor.fetchone()
            sell_count = sell_row[0] if sell_row else 0
            sell_amount = sell_row[1] if sell_row else 0
            wins = sell_row[2] if sell_row and sell_row[2] else 0
            losses = sell_row[3] if sell_row and sell_row[3] else 0
            realized = sell_row[4] if sell_row else 0

            return {
                "buy_count": buy_count,
                "buy_amount": buy_amount,
                "sell_count": sell_count,
                "sell_amount": sell_amount,
                "wins": wins,
                "losses": losses,
                "realized_profit": realized,
            }
        except sqlite3.Error as e:
            logger.error(f"❌ [DB] 오늘 통계 조회 실패: {e}")
            return {
                "buy_count": 0, "buy_amount": 0, "sell_count": 0,
                "sell_amount": 0, "wins": 0, "losses": 0, "realized_profit": 0,
            }

    def get_statistics(self, days=30):
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT
                    COUNT(*),
                    SUM(CASE WHEN realized_profit > 0 THEN 1 ELSE 0 END),
                    SUM(CASE WHEN realized_profit < 0 THEN 1 ELSE 0 END),
                    SUM(CASE WHEN realized_profit = 0 THEN 1 ELSE 0 END),
                    COALESCE(SUM(realized_profit), 0),
                    COALESCE(AVG(realized_profit), 0),
                    COALESCE(MAX(realized_profit), 0),
                    COALESCE(MIN(realized_profit), 0),
                    COALESCE(AVG(CASE WHEN realized_profit > 0 THEN realized_profit END), 0),
                    COALESCE(AVG(CASE WHEN realized_profit < 0 THEN realized_profit END), 0)
                FROM trade_history WHERE date >= ? AND trade_type = '매도'
            """, (cutoff,))
            row = cursor.fetchone()
            if not row or row[0] == 0:
                return None
            total, wins, losses, be, total_profit, avg_profit, best, worst, avg_win, avg_loss = row
            return {
                "total_sells": total, "wins": wins, "losses": losses, "breakeven": be,
                "win_rate": round((wins / total * 100) if total else 0, 1),
                "total_profit": total_profit, "avg_profit": int(avg_profit),
                "best_trade": best, "worst_trade": worst,
                "avg_win": int(avg_win), "avg_loss": int(avg_loss),
                "profit_factor": round(abs(avg_win / avg_loss), 2) if avg_loss else float('inf')
            }
        except sqlite3.Error:
            return None

    def get_condition_performance(self, days=30):
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT condition_name, COUNT(*),
                    SUM(CASE WHEN realized_profit > 0 THEN 1 ELSE 0 END), SUM(realized_profit)
                FROM trade_history WHERE date >= ? AND trade_type = '매도' GROUP BY condition_name
            """, (cutoff,))
            return cursor.fetchall()
        except sqlite3.Error:
            return []

    def get_daily_pnl(self, days=30):
        """[개선 #3] 일별 손익 조회 (웹 모니터 차트용)."""
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT date, COALESCE(SUM(realized_profit), 0), COUNT(*)
                FROM trade_history
                WHERE date >= ? AND trade_type = '매도'
                GROUP BY date ORDER BY date
            """, (cutoff,))
            return cursor.fetchall()
        except sqlite3.Error:
            return []

    # ── 엔진 상태 공유 (웹 모니터용) ──────────────────────────
    def write_engine_state(self, state: dict):
        """[개선 #4] 엔진 상태를 JSON 파일로 저장 (웹 모니터가 읽음). 원자적 쓰기."""
        tmp_path = self._state_file + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False)
            os.replace(tmp_path, self._state_file)
        except Exception as e:
            logger.debug(f"[DB] 상태 파일 쓰기 실패: {e}")

    def read_engine_state(self) -> dict:
        """[개선 #4] 엔진 상태 JSON 파일 읽기 (웹 모니터용)."""
        try:
            if os.path.exists(self._state_file):
                with open(self._state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.debug(f"[DB] 상태 파일 읽기 실패: {e}")
        return {}

    def close(self):
        if self.conn:
            self.conn.close()