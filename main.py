"""
K-Trader Master v7.4.6 - 메인 진입점
[개선] 엔진 스폰 시 동적 IPC 포트 매개변수 추가
"""
import sys
import os
import subprocess

# 프로젝트 루트를 path에 추가하여 어디서 실행하든 절대 경로 보장
# PyInstaller --onedir 빌드 시 __file__은 _internal 폴더 안을 가리키므로
# sys.executable(K-Trader.exe) 기준의 폴더를 사용합니다.
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# 필수 디렉토리 생성
for d in ["config", "data", "logs", "reports"]:
    os.makedirs(os.path.join(BASE_DIR, d), exist_ok=True)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "ui"

    if mode == "engine":
        # v6.1: UI가 할당해준 동적 IPC 포트를 읽어옵니다.
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        from src.engine import run_engine
        run_engine(port)

    elif mode == "web":
        from src.web_monitor import run_web_monitor
        run_web_monitor()

    elif mode == "backtest":
        args = [sys.executable, "-m", "src.backtest"] + sys.argv[2:]
        subprocess.run(args, cwd=BASE_DIR)

    else:
        # 첫 실행 시 설정 마법사 실행
        from src.setup_wizard import should_run_wizard, run_wizard
        if should_run_wizard():
            from PyQt5.QtWidgets import QApplication
            app = QApplication(sys.argv)
            result = run_wizard()
            if result == 0:  # 취소
                print("설정이 취소되었습니다.")
                sys.exit(0)
            del app  # QApplication 중복 방지

        # 기본: UI 대시보드
        from src.ui_dashboard import run_ui
        run_ui()


if __name__ == "__main__":
    main()