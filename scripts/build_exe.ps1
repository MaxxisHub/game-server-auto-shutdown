param(
    [string]$PythonExe = "python",
    [string]$ExecutableName = "AmpAutoShutdown",
    [string]$DistDir = "dist",
    [string]$BuildDir = "build"
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepositoryRoot = (Resolve-Path -Path (Join-Path $ScriptDir "..")).Path
Set-Location $RepositoryRoot

Write-Host "Building single-file executable with PyInstaller" -ForegroundColor Cyan

$SourceDir = (Resolve-Path -Path "src").Path
$GuiDir = (Resolve-Path -Path "gui").Path
$PathSeparator = [System.IO.Path]::PathSeparator
$PythonPath = "$SourceDir$PathSeparator$GuiDir"
$Env:PYTHONPATH = $PythonPath

$DataSeparator = if ([System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Windows)) {
    ";"
} else {
    ":"
}
$ConfigData = "config.example.toml${DataSeparator}."

$PyInstallerArgs = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--onefile",
    "--noconsole",
    "--name", $ExecutableName,
    "--distpath", $DistDir,
    "--workpath", $BuildDir,
    "--paths", "src",
    "--paths", "gui",
    "--add-data", $ConfigData,
    "--collect-all", "PySide6",
    "src/amp_autoshutdown/__main__.py"
)

& $PythonExe @PyInstallerArgs
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code $LASTEXITCODE"
}

Write-Host "Build complete. Executable located in $DistDir" -ForegroundColor Green
