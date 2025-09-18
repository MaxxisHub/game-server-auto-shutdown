param(
    [string]$ExecutablePath = "../dist/AmpAutoShutdown.exe"
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$exePath = Resolve-Path -Path (Join-Path $scriptRoot $ExecutablePath) -ErrorAction SilentlyContinue

if (-not $exePath) {
    $exePath = Join-Path $scriptRoot $ExecutablePath
    throw "Executable not found at $exePath"
}

$exePath = $exePath.ProviderPath

if (-not (Test-Path -Path $exePath)) {
    throw "Executable not found at $exePath"
}

Write-Host "Installing service using $exePath" -ForegroundColor Cyan
& $exePath "--install-service"
