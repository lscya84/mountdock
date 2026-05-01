#define MyAppName "MountDock"
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "dist\\MountDock"
#endif
#ifndef OutputDir
  #define OutputDir "dist\\release"
#endif
#ifndef OutputBaseFilename
  #define OutputBaseFilename "MountDock-Setup"
#endif

[Setup]
AppId={{A2B5E8DA-4A74-4DF4-9C1A-BE6AC30D44B7}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=lscya84
AppPublisherURL=https://github.com/lscya84/mountdock
AppSupportURL=https://github.com/lscya84/mountdock/issues
AppUpdatesURL=https://github.com/lscya84/mountdock/releases
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\MountDock.exe
ChangesAssociations=no
OutputDir={#OutputDir}
OutputBaseFilename={#OutputBaseFilename}
SetupIconFile=..\assets\icon.ico
LicenseFile=..\LICENSE

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\MountDock"; Filename: "{app}\MountDock.exe"
Name: "{autodesktop}\MountDock"; Filename: "{app}\MountDock.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\MountDock.exe"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
function GetWinFspInstallDir(var InstallDir: string): Boolean;
begin
  Result :=
    RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\WinFsp', 'InstallDir', InstallDir) or
    RegQueryStringValue(HKLM, 'SOFTWARE\WinFsp', 'InstallDir', InstallDir);
end;

function InitializeSetup(): Boolean;
var
  InstallDir: string;
  Reply: Integer;
begin
  if GetWinFspInstallDir(InstallDir) then
  begin
    Result := True;
    exit;
  end;

  Reply := MsgBox(
    'MountDock requires WinFsp for Windows drive mounts.' + #13#10 + #13#10 +
    'WinFsp was not detected on this PC.' + #13#10 +
    'Install WinFsp first, then run the MountDock installer again.' + #13#10 + #13#10 +
    'Open the WinFsp download page now?',
    mbConfirmation,
    MB_YESNO
  );

  if Reply = IDYES then
    ShellExec('open', 'https://winfsp.dev/rel/', '', '', SW_SHOWNORMAL, ewNoWait, Reply);

  Result := False;
end;
