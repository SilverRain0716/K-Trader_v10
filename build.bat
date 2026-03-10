@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
echo.
echo  [K-Trader v8.0 - EXE Build Tool]
echo.

:: ── 0. Python 32비트 확인 (py launcher 우선 사용) ──
echo [0/5] Python 환경 확인...

:: py launcher로 32비트 Python 3.10 직접 지정
py -3.10-32 --version >nul 2>&1
if !errorlevel! equ 0 (
    set PYTHON=py -3.10-32
    echo  [OK] py launcher로 Python 3.10 32-bit 사용
    goto :check_bits
)

:: py launcher에 버전 지정 없이 시도
py -32 --version >nul 2>&1
if !errorlevel! equ 0 (
    set PYTHON=py -32
    echo  [OK] py launcher로 32-bit Python 사용
    goto :check_bits
)

:: 일반 python 명령 시도
python --version >nul 2>&1
if !errorlevel! equ 0 (
    set PYTHON=python
    echo  [OK] python 명령 사용
    goto :check_bits
)

echo.
echo  [ERROR] Python을 찾을 수 없습니다!
echo  Python 3.10 32비트를 설치하고 py launcher가 포함되도록 해주세요.
echo  https://www.python.org/downloads/release/python-31011/
echo.
pause
exit /b 1

:check_bits
%PYTHON% -c "import struct; bits=struct.calcsize('P')*8; print('  Python ' + str(bits) + '-bit'); exit(0 if bits==32 else 1)"
if !errorlevel! neq 0 (
    echo.
    echo  [ERROR] 64비트 Python이 감지되었습니다!
    echo  키움 OpenAPI는 32비트 전용입니다.
    echo  py -3.10-32 명령이 동작하는지 확인해주세요.
    echo.
    pause
    exit /b 1
)
echo  [OK] 32-bit Python 확인 완료
echo.

:: ── 1. 의존성 설치 ──
echo [1/5] pip 의존성 설치 중...
%PYTHON% -m pip install -r requirements.txt --quiet
%PYTHON% -m pip install pyinstaller --quiet
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
%PYTHON% -m PyInstaller --noconfirm --clean --onedir --windowed --name "K-Trader" %ICON_OPT% --add-data "src;src" --hidden-import "PyQt5.QtWidgets" --hidden-import "PyQt5.QAxContainer" --hidden-import "PyQt5.QtCore" --hidden-import "PyQt5.QtGui" --hidden-import "src.engine" --hidden-import "src.ui_dashboard" --hidden-import "src.setup_wizard" --hidden-import "src.config_manager" --hidden-import "src.notifications" --hidden-import "src.database" --hidden-import "src.market_calendar" --hidden-import "src.ipc" --hidden-import "src.utils" --hidden-import "src.styles" --hidden-import "src.web_monitor" --hidden-import "src.backtest" --hidden-import "cryptography" --hidden-import "cryptography.fernet" --hidden-import "cryptography.hazmat.primitives.kdf.pbkdf2" --hidden-import "requests" --hidden-import "requests.adapters" --hidden-import "flask" --hidden-import "flask.cli" --hidden-import "openpyxl" --hidden-import "openpyxl.styles" --hidden-import "openpyxl.utils" main.py
if %errorlevel% neq 0 (
    echo  [ERROR] 빌드 실패! 위 에러를 확인하세요.
    pause
    exit /b 1
)
echo  [OK] K-Trader.exe 빌드 완료
echo.

:: ── 4. 설정 마법사 빌드 ──
echo [4/5] Setup Wizard 빌드 중...
%PYTHON% -m PyInstaller --noconfirm --clean --onefile --windowed --name "K-Trader Setup Wizard" %ICON_OPT% src\setup_wizard.py
if %errorlevel% neq 0 (
    echo  [ERROR] Setup Wizard 빌드 실패!
    pause
    exit /b 1
)
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
echo  =============================================
echo   결과: dist\K-Trader\K-Trader.exe
echo   다음: installer.iss 를 Inno Setup으로 컴파일
echo  =============================================
pause
