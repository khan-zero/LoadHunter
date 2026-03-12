[Setup]
AppName=LoadHunter
AppVersion=1.0.21
DefaultDirName={pf}\LoadHunter
DefaultGroupName=LoadHunter
OutputDir=.
OutputBaseFilename=LoadHunter-Setup
Compression=lzma
SolidCompression=yes

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\LoadHunter.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\LoadHunter"; Filename: "{app}\LoadHunter.exe"
Name: "{commondesktop}\LoadHunter"; Filename: "{app}\LoadHunter.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\LoadHunter.exe"; Description: "{cm:LaunchProgram,LoadHunter}"; Flags: nowait postinstall skipifsilent
