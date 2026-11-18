param(
    [switch]$WithGemma
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

function Start-Window([string]$script, [string[]]$extra = @()) {
    $argList = @("-NoExit", "-ExecutionPolicy", "Bypass", "-File", $script) + $extra
    Start-Process -FilePath "powershell.exe" -ArgumentList $argList -WorkingDirectory $root | Out-Null
}

Start-Window (Join-Path $PSScriptRoot "start_backend.ps1") @("-Reload")
Start-Sleep -Seconds 2
Start-Window (Join-Path $PSScriptRoot "start_frontend.ps1")

if ($WithGemma) {
    Start-Window (Join-Path $PSScriptRoot "start_gemma.ps1")
}

Write-Host "Studio starting."
Write-Host "UI:  http://localhost:5173"
Write-Host "API: http://127.0.0.1:8000/docs"
if ($WithGemma) {
    Write-Host "Gemma: http://127.0.0.1:8081/v1 (first load takes a while)"
}
