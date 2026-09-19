; Video to audio Inno Setup 7 installer (x64)
; Copyright © 2026 XiaoDong and JiangRTTTR

#define MyAppName "Video to audio"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "XiaoDong & JiangRTTTR"
#define MyAppExeName "Video to audio.exe"
; Paths are relative to this .iss file (project root), so the script works on any machine.
#define MyAppSourceDir AddBackslash(SourcePath) + "dist\Video to audio"
#define MyAppIcon AddBackslash(SourcePath) + "resources\icon.ico"
#define MyAppUserModelId "XiaoDong.VideoToAudio"

[Setup]
AppId={{B3E8A4C2-7D91-4F5E-A6B0-2C9D8E1F4A70}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
OutputDir=dist_installer
OutputBaseFilename=Video to audio_Setup
SetupIconFile={#MyAppIcon}
SolidCompression=yes
WizardStyle=modern dynamic

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:\Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Personal configuration files are never included in the installer.
; Existing user configuration is preserved during overwrite/upgrade installation.
Source: "{#MyAppSourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "config.ini,config.json,settings.ini,settings.json,history.ini,history.json,crash.log,video-to-audio-failures.log"

[Icons]
; Read the icon directly from the installed EXE instead of referencing icon.ico.
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; IconIndex: 0; WorkingDir: "{app}"; AppUserModelID: "{#MyAppUserModelId}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; IconIndex: 0; WorkingDir: "{app}"; AppUserModelID: "{#MyAppUserModelId}"; Tasks: desktopicon

[Code]
procedure DeleteUserData;
var
  UserDataDir: string;
begin
  { Installed-version configuration is stored in %APPDATA%\video_to_audio. }
  UserDataDir := ExpandConstant('{userappdata}\video_to_audio');
  if DirExists(UserDataDir) then
    DelTree(UserDataDir, True, True, True);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  { Only a real uninstall removes user data. Overwrite/upgrade installation does not call this. }
  if CurUninstallStep = usUninstall then
  begin
    MsgBox('Video to audio 将删除程序文件以及当前用户保存的配置等数据。', mbInformation, MB_OK);
    DeleteUserData;
  end;
end;

[Run]
; Refresh the Windows shell icon cache after an overwrite installation.
Filename: "{sys}\ie4uinit.exe"; Parameters: "-show"; Flags: runhidden waituntilterminated skipifsilent skipifdoesntexist
Filename: "{app}\{#MyAppExeName}"; Description: "启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent
