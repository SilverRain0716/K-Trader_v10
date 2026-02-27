"""
K-Trader Master — 첫 실행 설정 마법사 (Setup Wizard)
키움 OpenAPI 설치 확인 → 계좌 정보 → 디스코드 웹훅 설정 → 완료
"""
import sys
import os
import json
import winreg
import webbrowser
import requests

from PyQt5.QtWidgets import (
    QApplication, QWizard, QWizardPage, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QCheckBox, QMessageBox,
    QGroupBox, QGridLayout, QTextEdit, QComboBox, QFrame
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPixmap

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
os.makedirs(CONFIG_DIR, exist_ok=True)


def check_kiwoom_installed() -> bool:
    """레지스트리에서 키움 OpenAPI 설치 여부 확인."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "KHOPENAPI.KHOpenAPICtrl.1")
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False


class IntroPage(QWizardPage):
    """페이지 0: 환영 + 안내."""

    def __init__(self):
        super().__init__()
        self.setTitle("K-Trader Master 설정 마법사")
        self.setSubTitle("처음 사용하시는 분을 위한 단계별 설정입니다.")

        layout = QVBoxLayout()
        layout.setSpacing(12)

        info = QLabel(
            "이 마법사는 K-Trader를 실행하기 위해 필요한 설정을 도와드립니다.\n\n"
            "다음 정보를 준비해주세요:\n"
            "  1. 키움증권 OpenAPI 설치 (미설치 시 안내해드립니다)\n"
            "  2. 프로그램 자동매매에 사용할 지정계좌 번호 및 비밀번호\n"
            "     (계좌가 여러 개인 경우 지정계좌만 자동매매, 나머지는 조회 전용)\n"
            "  3. 디스코드 웹훅 URL (선택사항, 알림 수신용)\n\n"
            "모든 정보는 암호화되어 로컬에만 저장됩니다."
        )
        info.setWordWrap(True)
        info.setFont(QFont("맑은 고딕", 10))
        layout.addWidget(info)
        layout.addStretch()
        self.setLayout(layout)


class KiwoomCheckPage(QWizardPage):
    """페이지 1: 키움 OpenAPI 설치 확인."""

    def __init__(self):
        super().__init__()
        self.setTitle("1단계: 키움 OpenAPI 설치 확인")
        self.setSubTitle("키움증권 OpenAPI가 설치되어 있어야 K-Trader를 사용할 수 있습니다.")

        layout = QVBoxLayout()
        layout.setSpacing(12)

        self.status_label = QLabel("확인 중...")
        self.status_label.setFont(QFont("맑은 고딕", 11, QFont.Bold))
        layout.addWidget(self.status_label)

        self.detail_label = QLabel("")
        self.detail_label.setWordWrap(True)
        layout.addWidget(self.detail_label)

        btn_layout = QHBoxLayout()
        self.btn_check = QPushButton("🔍 다시 확인")
        self.btn_check.clicked.connect(self._check)
        btn_layout.addWidget(self.btn_check)

        self.btn_download = QPushButton("📥 키움 OpenAPI 다운로드 페이지 열기")
        self.btn_download.clicked.connect(
            lambda: webbrowser.open("https://www.kiwoom.com/h/common/bbs/VBbsBoardBWView?dession=all&bsn=12&grn=2")
        )
        btn_layout.addWidget(self.btn_download)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 주의사항
        note = QGroupBox("⚠️ 주의사항")
        note_layout = QVBoxLayout()
        note_text = QLabel(
            "• 키움 OpenAPI는 반드시 32비트(x86)로 설치해야 합니다.\n"
            "• Python도 32비트 버전이어야 합니다.\n"
            "• 설치 후 키움증권 HTS(영웅문)에서 한 번 이상 로그인해야 활성화됩니다.\n"
            "• 모의투자 신청은 키움증권 홈페이지 → 모의투자 → 신청에서 가능합니다."
        )
        note_text.setWordWrap(True)
        note_layout.addWidget(note_text)
        note.setLayout(note_layout)
        layout.addWidget(note)

        layout.addStretch()
        self.setLayout(layout)
        self._installed = False

    def initializePage(self):
        self._check()

    def _check(self):
        try:
            installed = check_kiwoom_installed()
        except Exception:
            installed = False

        self._installed = installed
        if installed:
            self.status_label.setText("✅ 키움 OpenAPI가 설치되어 있습니다!")
            self.status_label.setStyleSheet("color: #00c853;")
            self.detail_label.setText("다음 단계로 진행하세요.")
        else:
            self.status_label.setText("❌ 키움 OpenAPI가 감지되지 않습니다.")
            self.status_label.setStyleSheet("color: #ff1744;")
            self.detail_label.setText(
                "아래 '다운로드 페이지 열기' 버튼을 눌러 키움 OpenAPI를 설치해주세요.\n"
                "설치 후 '다시 확인' 버튼을 누르면 됩니다.\n\n"
                "※ 설치를 건너뛰고 나중에 하셔도 됩니다 (다음 버튼으로 진행 가능)."
            )
        self.completeChanged.emit()

    def isComplete(self):
        return True  # 설치 안 돼도 진행 가능 (나중에 설치할 수 있으므로)


class AccountPage(QWizardPage):
    """페이지 2: 계좌 정보 입력."""

    def __init__(self):
        super().__init__()
        self.setTitle("2단계: 키움증권 계좌 정보")
        self.setSubTitle("매매에 사용할 지정계좌 번호와 비밀번호를 입력해주세요.")

        layout = QVBoxLayout()
        layout.setSpacing(12)

        info = QLabel(
            "키움 로그인 후 계좌 목록이 자동으로 불러와집니다.\n"
            "계좌가 여러 개인 경우, 아래 '지정계좌'에 프로그램 매매에 사용할 계좌번호를\n"
            "입력해주세요. 지정계좌만 자동 매매가 허용되고 나머지는 조회 전용이 됩니다.\n"
            "※ 지정계좌를 비워두면 계좌 목록의 첫 번째 계좌로 자동 선택됩니다."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # 모의투자
        mock_group = QGroupBox("🔵 모의투자 계좌")
        mock_layout = QGridLayout()
        mock_layout.addWidget(QLabel("지정계좌 번호:"), 0, 0)
        self.mock_target = QLineEdit()
        self.mock_target.setPlaceholderText("모의투자 계좌번호 (예: 1234567890, 선택사항)")
        self.mock_target.setFixedWidth(280)
        mock_layout.addWidget(self.mock_target, 0, 1)
        mock_layout.addWidget(QLabel("비밀번호:"), 1, 0)
        self.mock_pw = QLineEdit()
        self.mock_pw.setEchoMode(QLineEdit.Password)
        self.mock_pw.setPlaceholderText("모의투자 비밀번호 (보통 0000)")
        self.mock_pw.setText("0000")
        self.mock_pw.setFixedWidth(280)
        mock_layout.addWidget(self.mock_pw, 1, 1)
        mock_group.setLayout(mock_layout)
        layout.addWidget(mock_group)

        # 실계좌
        real_group = QGroupBox("🔴 실계좌 (선택사항)")
        real_layout = QGridLayout()
        real_layout.addWidget(QLabel("지정계좌 번호:"), 0, 0)
        self.real_target = QLineEdit()
        self.real_target.setPlaceholderText("실계좌 계좌번호 (예: 1234567890, 선택사항)")
        self.real_target.setFixedWidth(280)
        real_layout.addWidget(self.real_target, 0, 1)
        real_layout.addWidget(QLabel("비밀번호:"), 1, 0)
        self.real_pw = QLineEdit()
        self.real_pw.setEchoMode(QLineEdit.Password)
        self.real_pw.setPlaceholderText("실계좌 비밀번호 (4자리)")
        self.real_pw.setFixedWidth(280)
        real_layout.addWidget(self.real_pw, 1, 1)
        real_group.setLayout(real_layout)
        layout.addWidget(real_group)

        warn = QLabel("※ 계좌번호와 비밀번호는 암호화되어 로컬에만 저장됩니다. 서버로 전송되지 않습니다.")
        warn.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(warn)

        layout.addStretch()
        self.setLayout(layout)

        self.registerField("mock_target", self.mock_target)
        self.registerField("mock_pw", self.mock_pw)
        self.registerField("real_target", self.real_target)
        self.registerField("real_pw", self.real_pw)


class DiscordPage(QWizardPage):
    """페이지 3: 디스코드 웹훅 설정."""

    def __init__(self):
        super().__init__()
        self.setTitle("3단계: 디스코드 알림 설정 (선택사항)")
        self.setSubTitle("디스코드 웹훅 URL을 입력하면 매매 알림을 받을 수 있습니다.")

        layout = QVBoxLayout()
        layout.setSpacing(12)

        # 가이드
        guide = QGroupBox("📖 디스코드 웹훅 만드는 방법")
        guide_layout = QVBoxLayout()
        steps = QLabel(
            "1. 디스코드에서 알림받을 서버의 채널 선택\n"
            "2. 채널 설정(⚙️) → 연동 → 웹후크 → 새 웹후크\n"
            "3. 이름을 'K-Trader' 등으로 설정\n"
            "4. '웹후크 URL 복사' 클릭\n"
            "5. 아래에 붙여넣기"
        )
        steps.setWordWrap(True)
        guide_layout.addWidget(steps)
        guide.setLayout(guide_layout)
        layout.addWidget(guide)

        # 입력
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("웹훅 URL:"))
        self.webhook_input = QLineEdit()
        self.webhook_input.setPlaceholderText("https://discord.com/api/webhooks/...")
        url_layout.addWidget(self.webhook_input, stretch=1)
        layout.addLayout(url_layout)

        # 테스트 버튼
        test_layout = QHBoxLayout()
        self.btn_test = QPushButton("🔔 테스트 메시지 보내기")
        self.btn_test.clicked.connect(self._test_webhook)
        self.test_result = QLabel("")
        test_layout.addWidget(self.btn_test)
        test_layout.addWidget(self.test_result, stretch=1)
        layout.addLayout(test_layout)

        skip = QLabel("※ 건너뛰셔도 됩니다. 나중에 config/secrets.json에서 수정할 수 있습니다.")
        skip.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(skip)

        layout.addStretch()
        self.setLayout(layout)

        self.registerField("discord_webhook", self.webhook_input)

    def _test_webhook(self):
        url = self.webhook_input.text().strip()
        if not url:
            self.test_result.setText("❌ URL을 입력해주세요.")
            self.test_result.setStyleSheet("color: #ff1744;")
            return
        try:
            resp = requests.post(url, json={
                "content": "✅ **K-Trader 연결 테스트 성공!**\n이 메시지가 보이면 웹훅이 정상 작동합니다."
            }, timeout=10)
            if resp.status_code in (200, 204):
                self.test_result.setText("✅ 전송 성공! 디스코드를 확인하세요.")
                self.test_result.setStyleSheet("color: #00c853;")
            else:
                self.test_result.setText(f"❌ 실패 (HTTP {resp.status_code})")
                self.test_result.setStyleSheet("color: #ff1744;")
        except Exception as e:
            self.test_result.setText(f"❌ 오류: {str(e)[:50]}")
            self.test_result.setStyleSheet("color: #ff1744;")


class CalendarApiPage(QWizardPage):
    """페이지 4: 공공데이터 API 키 (선택사항)."""

    def __init__(self):
        super().__init__()
        self.setTitle("4단계: 공휴일 API 키 (선택사항)")
        self.setSubTitle("한국투자데이터 API 키가 있으면 공휴일 자동 판별이 가능합니다.")

        layout = QVBoxLayout()
        layout.setSpacing(12)

        info = QLabel(
            "공공데이터포털(data.go.kr)의 '한국천문연구원 특일정보' API 키를 입력하면\n"
            "공휴일/대체공휴일을 자동으로 감지하여 장이 쉬는 날 매매를 방지합니다.\n\n"
            "없으면 내장된 기본 공휴일 목록을 사용합니다 (대부분 충분합니다)."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        key_layout = QHBoxLayout()
        key_layout.addWidget(QLabel("API 키:"))
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("공공데이터포털 서비스키 (선택사항)")
        key_layout.addWidget(self.api_key_input, stretch=1)
        layout.addLayout(key_layout)

        layout.addStretch()
        self.setLayout(layout)

        self.registerField("calendar_api_key", self.api_key_input)


class CompletePage(QWizardPage):
    """페이지 5: 설정 완료."""

    def __init__(self):
        super().__init__()
        self.setTitle("설정 완료!")
        self.setSubTitle("모든 설정이 저장되었습니다.")

        layout = QVBoxLayout()
        layout.setSpacing(12)

        self.summary = QTextEdit()
        self.summary.setReadOnly(True)
        self.summary.setFont(QFont("Consolas", 10))
        layout.addWidget(self.summary)

        info = QLabel(
            "※ 설정은 config/secrets.enc에 암호화되어 저장됩니다.\n"
            "※ 설정 변경이 필요하면 프로그램 내 설정 탭에서 수정하거나,\n"
            "   이 마법사를 다시 실행하세요 (setup_wizard.exe)."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #888;")
        layout.addWidget(info)

        layout.addStretch()
        self.setLayout(layout)

    def initializePage(self):
        mock_target = self.field("mock_target") or ""
        mock_pw = self.field("mock_pw") or "0000"
        real_target = self.field("real_target") or ""
        real_pw = self.field("real_pw") or ""
        webhook = self.field("discord_webhook") or ""
        api_key = self.field("calendar_api_key") or ""

        def mask_account(acc):
            """계좌번호 마스킹 (앞 4자리 + **** + 뒤 2자리)."""
            if not acc:
                return "(미설정 — 첫 번째 계좌 자동 사용)"
            if len(acc) > 6:
                return f"{acc[:4]}****{acc[-2:]}"
            return acc

        summary_lines = [
            "═══════════════════════════════════",
            "  K-Trader 설정 요약",
            "═══════════════════════════════════",
            f"  모의투자 지정계좌: {mask_account(mock_target)}",
            f"  모의투자 비밀번호: {'●' * len(mock_pw) if mock_pw else '(미설정)'}",
            f"  실계좌 지정계좌:   {mask_account(real_target)}",
            f"  실계좌 비밀번호:   {'●' * len(real_pw) if real_pw else '(미설정)'}",
            f"  디스코드 웹훅:     {'✅ 설정됨' if webhook else '❌ 미설정'}",
            f"  공휴일 API:        {'✅ 설정됨' if api_key else '❌ 미설정 (기본값 사용)'}",
            "═══════════════════════════════════",
        ]
        self.summary.setText("\n".join(summary_lines))

        # 저장
        self._save_secrets(mock_target, mock_pw, real_target, real_pw, webhook, api_key)

    def _save_secrets(self, mock_target, mock_pw, real_target, real_pw, webhook, api_key):
        secrets = {
            "mock_target_account": mock_target,
            "mock_account_password": mock_pw,
            "real_target_account": real_target,
            "real_account_password": real_pw,
            "discord_webhook": webhook,
            "calendar_api_key": api_key,
        }

        # 기존 secrets가 있으면 병합 (덮어쓰지 않고 추가)
        secrets_path = os.path.join(CONFIG_DIR, "secrets.json")
        if os.path.exists(secrets_path):
            try:
                with open(secrets_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                existing.update({k: v for k, v in secrets.items() if v})
                secrets = existing
            except Exception:
                pass

        # 평문으로 저장 (프로그램 실행 시 자동 암호화 마이그레이션됨)
        with open(secrets_path, "w", encoding="utf-8") as f:
            json.dump(secrets, f, ensure_ascii=False, indent=2)


class SetupWizard(QWizard):
    """K-Trader 설정 마법사 메인."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("K-Trader Master — 설정 마법사")
        self.setMinimumSize(650, 500)
        self.setWizardStyle(QWizard.ModernStyle)

        self.addPage(IntroPage())
        self.addPage(KiwoomCheckPage())
        self.addPage(AccountPage())
        self.addPage(DiscordPage())
        self.addPage(CalendarApiPage())
        self.addPage(CompletePage())

        self.setButtonText(QWizard.NextButton, "다음 →")
        self.setButtonText(QWizard.BackButton, "← 이전")
        self.setButtonText(QWizard.FinishButton, "완료 ✅")
        self.setButtonText(QWizard.CancelButton, "취소")


def should_run_wizard() -> bool:
    """secrets.json/secrets.enc가 없으면 마법사 실행 필요."""
    secrets_path = os.path.join(CONFIG_DIR, "secrets.json")
    encrypted_path = os.path.join(CONFIG_DIR, "secrets.enc")
    return not os.path.exists(secrets_path) and not os.path.exists(encrypted_path)


def run_wizard():
    app = QApplication.instance() or QApplication(sys.argv)
    wizard = SetupWizard()
    wizard.show()
    return wizard.exec_()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    wizard = SetupWizard()
    wizard.show()
    sys.exit(app.exec_())
