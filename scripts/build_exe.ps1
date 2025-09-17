param(
    [string] = "python",
    [string] = "AmpAutoShutdown",
    [string] = "dist",
    [string] = "build"
)

Continue = "Stop"
 = Split-Path -Parent 
Set-Location 

Write-Host "Building single-file executable with PyInstaller" -ForegroundColor Cyan

 = "\src;\gui"

 = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--onefile",
    "--noconsole",
    "--name", ,
    "--distpath", ,
    "--workpath", ,
    "--paths", "src",
    "--paths", "gui",
    "--add-data", "config.example.toml;.",
    "--collect-all", "PySide6",
    "src/amp_autoshutdown/__main__.py"
)

&  
if ( -ne 0) {
    throw "PyInstaller build failed with exit code "
}

Write-Host "Build complete. Executable located in " -ForegroundColor Green
