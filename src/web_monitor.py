"""
K-Trader v7.0 - 웹 모니터링 대시보드
[개선 #1] DB 폴링 → JSON 파일 기반 상태 읽기 (IPC 아키텍처 호환)
[개선 #2] 누락 메서드(read_engine_state, get_daily_pnl) 에러 해결
[개선 #3] 모바일 브라우저 대응 및 자동 새로고침
[Item 1] 경로를 앱 데이터 디렉토리로 통일
[Item 2] HTTP Basic Auth + 전역 예외 처리 추가

실행: python -m src.web_monitor [--host 0.0.0.0] [--port 5000]
브라우저: http://localhost:5000
"""
import os
import sys
import json
import logging
import datetime
import functools

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from flask import Flask, render_template_string, jsonify, request, Response
except ImportError:
    print("Flask가 설치되어 있지 않습니다. pip install flask 로 설치해주세요.")
    sys.exit(1)

from src.database import Database
from src.market_calendar import MarketCalendar
from src.utils import resolve_db_path, get_app_dir
from src.config_manager import SecretManager

logger = logging.getLogger("ktrader")

# [Item 1] 경로 통일
_APP_DIR = get_app_dir()

app = Flask(__name__)
db = Database(resolve_db_path())
calendar = MarketCalendar()

# ── [Item 2] HTTP Basic Auth ──────────────────────────────────────
_web_password: str = ""   # run_web_monitor() 호출 시 secrets에서 주입


def _require_auth(f):
    """모든 라우트에 Basic Auth를 적용하는 데코레이터."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not _web_password:
            # 비밀번호 미설정 → localhost 접근만 허용
            if request.remote_addr not in ("127.0.0.1", "::1"):
                return Response(
                    "웹 모니터 비밀번호가 설정되지 않았습니다.\n"
                    "secrets.json 에 web_monitor_password 를 추가하세요.",
                    403,
                )
            return f(*args, **kwargs)
        auth = request.authorization
        if not auth or auth.password != _web_password:
            return Response(
                "인증이 필요합니다.",
                401,
                {"WWW-Authenticate": 'Basic realm="K-Trader Monitor"'},
            )
        return f(*args, **kwargs)
    return decorated


@app.errorhandler(Exception)
def _handle_exception(e):
    """[Item 2] 전역 예외 처리 — 스택 트레이스를 클라이언트에 노출하지 않음."""
    logger.error(f"[웹모니터] 처리되지 않은 예외: {e}", exc_info=True)
    return jsonify({"error": "서버 내부 오류가 발생했습니다."}), 500

# ── HTML 템플릿 (단일 파일) ──────────────────────
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <title>K-Trader v7.0 Monitor</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Malgun Gothic', -apple-system, sans-serif;
            background: #0a0a1a; color: #e0e0e0;
            padding: 20px; min-height: 100vh;
        }
        .header {
            display: flex; justify-content: space-between; align-items: center;
            padding: 16px 24px; background: #1a1a2e; border-radius: 12px;
            margin-bottom: 20px; border: 1px solid #2a3a5e;
        }
        .header h1 { font-size: 20px; color: #4fc3f7; }
        .header .status { font-size: 14px; padding: 6px 16px; border-radius: 20px; }
        .status.online { background: #1b5e20; color: #69f0ae; }
        .status.offline { background: #4a1010; color: #ff8a80; }
        .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 20px; }
        .card {
            background: #16213e; padding: 20px; border-radius: 12px;
            border: 1px solid #2a3a5e;
        }
        .card .label { font-size: 12px; color: #8892b0; margin-bottom: 8px; }
        .card .value { font-size: 24px; font-weight: bold; }
        .card .value.profit { color: #ff1744; }
        .card .value.loss { color: #448aff; }
        .card .value.neutral { color: #e0e0e0; }
        table {
            width: 100%; border-collapse: collapse; background: #0d1b2a;
            border-radius: 12px; overflow: hidden; border: 1px solid #2a3a5e;
        }
        th { background: #0f3460; color: #4fc3f7; padding: 12px; text-align: center; font-size: 12px; }
        td { padding: 10px 12px; text-align: center; border-bottom: 1px solid #1a2a4e; font-size: 13px; }
        tr:nth-child(even) { background: #1b2838; }
        .refresh-btn {
            background: #0f3460; color: #4fc3f7; border: 1px solid #2a3a5e;
            padding: 8px 20px; border-radius: 6px; cursor: pointer; font-size: 13px;
        }
        .section-title { font-size: 16px; color: #4fc3f7; margin: 20px 0 12px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 K-Trader v7.0 Monitor</h1>
        <div>
            <span class="status" id="engineStatus">로딩 중...</span>
            <button class="refresh-btn" onclick="refresh()">🔄 새로고침</button>
        </div>
    </div>

    <div class="cards" id="cards"></div>
    <h3 class="section-title">📈 포트폴리오</h3>
    <table>
        <thead><tr><th>종목명</th><th>조건식</th><th>매수가</th><th>현재가</th><th>수익률</th><th>손익</th><th>수량</th></tr></thead>
        <tbody id="portfolio"></tbody>
    </table>

    <h3 class="section-title">📋 최근 거래</h3>
    <table>
        <thead><tr><th>시간</th><th>구분</th><th>조건식</th><th>종목명</th><th>단가</th><th>수량</th><th>손익</th></tr></thead>
        <tbody id="trades"></tbody>
    </table>

    <script>
        function pnlClass(val) { return val > 0 ? 'profit' : val < 0 ? 'loss' : 'neutral'; }
        function fmt(n) { return Number(n || 0).toLocaleString('ko-KR'); }

        async function refresh() {
            try {
                const res = await fetch('/api/status');
                const d = await res.json();

                const el = document.getElementById('engineStatus');
                const status = String(d.engine_status || 'OFFLINE');
                const isTrading = status.startsWith('TRADING');
                const online = status !== 'OFFLINE' && status !== 'LOGIN_FAILED';
                el.textContent = isTrading ? '🟢 가동 중' : status;
                el.className = 'status ' + (online ? 'online' : 'offline');

                document.getElementById('cards').innerHTML = `
                    <div class="card"><div class="label">💰 예수금</div><div class="value neutral">${fmt(d.deposit)}원</div></div>
                    <div class="card"><div class="label">📊 실현손익</div><div class="value ${pnlClass(d.profit)}">${d.profit > 0 ? '+' : ''}${fmt(d.profit)}원</div></div>
                    <div class="card"><div class="label">📈 보유종목</div><div class="value neutral">${d.holdings}종목</div></div>
                    <div class="card"><div class="label">🕐 장 상태</div><div class="value neutral">${d.market_phase}</div></div>
                `;

                let phtml = '';
                for (const [code, p] of Object.entries(d.portfolio || {})) {
                    const yr = p.buy_price > 0 ? ((p.current_price - p.buy_price) / p.buy_price * 100) : 0;
                    const pnl = (p.current_price - p.buy_price) * p.qty;
                    phtml += `<tr>
                        <td>${p.name}</td><td>${p.cond_name || '-'}</td>
                        <td>${fmt(p.buy_price)}</td><td>${fmt(p.current_price)}</td>
                        <td style="color:${yr>0?'#ff1744':yr<0?'#448aff':'#888'}">${yr > 0 ? '+' : ''}${yr.toFixed(2)}%</td>
                        <td style="color:${pnl>0?'#ff1744':pnl<0?'#448aff':'#888'}">${pnl > 0 ? '+' : ''}${fmt(pnl)}</td>
                        <td>${p.qty}</td>
                    </tr>`;
                }
                document.getElementById('portfolio').innerHTML = phtml || '<tr><td colspan="7" style="color:#666">보유 종목 없음</td></tr>';

                const tres = await fetch('/api/trades');
                const trades = await tres.json();
                let thtml = '';
                for (const t of (trades || [])) {
                    thtml += `<tr>
                        <td>${t[0]}</td><td>${t[1]}</td><td>${t[2]}</td><td>${t[3]}</td>
                        <td>${fmt(t[4])}</td><td>${t[5]}</td>
                        <td style="color:${t[6]>0?'#ff1744':t[6]<0?'#448aff':'#888'}">${t[6] > 0 ? '+' : ''}${fmt(t[6])}</td>
                    </tr>`;
                }
                document.getElementById('trades').innerHTML = thtml || '<tr><td colspan="7" style="color:#666">오늘 거래 없음</td></tr>';

            } catch(e) {
                console.error('Refresh error:', e);
            }
        }

        refresh();
        setInterval(refresh, 3000);
    </script>
</body>
</html>
"""


