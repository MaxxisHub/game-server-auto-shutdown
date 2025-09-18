param(
    [string]$ExecutablePath = "../dist/AmpAutoShutdown.exe"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ExecutableFullPath = Join-Path -Path $ScriptDir -ChildPath $ExecutablePath
if (-not (Test-Path $ExecutableFullPath)) {
    throw "Executable not found at $ExecutableFullPath"
}
$ResolvedExe = (Resolve-Path -Path $ExecutableFullPath).ProviderPath
Write-Host "Installing service using $ResolvedExe" -ForegroundColor Cyan
& $ResolvedExe --install-service
