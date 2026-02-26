# EXE Installer Notes

This installer deploys the CEP extension to:

`C:\Program Files (x86)\Common Files\Adobe\CEP\extensions\com.AESD.cep`

It also enables `PlayerDebugMode` for CSXS versions 9-15 (for unsigned CEP extension loading).

## Build

From repository root in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-installer.ps1
```

Generated output:

`installer\dist\AfterAI-Installer-<version>.exe`

## Runtime Requirement

This EXE installs the CEP panel files.  
The local Python gateway (`cep/Python/main.py`) still needs to run for AIGC API calls.
