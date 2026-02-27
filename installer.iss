; K-Trader Master — Inno Setup 인스톨러 스크립트
; Inno Setup 6.x 이상 필요: https://jrsoftware.org/isdl.php

[Setup]
AppName=K-Trader Master
AppVersion=7.5
AppPublisher=K-Trader
DefaultDirName={autopf}\K-Trader
DefaultGroupName=K-Trader Master
OutputBaseFilename=K-Trader_Setup_v7.5
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Files]
; 메인 프로그램 (PyInstaller 출력물 전체)
Source: "dist\K-Trader\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs
; 설정 마법사
Source: "dist\K-Trader Setup Wizard.exe"; DestDir: "{app}"; Flags: ignoreversion
; 빈 폴더 구조
Source: "config\*"; DestDir: "{app}\config"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "*.enc,*.json"
; 가이드 PDF
Source: "docs\K-Trader_Guide.pdf"; DestDir: "{app}\docs"; Flags: ignoreversion

[Dirs]
Name: "{app}\config"
Name: "{app}\data"
Name: "{app}\logs"
Name: "{app}\reports"

[Icons]
Name: "{group}\K-Trader Master"; Filename: "{app}\K-Trader.exe"
Name: "{group}\설정 마법사"; Filename: "{app}\K-Trader Setup Wizard.exe"
Name: "{commondesktop}\K-Trader Master"; Filename: "{app}\K-Trader.exe"; Tasks: desktopicon
Name: "{group}\사용 가이드"; Filename: "{app}\docs\K-Trader_Guide.pdf"
Name: "{group}\K-Trader 제거"; Filename: "{uninstallexe}"

[Tasks]
Name: "desktopicon"; Description: "바탕화면에 바로가기 생성"; GroupDescription: "추가 작업:"

[Run]
; 설치 완료 후 설정 마법사 실행 (secrets 없으면)
Filename: "{app}\K-Trader Setup Wizard.exe"; Description: "설정 마법사 실행"; Flags: postinstall nowait skipifsilent
