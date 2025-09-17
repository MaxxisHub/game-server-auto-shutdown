param(
    [string] = "../dist/AmpAutoShutdown.exe"
)

Continue = "Stop"
 = Split-Path -Parent System.Management.Automation.InvocationInfo.MyCommand.Path
 = Resolve-Path -Path (Join-Path  )

if (-not (Test-Path )) {
    throw "Executable not found at "
}

Write-Host "Installing service using " -ForegroundColor Cyan
&  --install-service
