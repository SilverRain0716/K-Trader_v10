"""
K-Trader v10.6.0 - 메인 진입점
[개선] 엔진 스폰 시 동적 IPC 포트 매개변수 추가
[Fix] UI 단일 인스턴스 방지 (PID 락 파일)
[Item 1] 파일 I/O 아키텍처 개편: 설치 디렉토리(읽기전용)와 앱 데이터 디렉토리(쓰기)를 분리
"""
import sys
import os
import subprocess
import atexit

# 프로젝트 루트를 path에 추가하여 어디서 실행하든 절대 경로 보장
# PyInstaller --onedir 빌드 시 __file__은 _internal 폴더 안을 가리키므로
# sys.executable(K-Trader.exe) 기준의 폴더를 사용합니다.
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from src.utils import get_app_dir

# ── 앱 데이터 디렉토리 초기화 (쓰기 가능한 사용자 영역) ──────────
_APP_DIR = get_app_dir()
for _d in ["config", "data", "logs", "reports"]:
    os.makedirs(os.path.join(_APP_DIR, _d), exist_ok=True)


def _migrate_legacy_files():
    """
    구버전(BASE_DIR/config) → 새 앱 데이터 디렉토리 일회성 마이그레이션.
    이미 새 경로에 파일이 있으면 덮어쓰지 않음(사용자 설정 보호).
    """
    import shutil
    new_config = os.path.join(_APP_DIR, "config")
    new_data   = os.path.join(_APP_DIR, "data")
    old_config = os.path.join(BASE_DIR, "config")
    old_data   = os.path.join(BASE_DIR, "data")

    if old_config == new_config:
        return  # 개발 환경에서 경로가 같으면 스킵

    # config 파일 마이그레이션
    for fname in ("secrets.enc", "secrets.json", "bot_config.json"):
        src = os.path.join(old_config, fname)
        dst = os.path.join(new_config, fname)
        if os.path.exists(src) and not os.path.exists(dst):
            try:
                shutil.copy2(src, dst)
            except Exception:
                pass

    # data 파일 마이그레이션 (bot_state.json)
    for fname in ("bot_state.json",):
        src = os.path.join(old_data, fname)
        dst = os.path.join(new_data, fname)
        if os.path.exists(src) and not os.path.exists(dst):
            try:
                shutil.copy2(src, dst)
            except Exception:
                pass

_migrate_legacy_files()


def _is_pid_alive(pid: int) -> bool:
    """PID 가 현재 실행 중인지 확인 (Windows/POSIX 호환)."""
    try:
        if sys.platform == "win32":
            import ctypes
            PROCESS_QUERY_INFORMATION = 0x0400
            STILL_ACTIVE = 259
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, pid)
            if not handle:
                return False
            ec = ctypes.c_ulong()
            ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(ec))
            ctypes.windll.kernel32.CloseHandle(handle)
            return ec.value == STILL_ACTIVE
        else:
            os.kill(pid, 0)
            return True
    except Exception:
        return False


def _acquire_ui_lock():
    """UI 단일 인스턴스 락 파일 획득.

    Returns:
        (True, current_pid)  - 락 획득 성공
        (False, existing_pid) - 이미 다른 인스턴스 실행 중
    """
    lock_path = os.path.join(_APP_DIR, "data", "ui.lock")

    if os.path.exists(lock_path):
        try:
            with open(lock_path, "r") as f:
                existing_pid = int(f.read().strip())
            if _is_pid_alive(existing_pid):
                return False, existing_pid
        except (ValueError, IOError):
            pass  # 락 파일 손상 → 무시하고 덮어쓰기

    # 현재 PID 기록
    with open(lock_path, "w") as f:
        f.write(str(os.getpid()))

    # 프로세스 종료 시 락 파일 자동 삭제
    def _remove_lock():
        try:
            os.remove(lock_path)
        except Exception:
            pass

    atexit.register(_remove_lock)
    return True, os.getpid()


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "ui"

    if mode == "engine":
        # v6.1: UI가 할당해준 동적 IPC 포트를 읽어옵니다.
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        from src.engine import run_engine
        run_engine(port)

    elif mode == "web":
        # 선택적 인자: --host 0.0.0.0 --port 5000
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--host", default="127.0.0.1")
        parser.add_argument("--port", type=int, default=5000)
        args, _ = parser.parse_known_args(sys.argv[2:])
        from src.web_monitor import run_web_monitor
        run_web_monitor(host=args.host, port=args.port)

    elif mode == "backtest":
        args = [sys.executable, "-m", "src.backtest"] + sys.argv[2:]
        subprocess.run(args, cwd=BASE_DIR)

    else:
        # ── UI 단일 인스턴스 방지 ───────────────────────────────────────
        acquired, pid = _acquire_ui_lock()
        if not acquired:
            try:
                from PyQt5.QtWidgets import QApplication, QMessageBox
                _app = QApplication(sys.argv)
                QMessageBox.warning(
                    None, "K-Trader 이미 실행 중",
                    f"K-Trader가 이미 실행 중입니다. (PID: {pid})\n"
                    "작업 표시줄 또는 시스템 트레이를 확인하세요."
                )
                del _app
            except Exception:
                print(f"K-Trader가 이미 실행 중입니다. (PID: {pid})")
            sys.exit(0)

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
