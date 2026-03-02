@echo off
set TRADER_EXE=C:\Users\Administrator\AppData\Local\Programs\K-Trader\K-Trader.exe
set LOG=C:\Users\Administrator\Desktop\start_trader.log

echo [%date% %time%] START >> "%LOG%"
echo [%date% %time%] START

if not exist "%TRADER_EXE%" (
    echo [%date% %time%] ERROR: K-Trader.exe not found >> "%LOG%"
    echo ERROR: K-Trader.exe not found at %TRADER_EXE%
    pause
    exit /B 1
)
echo [%date% %time%] K-Trader.exe found >> "%LOG%"
echo K-Trader.exe found

REM [Fix Maintenance] 스케줄러 기동 시 K-Trader.exe 가 좀비 상태로 살아있을 수 있음.
REM 키움 -101/-106 점검 단절로 엔진은 죽고 UI만 남아있는 경우 강제 종료 후 재시작.
REM 이를 위해 기존 프로세스를 무조건 종료하고 새로 시작한다.
tasklist /FI "IMAGENAME eq K-Trader.exe" 2>NUL | find /I "K-Trader.exe" >NUL
if %ERRORLEVEL%==0 (
    echo [%date% %time%] K-Trader.exe already running - force kill and restart >> "%LOG%"
    echo K-Trader.exe already running - force kill and restart
    taskkill /F /IM K-Trader.exe >NUL 2>&1
    timeout /t 3 /nobreak >NUL
)

echo [%date% %time%] Starting K-Trader... >> "%LOG%"
echo Starting K-Trader...
start "" "%TRADER_EXE%"
echo [%date% %time%] Done >> "%LOG%"
echo Done

exit /B 0
