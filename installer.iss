; Inno Setup script for Sada. Build dist\Sada.exe first (build_exe.bat), then compile this file.
#define AppName "Sada"
#define AppVersion "1.0.0"

[Setup]
AppId={{6F2B8C1E-4D7A-4B39-9E52-A1C3D0F7B684}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=<your name>
DefaultDirName={autopf}\Sada
DefaultGroupName=Sada
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
SetupIconFile=brand\sada.ico
UninstallDisplayIcon={app}\Sada.exe
WizardStyle=modern
WizardImageFile=brand\wizard_large.bmp
WizardSmallImageFile=brand\wizard_small.bmp
LicenseFile=LICENSE
OutputDir=installer
OutputBaseFilename=Sada-Setup
Compression=lzma2
SolidCompression=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "dist\Sada.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Sada"; Filename: "{app}\Sada.exe"
Name: "{autodesktop}\Sada"; Filename: "{app}\Sada.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Sada.exe"; Description: "Start Sada"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Your signal data lives in %APPDATA%\Sada and is kept on uninstall.
Type: filesandordirs; Name: "{app}"
