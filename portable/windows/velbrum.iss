; Instalador de Velbrum para Windows (Inno Setup 6). Lo compila GitHub Actions
; (.github/workflows/paquetes.yml) a partir de la carpeta que arma
; portable/empaquetar.py:
;   iscc /DVersion=2026.10.25.1 /DOrigen=C:\...\Velbrum /DSalida=C:\... velbrum.iss
; Se instala para tu usuario, sin pedir permisos de administrador, en
; %LOCALAPPDATA%\Programs\Velbrum. Los datos quedan en %LOCALAPPDATA%\Velbrum
; (no se borran al desinstalar).

#ifndef Version
  #define Version "0"
#endif

[Setup]
AppId={{6F7D3A52-0E4B-4C1E-9A54-56B7E1A0C0DE}
AppName=Velbrum
AppVersion={#Version}
AppVerName=Velbrum {#Version}
AppPublisher=Velbrum
AppPublisherURL=https://github.com/ebalia-real/velbrum
AppSupportURL=https://github.com/ebalia-real/velbrum/issues
AppUpdatesURL=https://github.com/ebalia-real/velbrum/releases
DefaultDirName={localappdata}\Programs\Velbrum
DefaultGroupName=Velbrum
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#Salida}
OutputBaseFilename=velbrum-{#Version}-windows-x86_64-instalador
SetupIconFile={#Origen}\..\velbrum.ico
UninstallDisplayIcon={app}\velbrum.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile={#Origen}\LICENSE-velbrum.txt
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "escritorio"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#Origen}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Velbrum"; Filename: "{app}\velbrum.exe"
Name: "{group}\Velbrum con Tor"; Filename: "{app}\velbrum.exe"; Parameters: "--tor"
Name: "{group}\Desinstalar Velbrum"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Velbrum"; Filename: "{app}\velbrum.exe"; Tasks: escritorio

[Registry]
; Velbrum como navegador que se puede elegir en «Aplicaciones predeterminadas».
Root: HKCU; Subkey: "Software\Classes\VelbrumHTML"; ValueType: string; ValueName: ""; ValueData: "Página web de Velbrum"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\VelbrumHTML\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\velbrum.exe,0"
Root: HKCU; Subkey: "Software\Classes\VelbrumHTML\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\velbrum.exe"" ""%1"""
Root: HKCU; Subkey: "Software\Clients\StartMenuInternet\Velbrum"; ValueType: string; ValueName: ""; ValueData: "Velbrum"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Clients\StartMenuInternet\Velbrum\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\velbrum.exe,0"
Root: HKCU; Subkey: "Software\Clients\StartMenuInternet\Velbrum\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\velbrum.exe"""
Root: HKCU; Subkey: "Software\Clients\StartMenuInternet\Velbrum\Capabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "Velbrum"
Root: HKCU; Subkey: "Software\Clients\StartMenuInternet\Velbrum\Capabilities"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "Navegador privado con la protección de Mullvad Browser y extensiones de Chrome"
Root: HKCU; Subkey: "Software\Clients\StartMenuInternet\Velbrum\Capabilities"; ValueType: string; ValueName: "ApplicationIcon"; ValueData: "{app}\velbrum.exe,0"
Root: HKCU; Subkey: "Software\Clients\StartMenuInternet\Velbrum\Capabilities\URLAssociations"; ValueType: string; ValueName: "http"; ValueData: "VelbrumHTML"
Root: HKCU; Subkey: "Software\Clients\StartMenuInternet\Velbrum\Capabilities\URLAssociations"; ValueType: string; ValueName: "https"; ValueData: "VelbrumHTML"
Root: HKCU; Subkey: "Software\Clients\StartMenuInternet\Velbrum\Capabilities\FileAssociations"; ValueType: string; ValueName: ".html"; ValueData: "VelbrumHTML"
Root: HKCU; Subkey: "Software\Clients\StartMenuInternet\Velbrum\Capabilities\FileAssociations"; ValueType: string; ValueName: ".htm"; ValueData: "VelbrumHTML"
Root: HKCU; Subkey: "Software\Clients\StartMenuInternet\Velbrum\Capabilities\FileAssociations"; ValueType: string; ValueName: ".crx"; ValueData: "VelbrumHTML"
Root: HKCU; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "Velbrum"; ValueData: "Software\Clients\StartMenuInternet\Velbrum\Capabilities"; Flags: uninsdeletevalue
; El host de las tiendas lo registra el lanzador al abrir Velbrum; al
; desinstalar se borra.
Root: HKCU; Subkey: "Software\Mozilla\NativeMessagingHosts\velbrum.extensiones"; Flags: uninsdeletekey dontcreatekey

[Run]
Filename: "{app}\velbrum.exe"; Description: "{cm:LaunchProgram,Velbrum}"; Flags: nowait postinstall skipifsilent