@app.route("/")
@_require_auth
def dashboard():
    return render_template_string(DASHBOARD_HTML)


@app.route("/api/status")
@_require_auth
def api_status():
    """[v7.0] JSON 파일 기반 상태 읽기 (엔진이 0.5초마다 갱신)."""
    state = db.read_engine_state()
    if not state:
        return jsonify({
            "engine_status": "OFFLINE",
            "deposit": 0, "profit": 0, "holdings": 0,
            "portfolio": {}, "market_phase": calendar.status_text(),
            "timestamp": datetime.datetime.now().isoformat(),
        })
    port = state.get("portfolio", {})
    holding_count = len([c for c, d in port.items() if d.get("qty", 0) > 0])
    return jsonify({
        "engine_status": state.get("status", "OFFLINE"),
        "deposit": state.get("deposit", 0),
        "profit": state.get("profit", 0),
        "holdings": holding_count,
        "portfolio": port,
        "market_phase": calendar.status_text(),
        "timestamp": datetime.datetime.now().isoformat(),
    })


@app.route("/api/trades")
@_require_auth
def api_trades():
    rows = db.get_today_trades()
    return jsonify(rows)


@app.route("/api/statistics")
@_require_auth
def api_statistics():
    stats = db.get_statistics(30)
    return jsonify(stats or {})


@app.route("/api/daily_pnl")
@_require_auth
def api_daily_pnl():
    rows = db.get_daily_pnl(30)
    return jsonify([{"date": r[0], "pnl": r[1], "trades": r[2]} for r in rows])


def run_web_monitor(host: str = "127.0.0.1", port: int = 5000):
    """
    웹 모니터링 서버 실행.
    [Item 2] 기본 host를 127.0.0.1(로컬 전용)으로 변경.
             외부 접근이 필요한 경우 --host 0.0.0.0 으로 명시적 지정.
    """
    global _web_password
    # secrets 에서 웹 모니터 비밀번호 로드
    try:
        cfg_dir = os.path.join(_APP_DIR, "config")
        secrets = SecretManager(cfg_dir).load()
        _web_password = secrets.get("web_monitor_password", "").strip()
    except Exception as e:
        logger.warning(f"⚠️ [웹모니터] secrets 로드 실패: {e}")
        _web_password = ""

    if _web_password:
        print(f"🔒 K-Trader 웹 모니터: Basic Auth 활성 (비밀번호 설정됨)")
    else:
        print(f"⚠️  K-Trader 웹 모니터: 비밀번호 미설정 → localhost({host}) 접근만 허용")

    print(f"🌐 K-Trader 웹 모니터링: http://{host}:{port}")
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    run_web_monitor()
