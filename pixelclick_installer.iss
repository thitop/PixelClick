[Setup]
; App Information
AppName=PixelClick
AppVersion=1.0
AppPublisher=Thitopp
AppPublisherURL=https://github.com/Thitopp
AppSupportURL=https://github.com/Thitopp
AppUpdatesURL=https://github.com/Thitopp
DefaultDirName={autopf}\PixelClick
DefaultGroupName=PixelClick
AllowNoIcons=yes
; Setup Icon & Output
SetupIconFile=logo\PixelClick_logo.ico
UninstallDisplayIcon={app}\PixelClick.exe
OutputDir=dist
OutputBaseFilename=Setup_PixelClick
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
; UI Settings
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Main Executable
Source: "dist\PixelClick.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Start Menu Shortcut
Name: "{group}\PixelClick"; Filename: "{app}\PixelClick.exe"
Name: "{group}\{cm:UninstallProgram,PixelClick}"; Filename: "{uninstallexe}"
; Desktop Shortcut
Name: "{autodesktop}\PixelClick"; Filename: "{app}\PixelClick.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\PixelClick.exe"; Description: "{cm:LaunchProgram,PixelClick}"; Flags: nowait postinstall skipifsilent
