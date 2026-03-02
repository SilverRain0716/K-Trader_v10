@echo off
:: ============================================================
:: K-Trader 자동 시작 스크립트 (Windows 작업 스케줄러용)
:: 30분 간격으로 실행하도록 스케줄러에 등록하세요.
:: 이미 실행 중이면 자동으로 스킵합니다.
:: ============================================================

:: K-Trader 실행 파일 경로
set TRADER_EXE=C:\Users\Administrator\AppData\Local\Programs\K-Trader\K-Trader.exe

:: ── 이미 실행 중인지 확인 ─────────────────────────────────────
tasklist /FI "IMAGENAME eq K-Trader.exe" 2>NUL | find /I "K-Trader.exe" >NUL
if %ERRORLEVEL%==0 (
    echo [%date% %time%] K-Trader 이미 실행 중 - 스킵
    exit /B 0
)

:: ── 실행 중이 아니면 시작 ─────────────────────────────────────
echo [%date% %time%] K-Trader 시작
start "" "%TRADER_EXE%"

echo [%date% %time%] K-Trader 시작 완료
exit /B 0
