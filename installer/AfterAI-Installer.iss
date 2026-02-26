#define AppName "After-AI Director Board"
#define AppVersion "0.1.0"
#define AppPublisher "After-AI"
#define AppExeName "AfterAI-Installer"
#define CepExtensionId "com.AESD.cep"
#define SourceCepDir "..\cep"

[Setup]
AppId={{AA7EEC01-8DF2-48D5-B4C4-4E486C1D9F3C}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\After-AI
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
Compression=lzma2
SolidCompression=yes
OutputDir=dist
OutputBaseFilename={#AppExeName}-{#AppVersion}
WizardStyle=modern
SetupLogging=yes

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "enable_cep_debug"; Description: "启用 Adobe CEP 调试模式（未签名扩展必需）"; Flags: checkedonce

[Files]
; 直接把 CEP 扩展复制到 AE 扩展目录
Source: "{#SourceCepDir}\*"; DestDir: "{commoncf32}\Adobe\CEP\extensions\{#CepExtensionId}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Registry]
; 为常见 CSXS 版本写入调试开关
Root: HKCU; Subkey: "Software\Adobe\CSXS.9";  ValueType: string; ValueName: "PlayerDebugMode"; ValueData: "1"; Flags: uninsdeletevalue; Tasks: enable_cep_debug
Root: HKCU; Subkey: "Software\Adobe\CSXS.10"; ValueType: string; ValueName: "PlayerDebugMode"; ValueData: "1"; Flags: uninsdeletevalue; Tasks: enable_cep_debug
Root: HKCU; Subkey: "Software\Adobe\CSXS.11"; ValueType: string; ValueName: "PlayerDebugMode"; ValueData: "1"; Flags: uninsdeletevalue; Tasks: enable_cep_debug
Root: HKCU; Subkey: "Software\Adobe\CSXS.12"; ValueType: string; ValueName: "PlayerDebugMode"; ValueData: "1"; Flags: uninsdeletevalue; Tasks: enable_cep_debug
Root: HKCU; Subkey: "Software\Adobe\CSXS.13"; ValueType: string; ValueName: "PlayerDebugMode"; ValueData: "1"; Flags: uninsdeletevalue; Tasks: enable_cep_debug
Root: HKCU; Subkey: "Software\Adobe\CSXS.14"; ValueType: string; ValueName: "PlayerDebugMode"; ValueData: "1"; Flags: uninsdeletevalue; Tasks: enable_cep_debug
Root: HKCU; Subkey: "Software\Adobe\CSXS.15"; ValueType: string; ValueName: "PlayerDebugMode"; ValueData: "1"; Flags: uninsdeletevalue; Tasks: enable_cep_debug

[Run]
; 安装后提示用户重启 AE
Filename: "cmd.exe"; Parameters: "/c echo After-AI 已安装，请重启 After Effects。&& pause"; Flags: runhidden postinstall skipifsilent unchecked

[UninstallDelete]
; 卸载时删除扩展目录
Type: filesandordirs; Name: "{commoncf32}\Adobe\CEP\extensions\{#CepExtensionId}"
