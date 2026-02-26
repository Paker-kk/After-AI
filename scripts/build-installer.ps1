param(
  [string]$InnoScript = "installer/AfterAI-Installer.iss"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$scriptPath = Join-Path $repoRoot $InnoScript

if (!(Test-Path $scriptPath)) {
  throw "Installer script not found: $scriptPath"
}

$isccCandidates = @(
  "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
  "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
)

$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
  throw "ISCC.exe not found. Please install Inno Setup 6 first."
}

Write-Host "Using ISCC:" $iscc
Write-Host "Building installer:" $scriptPath

Push-Location $repoRoot
try {
  & $iscc $scriptPath
}
finally {
  Pop-Location
}

Write-Host "Build done. Check installer/dist/ for the generated EXE."
