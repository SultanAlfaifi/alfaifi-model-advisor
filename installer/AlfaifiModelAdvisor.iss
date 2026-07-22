#define AppName "Alfaifi Model Advisor"
#define AppVersion "0.1.0"
#define AppPublisher "Sultan Alfaifi"
#define AppURL "https://x.com/SultAlfaifi"
#define ProjectRoot AddBackslash(SourcePath) + ".."

#ifndef ReleaseDir
  #define ReleaseDir AddBackslash(ProjectRoot) + "dist"
#endif

#ifndef OutputDir
  #define OutputDir AddBackslash(ProjectRoot) + "dist"
#endif

[Setup]
AppId={{7D96C4F1-C764-4619-91C8-758021E47C0A}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL=https://www.linkedin.com/in/alfaifi-sultan/
AppUpdatesURL={#AppURL}
DefaultDirName={localappdata}\Programs\AlfaifiModelAdvisor
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=AlfaifiModelAdvisor-Setup-{#AppVersion}
SetupIconFile={#ProjectRoot}\assets\alfaifi.ico
UninstallDisplayIcon={app}\alfaifi.exe
LicenseFile={#ReleaseDir}\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ChangesEnvironment=yes
CloseApplications=no
VersionInfoVersion=0.1.0.0
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} installer
VersionInfoCopyright=Copyright (c) 2026 Sultan Alfaifi. Licensed under Apache-2.0.
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}

[Files]
Source: "{#ReleaseDir}\alfaifi.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ReleaseDir}\alfaifi.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ReleaseDir}\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ReleaseDir}\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ReleaseDir}\NOTICE"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ReleaseDir}\TRADEMARKS.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Alfaifi Model Advisor"; Filename: "{app}\alfaifi.exe"; WorkingDir: "{app}"; IconFilename: "{app}\alfaifi.ico"
Name: "{group}\Documentation"; Filename: "{app}\README.md"
Name: "{group}\Uninstall Alfaifi Model Advisor"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\alfaifi.exe"; Description: "Launch Alfaifi Model Advisor"; Flags: nowait postinstall skipifsilent

[Code]
function NormalizedPathEntry(Value: String): String;
begin
  Result := Lowercase(Trim(Value));
  while (Length(Result) > 3) and (Result[Length(Result)] = '\') do
    Delete(Result, Length(Result), 1);
end;

function PathContains(PathValue, Entry: String): Boolean;
var
  Remaining: String;
  Item: String;
  Separator: Integer;
begin
  Result := False;
  Remaining := PathValue;
  while Remaining <> '' do
  begin
    Separator := Pos(';', Remaining);
    if Separator = 0 then
    begin
      Item := Remaining;
      Remaining := '';
    end
    else
    begin
      Item := Copy(Remaining, 1, Separator - 1);
      Delete(Remaining, 1, Separator);
    end;

    if NormalizedPathEntry(Item) = NormalizedPathEntry(Entry) then
    begin
      Result := True;
      Exit;
    end;
  end;
end;

procedure AddUserPath(Entry: String);
var
  CurrentPath: String;
begin
  if not RegQueryStringValue(HKCU, 'Environment', 'Path', CurrentPath) then
    CurrentPath := '';

  if not PathContains(CurrentPath, Entry) then
  begin
    if (CurrentPath <> '') and (CurrentPath[Length(CurrentPath)] <> ';') then
      CurrentPath := CurrentPath + ';';
    RegWriteExpandStringValue(HKCU, 'Environment', 'Path', CurrentPath + Entry);
  end;
end;

procedure RemoveUserPath(Entry: String);
var
  CurrentPath: String;
  Remaining: String;
  Item: String;
  NewPath: String;
  Separator: Integer;
begin
  if not RegQueryStringValue(HKCU, 'Environment', 'Path', CurrentPath) then
    Exit;

  Remaining := CurrentPath;
  NewPath := '';
  while Remaining <> '' do
  begin
    Separator := Pos(';', Remaining);
    if Separator = 0 then
    begin
      Item := Remaining;
      Remaining := '';
    end
    else
    begin
      Item := Copy(Remaining, 1, Separator - 1);
      Delete(Remaining, 1, Separator);
    end;

    if (Trim(Item) <> '') and
       (NormalizedPathEntry(Item) <> NormalizedPathEntry(Entry)) then
    begin
      if NewPath <> '' then
        NewPath := NewPath + ';';
      NewPath := NewPath + Trim(Item);
    end;
  end;

  RegWriteExpandStringValue(HKCU, 'Environment', 'Path', NewPath);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    AddUserPath(ExpandConstant('{app}'));
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    RemoveUserPath(ExpandConstant('{app}'));
end;
