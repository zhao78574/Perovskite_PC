#define AppName "Perovskite Engine"
#define AppVersion "1.4.6"
#define AppExeName "PerovskiteEngine.exe"

[Setup]
AppId={{B48E8FA9-6DC4-46DA-953E-8DCC6FF01393}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Perovskite Engine
SetupIconFile=..\assets\icon.ico
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
OutputDir=installers
OutputBaseFilename=PerovskiteEngine-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
UninstallDisplayIcon={app}\{#AppExeName}
ArchitecturesAllowed=x64compatible

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式："; Flags: unchecked

[Files]
Source: "release-dist\PerovskiteEngine\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "release-dist\Updater.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\卸载 {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "启动 {#AppName}"; Flags: nowait postinstall skipifsilent
