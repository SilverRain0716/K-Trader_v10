"""
K-Trader Master v7.1 - 알림 모듈 (Level 3 전면 재설계)
[v7.1 수정사항]
  - Fix #3: 모든 알림 메시지에 모의투자/실계좌 구분 태그 추가
  - 기존 개선사항 모두 유지 (큐, Rate Limit, 유효성 검증, Drain 등)
"""
import os
import time
import logging
import smtplib
import threading
import queue
import datetime
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

from src.utils import calc_sell_cost

logger = logging.getLogger("ktrader")


def _mode_tag(is_mock: bool) -> str:
    """모의/실계좌 구분 태그를 반환합니다."""
    return "🔵 모의투자" if is_mock else "🔴 실계좌"


def _mode_header(is_mock: bool) -> str:
    """메시지 상단에 삽입할 모드 헤더 라인."""
    if is_mock:
        return "💻 **[모의투자 모드]**"
    else:
        return "💰 **[실계좌 모드]** ⚠️"


class Notifier:
    """디스코드 웹훅 & 이메일 알림 발송기 (큐 기반 비동기 처리)."""

    def __init__(self, secrets: dict):
        self.discord_url = secrets.get("discord_webhook", "")
        # Discord 구 도메인(discordapp.com) → 신 도메인(discord.com) 자동 정리
        # (사용자가 예전 URL을 붙여넣어도 동작하도록)
        if self.discord_url and "discordapp.com/api/webhooks/" in self.discord_url:
            self.discord_url = self.discord_url.replace("discordapp.com", "discord.com", 1)

        # requests 세션 재사용(연결 안정성/성능)
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "KTraderMaster/7.4"})

        self.email_sender = secrets.get("email_sender", "")
        self.email_password = secrets.get("email_password", "")
        self.email_receiver = secrets.get("email_receiver", "") or self.email_sender

        # 초기화 시 Webhook URL 유효성 검증
        if not self.discord_url:
            logger.warning("⚠️ [알림] discord_webhook URL이 비어있습니다! secrets.json을 확인하세요.")
        else:
            logger.info(f"✅ [알림] 디스코드 웹훅 URL 로드 완료 (길이: {len(self.discord_url)})")

        # 메시지 큐 및 워커 스레드
        self.msg_queue = queue.Queue()
        self._shutdown_event = threading.Event()
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        logger.info("🚀 [알림] 메시지 큐 워커 스레드가 가동되었습니다.")

    # ══════════════════════════════════════════════════════════
    #  큐 워커 및 기반 메서드
    # ══════════════════════════════════════════════════════════
    def _worker_loop(self):
        """큐에 쌓인 알림 요청을 하나씩 꺼내어 처리하는 무한 루프."""
        while not self._shutdown_event.is_set():
            try:
                task = self.msg_queue.get(timeout=1.0)
                method = task.get("method")
                payload = task.get("payload")

                if method == "discord":
                    self._execute_discord(payload)
                elif method == "email":
                    self._execute_email(payload)

                time.sleep(1.1)  # 디스코드 Rate Limit 방어
                self.msg_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"❌ [알림] 워커 루프 실행 중 예외 발생: {e}")
                time.sleep(2)

    def discord(self, message: str, file_path: str = None):
        """큐에 디스코드 발송 요청을 추가합니다 (즉시 반환)."""
        if not self.discord_url:
            logger.debug("[알림] discord_webhook URL이 없어 디스코드 전송을 건너뜁니다.")
            return
        self.msg_queue.put({
            "method": "discord",
            "payload": {"message": message, "file_path": file_path}
        })

    def _execute_discord(self, payload):
        """실제 디스코드 API 호출부 (워커 스레드에서 실행)."""
        msg = payload['message']
        fpath = payload.get('file_path')
        MAX_RETRIES = 3

        for attempt in range(MAX_RETRIES + 1):
            try:
                if fpath and os.path.exists(fpath):
                    with open(fpath, 'rb') as f:
                        resp = self._session.post(
                            self.discord_url,
                            data={"content": msg},
                            files={"file": f},
                            timeout=15
                        )
                else:
                    # 디스코드 메시지 2000자 제한 대응
                    if len(msg) > 1990:
                        msg = msg[:1987] + "..."
                    resp = self._session.post(
                        self.discord_url,
                        json={"content": msg},
                        timeout=10
                    )

                if resp.status_code == 429 and attempt < MAX_RETRIES:
                    ra = None
                    try:
                        ra = resp.json().get('retry_after', None)
                    except Exception:
                        ra = None

                    if ra is None:
                        try:
                            ra = float(resp.headers.get('Retry-After', '1'))
                        except Exception:
                            ra = 1.0
                    try:
                        ra = float(ra)
                    except Exception:
                        ra = 1.0

                    # 1000 이상이면 ms로 간주
                    retry_after = ra / 1000.0 if ra >= 1000 else ra
                    logger.warning(f"⚠️ [알림] 디스코드 Rate Limit! {retry_after:.1f}초 후 재시도 ({attempt + 1}/{MAX_RETRIES})")
                    time.sleep(retry_after)
                    continue  # 재시도
                elif resp.status_code in (200, 204):
                    logger.debug("✅ [알림] 디스코드 전송 성공")
                    return
                elif resp.status_code >= 400:
                    logger.error(f"❌ [알림] 디스코드 전송 실패 (HTTP {resp.status_code}): {resp.text[:200]}")
                    return

            except requests.exceptions.Timeout:
                logger.error("❌ [알림] 디스코드 전송 타임아웃")
                return
            except requests.exceptions.ConnectionError:
                logger.error("❌ [알림] 디스코드 서버 연결 불가 (인터넷 확인 필요)")
                return
            except Exception as e:
                logger.error(f"❌ [알림] 디스코드 통신 중 오류 발생: {e}")
                return

    def diagnose_discord(self, timeout: float = 7.0):
        """디스코드 웹훅 연결 상태를 동기 방식으로 점검합니다.
        반환: (ok: bool, detail: str)
        - ok=True  → 웹훅 유효/접속 가능
        - ok=False → URL 누락/만료/네트워크 차단/권한 문제 등
        """
        if not self.discord_url:
            return False, "discord_webhook URL이 비어 있습니다. secrets 설정을 확인하세요."

        # 토큰 노출 방지: query string 제거 후 점검
        url = self.discord_url.split('?', 1)[0]
        try:
            resp = self._session.get(url, timeout=timeout)
            if resp.status_code == 200:
                return True, "Webhook OK (HTTP 200)"
            # 404: 토큰/웹훅 삭제, 401/403: 권한/차단
            snippet = (resp.text or "").strip().replace("\n", " ")[:200]
            return False, f"Webhook 오류 (HTTP {resp.status_code}): {snippet}"
        except requests.exceptions.Timeout:
            return False, "Timeout: 디스코드 연결 시간 초과"
        except requests.exceptions.ConnectionError:
            return False, "ConnectionError: 네트워크/방화벽/DNS 문제 가능"
        except Exception as e:
            return False, f"예외: {e}"

    def email(self, subject: str, content: str, attachment_path: str = None):
        """큐에 이메일 발송 요청을 추가합니다."""
        if self.email_sender and self.email_password:
            self.msg_queue.put({
                "method": "email",
                "payload": {"subject": subject, "content": content, "attachment": attachment_path}
            })

    def _execute_email(self, payload):
        """실제 이메일 발송 처리부."""
        subject = payload['subject']
        content = payload['content']
        attachment_path = payload.get('attachment')

        try:
            mail = MIMEMultipart()
            mail['Subject'] = subject
            mail['From'] = self.email_sender
            mail['To'] = self.email_receiver
            mail.attach(MIMEText(content, 'plain'))

            if attachment_path and os.path.exists(attachment_path):
                with open(attachment_path, 'rb') as f:
                    part = MIMEApplication(f.read(), Name=os.path.basename(attachment_path))
                    part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment_path)}"'
                    mail.attach(part)

            smtp_host = "smtp.gmail.com"
            server = smtplib.SMTP_SSL(smtp_host, 465)
            server.login(self.email_sender, self.email_password)
            server.send_message(mail)
            server.quit()
            logger.info("📧 [알림] 이메일 발송 성공")

        except Exception as e:
            logger.error(f"❌ [알림] 이메일 발송 중 오류 발생: {e}")

    def send_all(self, message: str, file_path: str = None, email_subject: str = ""):
        """디스코드와 이메일 모두에 알림을 요청합니다."""
        self.discord(message, file_path)
        subject = email_subject or f"[K-Trader] {message[:20]}..."
        self.email(subject, message, file_path)

    def drain_and_shutdown(self, timeout: float = 10.0):
        """큐에 남은 메시지를 모두 전송한 후 워커 스레드를 종료합니다."""
        logger.info(f"⏳ [알림] 큐 드레인 시작 (남은: {self.msg_queue.qsize()}개, 타임아웃: {timeout}초)")
        try:
            self.msg_queue.join()
        except Exception:
            pass
        self._shutdown_event.set()
        self.worker_thread.join(timeout=timeout)
        logger.info("✅ [알림] 알림 시스템 안전 종료 완료")

    # ══════════════════════════════════════════════════════════
    #  구조화된 메시지 빌더 [v7.1: is_mock 파라미터 추가]
    # ══════════════════════════════════════════════════════════

    def notify_buy(self, stock_name: str, code: str, price: int, qty: int,
                   total_qty: int = 0, cond_name: str = "", deposit: int = 0, is_mock: bool = False):
        """매수 체결 알림.

        - qty: 이번 체결 수량(부분체결의 델타)
        - total_qty: 누적 보유 수량(옵션)
        """
        total = price * qty
        tag = _mode_tag(is_mock)

        lines = [
            f"🟢 **[매수 체결]** {stock_name} ({code})  〔{tag}〕",
            "━━━━━━━━━━━━━━━━━━━",
            f"📋 조건식: {cond_name or '수동'}",
            f"💰 매수가: {price:,}원",
            f"📦 이번 체결: {qty:,}주",
        ]
        if total_qty and total_qty != qty:
            lines.append(f"📦 누적 수량: {total_qty:,}주")
        lines += [
            f"💵 매수금액: {total:,}원",
            f"🏦 남은 예수금: {deposit:,}원",
            f"⏰ {datetime.datetime.now().strftime('%H:%M:%S')}",
        ]
        self.discord("\n".join(lines))
    def notify_sell(self, stock_name: str, code: str, buy_price: int, sell_price: int,
                    qty: int, pnl: int, reason: str = "", cond_name: str = "",
                    deposit: int = 0, is_mock: bool = False):
        """매도 체결 알림."""
        yield_rate = (sell_price - buy_price) / buy_price * 100 if buy_price > 0 else 0
        pnl_emoji = "🔴" if pnl > 0 else ("🔵" if pnl < 0 else "⚪")
        result_text = "수익" if pnl > 0 else ("손실" if pnl < 0 else "무승부")
        tag = _mode_tag(is_mock)

        msg = (
            f"{pnl_emoji} **[매도 체결 - {result_text}]** {stock_name} ({code})  〔{tag}〕\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📋 조건식: {cond_name or '수동'}\n"
            f"📌 사유: {reason}\n"
            f"💰 매수가: {buy_price:,}원 → 매도가: {sell_price:,}원\n"
            f"📊 수익률: {yield_rate:+.2f}%\n"
            f"💵 손익금: {pnl:+,}원\n"
            f"📦 수량: {qty:,}주\n"
            f"🏦 남은 예수금: {deposit:,}원\n"
            f"⏰ {datetime.datetime.now().strftime('%H:%M:%S')}"
        )
        self.discord(msg)

    def notify_trading_start(self, conditions: list, portfolio: dict, deposit: int,
                             realized_profit: int = 0, is_mock: bool = False):
        """자동매매 가동 알림 (포트폴리오 현황 포함)."""
        cond_str = ", ".join(conditions) if conditions else "없음"
        now = datetime.datetime.now()
        mode_hdr = _mode_header(is_mock)
        tag = _mode_tag(is_mock)

        msg = (
            f"🟢 **[봇 가동] K-Trader Master 자동매매 시작**\n"
            f"{mode_hdr}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🖥️ 계좌 모드: {tag}\n"
            f"📅 날짜: {now.strftime('%Y년 %m월 %d일')}\n"
            f"⏰ 시각: {now.strftime('%H:%M:%S')}\n"
            f"🔍 감시 조건식: {cond_str}\n"
            f"🏦 예수금: {deposit:,}원\n"
        )

        if portfolio:
            holding = {c: d for c, d in portfolio.items() if d.get('qty', 0) > 0}
            if holding:
                msg += f"\n📈 **보유 포트폴리오 ({len(holding)}종목)**\n"
                for code, data in holding.items():
                    buy_p = data.get('buy_price', 0)
                    curr_p = data.get('current_price', 0)
                    yr = (curr_p - buy_p) / buy_p * 100 if buy_p > 0 else 0
                    pnl = calc_sell_cost(buy_p, curr_p, data['qty'], is_mock)
                    msg += (
                        f"  • {data['name']} | {data['qty']}주 | "
                        f"매수 {buy_p:,}→현재 {curr_p:,} | "
                        f"{yr:+.2f}% ({pnl:+,}원)\n"
                    )
            else:
                msg += "\n📈 보유 종목: 없음\n"
        else:
            msg += "\n📈 보유 종목: 없음\n"

        self.discord(msg)

    def notify_hourly_report(self, portfolio: dict, deposit: int,
                             realized_profit: int = 0, is_mock: bool = False):
        """1시간 정기 리포트."""
        now = datetime.datetime.now()
        tag = _mode_tag(is_mock)

        unrealized = 0
        holding_count = 0
        for code, data in portfolio.items():
            if data.get('qty', 0) > 0:
                holding_count += 1
                buy_p = data.get('buy_price', 0)
                curr_p = data.get('current_price', 0)
                unrealized += calc_sell_cost(buy_p, curr_p, data['qty'], is_mock)

        total_pnl = realized_profit + unrealized

        msg = (
            f"⏰ **[정기 리포트] {now.strftime('%H:%M')} 현황**  〔{tag}〕\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🏦 예수금: {deposit:,}원\n"
            f"📊 실현 손익: {realized_profit:+,}원\n"
            f"📈 미실현 손익: {unrealized:+,}원\n"
            f"💰 총 손익: {total_pnl:+,}원\n"
            f"📦 보유: {holding_count}종목\n"
        )

        if holding_count > 0:
            msg += "\n**보유 현황:**\n"
            for code, data in portfolio.items():
                if data.get('qty', 0) <= 0:
                    continue
                buy_p = data.get('buy_price', 0)
                curr_p = data.get('current_price', 0)
                yr = (curr_p - buy_p) / buy_p * 100 if buy_p > 0 else 0
                pnl = calc_sell_cost(buy_p, curr_p, data['qty'], is_mock)
                emoji = "🔴" if pnl > 0 else ("🔵" if pnl < 0 else "⚪")
                msg += (
                    f"  {emoji} {data['name']} | {data['qty']}주 | "
                    f"{buy_p:,}→{curr_p:,} | {yr:+.2f}% ({pnl:+,}원)\n"
                )

        self.discord(msg)

    def notify_shutdown_report(self, reason: str, deposit: int, realized_profit: int,
                               unrealized_profit: int, portfolio: dict,
                               buy_count: int, buy_amount: int,
                               sell_count: int, sell_amount: int,
                               wins: int, losses: int,
                               is_mock: bool = False):
        """프로그램 종료 리포트 (최종 정산)."""
        now = datetime.datetime.now()
        total_pnl = realized_profit + unrealized_profit
        holding_count = len([c for c, d in portfolio.items() if d.get('qty', 0) > 0])
        win_rate = (wins / sell_count * 100) if sell_count > 0 else 0
        mode_hdr = _mode_header(is_mock)
        tag = _mode_tag(is_mock)

        msg = (
            f"🔴 **[봇 종료] K-Trader Master 최종 리포트**\n"
            f"{mode_hdr}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🖥️ 계좌 모드: {tag}\n"
            f"📅 날짜: {now.strftime('%Y년 %m월 %d일')}\n"
            f"⏰ 종료: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"🔧 종료 사유: {reason}\n"
            f"\n"
            f"💰 **오늘의 손익 요약**\n"
            f"📊 실현 손익: {realized_profit:+,}원\n"
            f"📈 미실현 손익: {unrealized_profit:+,}원\n"
            f"💵 총 손익 (실현+미실현): {total_pnl:+,}원\n"
            f"\n"
            f"🏦 **계좌 현황**\n"
            f"예수금: {deposit:,}원\n"
            f"미청산 포지션: {holding_count}종목\n"
            f"\n"
            f"📋 **당일 매매 통계**\n"
            f"매수 체결: {buy_count}건 ({buy_amount:,}원)\n"
            f"매도 체결: {sell_count}건 ({sell_amount:,}원)\n"
            f"승률: {win_rate:.1f}% ({wins}승 {losses}패)"
        )

        if holding_count > 0:
            msg += "\n\n📈 **미청산 포지션:**\n"
            for code, data in portfolio.items():
                if data.get('qty', 0) <= 0:
                    continue
                buy_p = data.get('buy_price', 0)
                curr_p = data.get('current_price', 0)
                yr = (curr_p - buy_p) / buy_p * 100 if buy_p > 0 else 0
                pnl = calc_sell_cost(buy_p, curr_p, data['qty'], is_mock)
                msg += f"  • {data['name']} | {data['qty']}주 | {yr:+.2f}% ({pnl:+,}원)\n"

        self.discord(msg)

    def notify_loss_limit(self, current_loss: int, limit: int):
        """일일 손실 한도 초과 경고."""
        msg = (
            f"🚨 **[긴급] 일일 손실 한도 경고!**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💣 현재 손실: {current_loss:,}원\n"
            f"🛑 손실 한도: {limit:,}원\n"
            f"⚠️ 신규 매수가 중단됩니다!"
        )
        self.discord(msg)

    def notify_error(self, title: str, detail: str = ""):
        """에러/장애 알림."""
        msg = f"❌ **[에러] {title}**"
        if detail:
            msg += f"\n{detail}"
        self.discord(msg)