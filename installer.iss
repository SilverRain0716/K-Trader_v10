; K-Trader Inno Setup Installer
; Requires Inno Setup 6.x: https://jrsoftware.org/isdl.php

[Setup]
AppName=K-Trader
AppVersion=7.5
AppPublisher=K-Trader
DefaultDirName={autopf}\K-Trader
DefaultGroupName=K-Trader
OutputBaseFilename=K-Trader_Setup_v7.5
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
Name: "{group}\K-Trader Guide"; Filename: "{app}\docs\K-Trader_Guide.pdf"
Name: "{group}\Uninstall K-Trader"; Filename: "{uninstallexe}"
; Desktop shortcut
Name: "{commondesktop}\K-Trader"; Filename: "{app}\K-Trader.exe"

[Run]
; Launch K-Trader after install
Filename: "{app}\K-Trader.exe"; Description: "K-Trader 실행"; Flags: nowait postinstall skipifsilent
