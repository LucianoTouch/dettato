; Installer di Dettato — compilato da build.ps1 dopo PyInstaller.
#define AppName "Dettato"
; La versione arriva da build.ps1 (/DAppVersion=...), letta da dettato\__init__.py.
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppExe "Dettato.exe"

[Setup]
AppId={{B273674A-3297-44B5-A777-D077D7C49BC1}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName}
AppPublisher=LucianoTouch
AppPublisherURL=https://github.com/LucianoTouch/dettato
; Per-utente: nessuna richiesta di permessi di amministratore.
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\{#AppName}
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
OutputDir=..\dist
OutputBaseFilename=Dettato-Setup
SetupIconFile=..\assets\dettato.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/fast
SolidCompression=yes
DiskSpanning=no
WizardStyle=modern

[Languages]
Name: "it"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "Crea un'icona sul desktop"
Name: "autostart"; Description: "Avvia Dettato all'accesso a Windows"; Flags: unchecked

[Files]
Source: "..\dist\Dettato\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; Vecchia installazione "Dictation Tool" (venv Python di ~2 GB e collegamenti).
Type: filesandordirs; Name: "{localappdata}\DictationTool"
Type: files; Name: "{userprograms}\Avvia Dictation Tool.lnk"
Type: files; Name: "{userprograms}\Chiudi Dictation Tool.lnk"
Type: files; Name: "{userprograms}\Dictation Tool.lnk"
; Versione precedente di Dettato: evita che restino file di build vecchie.
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{userprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; Comment: "Avvia Dettato o apri la sua finestra"
Name: "{userprograms}\Chiudi {#AppName}"; Filename: "{app}\{#AppExe}"; Parameters: "--stop"; Comment: "Chiudi Dettato"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Comment: "Avvia Dettato o apri la sua finestra"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "DictationTool"; Flags: deletevalue dontcreatekey
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#AppName}"; ValueData: """{app}\{#AppExe}"""; Tasks: autostart
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "{#AppName}"; Flags: uninsdeletevalue dontcreatekey

[Run]
; Avviato tramite explorer e non come figlio diretto dell'installer: i processi
; figli di Setup ereditano la mitigazione RedirectionTrust, che impedisce di
; seguire i link simbolici della cache Hugging Face, e il modello non si carica.
Filename: "{win}\explorer.exe"; Parameters: """{app}\{#AppExe}"""; Description: "Avvia Dettato adesso"; Flags: nowait postinstall

[UninstallRun]
Filename: "{app}\{#AppExe}"; Parameters: "--stop"; Flags: runhidden; RunOnceId: "StopDettato"

[Code]
procedure StopOldInstances();
var
  ResultCode, Waited: Integer;
  LegacyPythonw, LegacyMain: String;
begin
  if FileExists(ExpandConstant('{localappdata}\Programs\{#AppName}\{#AppExe}')) then
    Exec(ExpandConstant('{localappdata}\Programs\{#AppName}\{#AppExe}'), '--stop', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

  LegacyPythonw := ExpandConstant('{localappdata}\DictationTool\.venv\Scripts\pythonw.exe');
  LegacyMain := ExpandConstant('{localappdata}\DictationTool\main.py');
  if FileExists(LegacyPythonw) and FileExists(LegacyMain) then
    Exec(LegacyPythonw, '"' + LegacyMain + '" --stop', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

  Waited := 0;
  while (CheckForMutexes('Dettato_SingleInstance_Mutex') or CheckForMutexes('DictationTool_SingleInstance_Mutex')) and (Waited < 10000) do
  begin
    Sleep(250);
    Waited := Waited + 250;
  end;
  // Lascia al processo il tempo di rilasciare le DLL dopo il mutex.
  Sleep(1000);
end;

function InitializeSetup(): Boolean;
begin
  StopOldInstances();
  Result := True;
end;
