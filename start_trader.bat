@echo off
:: ============================================================
:: K-Trader 자동 시작 스크립트 (Windows 작업 스케줄러용)
:: 30분 간격으로 실행하도록 스케줄러에 등록하세요.
:: 이미 실행 중이면 자동으로 스킵합니다.
:: ============================================================

:: K-Trader 설치 경로 (본인 경로로 수정하세요)
set TRADER_DIR=C:\K-Trader

:: ── 이미 실행 중인지 확인 ─────────────────────────────────────
:: engine 프로세스 확인 (python 프로세스 중 engine 인자 포함)
wmic process where "name='python.exe'" get commandline 2>nul | find "engine" >nul
if %ERRORLEVEL%==0 (
    echo [%date% %time%] K-Trader engine 이미 실행 중 - 스킵
    exit /B 0
)

:: ── 실행 중이 아니면 시작 ─────────────────────────────────────
echo [%date% %time%] K-Trader engine 시작
cd /d "%TRADER_DIR%"
start "" pythonw main.py engine

echo [%date% %time%] K-Trader engine 시작 완료
exit /B 0
