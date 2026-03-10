; K-Trader Inno Setup Installer
; Requires Inno Setup 6.x: https://jrsoftware.org/isdl.php

[Setup]
AppName=K-Trader
AppVersion=8.0
AppPublisher=K-Trader
DefaultDirName={autopf}\K-Trader
DefaultGroupName=K-Trader
OutputBaseFilename=K-Trader_Setup_v8.0
SetupIconFile=assets\K-Trader.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\K-Trader.exe

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Files]
; Main program (PyInstaller output)
Source: "dist\K-Trader\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Setup Wizard (별도 onefile 빌드)
Source: "dist\K-Trader Setup Wizard.exe"; DestDir: "{app}"; Flags: ignoreversion
; Guide PDF
Source: "docs\K-Trader_Guide.pdf"; DestDir: "{app}\docs"; Flags: ignoreversion skipifsourcedoesntexist
; Task Scheduler bat
Source: "start_trader.bat"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Dirs]
Name: "{app}\config"
Name: "{app}\data"
Name: "{app}\logs"
Name: "{app}\reports"
Name: "{app}\docs"

[Icons]
; Start menu
Name: "{group}\K-Trader"; Filename: "{app}\K-Trader.exe"
Name: "{group}\K-Trader 설정 마법사"; Filename: "{app}\K-Trader Setup Wizard.exe"
Name: "{group}\사용 가이드"; Filename: "{app}\docs\K-Trader_Guide.pdf"
Name: "{group}\K-Trader 제거"; Filename: "{uninstallexe}"
; Desktop shortcut
Name: "{commondesktop}\K-Trader"; Filename: "{app}\K-Trader.exe"

[Run]
; 설치 완료 후 설정 마법사 먼저 실행, 완료 후 K-Trader 실행
Filename: "{app}\K-Trader Setup Wizard.exe"; Description: "설정 마법사 실행 (계좌/디스코드 설정)"; Flags: nowait postinstall skipifsilent
