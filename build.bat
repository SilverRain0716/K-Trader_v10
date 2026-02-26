@echo off
chcp 65001 >nul
echo.
echo  ╔═══════════════════════════════════════════╗
echo  ║   K-Trader Master v7.5 - EXE Build Tool  ║
echo  ╚═══════════════════════════════════════════╝
echo.

:: ── 0. Python 32비트 확인 ──
echo [0/5] Python 환경 확인...
python --version 2>nul
if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] Python이 설치되지 않았거나 PATH에 없습니다!
    echo  https://www.python.org/downloads/ 에서 32비트 버전을 설치해주세요.
    echo  설치 시 "Add Python to PATH" 반드시 체크!
    pause
    exit /b 1
)
python -c "import struct; bits=struct.calcsize('P')*8; print(f'  Python {bits}-bit'); assert bits==32" 2>nul
if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] 64비트 Python이 감지되었습니다!
    echo  키움 OpenAPI는 32비트 전용이므로, 32비트 Python이 필요합니다.
    pause
    exit /b 1
)
echo  [OK] 32-bit Python 확인 완료
echo.

:: ── 1. 의존성 설치 ──
echo [1/5] pip 의존성 설치 중...
pip install -r requirements.txt --quiet 2>nul
pip install pyinstaller --quiet 2>nul
echo  [OK] 의존성 설치 완료
echo.

:: ── 2. 아이콘 확인 ──
set ICON_OPT=
if exist "assets\icon.ico" (
    set "ICON_OPT=--icon=assets\icon.ico"
    echo [2/5] 아이콘 파일 발견: assets\icon.ico
) else (
    echo [2/5] 아이콘 없음 - 기본 아이콘 사용
)
echo.

:: ── 3. 메인 프로그램 빌드 ──
echo [3/5] K-Trader.exe 빌드 중... (1~3분 소요)
pyinstaller --noconfirm --clean --onedir --windowed --name "K-Trader" %ICON_OPT% --add-data "src;src" --hidden-import "PyQt5.QtWidgets" --hidden-import "PyQt5.QAxContainer" --hidden-import "PyQt5.QtCore" --hidden-import "PyQt5.QtGui" --hidden-import "src.engine" --hidden-import "src.ui_dashboard" --hidden-import "src.setup_wizard" --hidden-import "src.config_manager" --hidden-import "src.notifications" --hidden-import "src.database" --hidden-import "src.market_calendar" --hidden-import "src.ipc" --hidden-import "src.utils" --hidden-import "src.styles" --hidden-import "src.web_monitor" --hidden-import "src.backtest" main.py
if %errorlevel% neq 0 (
    echo  [ERROR] 빌드 실패! 위 에러를 확인하세요.
    pause
    exit /b 1
)
echo  [OK] K-Trader.exe 빌드 완료
echo.

:: ── 4. 설정 마법사 빌드 ──
echo [4/5] Setup Wizard 빌드 중...
pyinstaller --noconfirm --clean --onefile --windowed --name "K-Trader Setup Wizard" %ICON_OPT% src\setup_wizard.py
echo  [OK] Setup Wizard 빌드 완료
echo.

:: ── 5. 배포 폴더 구성 ──
echo [5/5] 배포 폴더 구성 중...
if not exist "dist\K-Trader\config" mkdir "dist\K-Trader\config"
if not exist "dist\K-Trader\data" mkdir "dist\K-Trader\data"
if not exist "dist\K-Trader\logs" mkdir "dist\K-Trader\logs"
if not exist "dist\K-Trader\reports" mkdir "dist\K-Trader\reports"
if not exist "dist\K-Trader\docs" mkdir "dist\K-Trader\docs"
if exist "dist\K-Trader Setup Wizard.exe" copy /Y "dist\K-Trader Setup Wizard.exe" "dist\K-Trader\" >nul
if exist "docs\K-Trader_Guide.pdf" copy /Y "docs\K-Trader_Guide.pdf" "dist\K-Trader\docs\" >nul
echo  [OK] 완료
echo.
echo  ═══════════════════════════════════════════
echo   결과: dist\K-Trader\K-Trader.exe
echo   다음: installer.iss 를 Inno Setup으로 컴파일
echo  ═══════════════════════════════════════════
pause
