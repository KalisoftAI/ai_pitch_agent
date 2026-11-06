# Start the FastAPI backend and the Vite frontend locally.
# Usage:
#   .\scripts\run-local.ps1
#   .\scripts\run-local.ps1 -BackendOnly
#   .\scripts\run-local.ps1 -FrontendOnly
[CmdletBinding()]
param(
  [switch]$BackendOnly,
  [switch]$FrontendOnly
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$python = if (Test-Path ".venv\Scripts\python.exe") { (Resolve-Path ".venv\Scripts\python.exe").Path } else { "python" }

if (-not $FrontendOnly) {
  Write-Host "Starting FastAPI on http://localhost:8000 ..." -ForegroundColor Cyan
  Start-Process -FilePath "powershell" -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$root'; & '$python' run.py"
  ) | Out-Null
}

if (-not $BackendOnly) {
  Write-Host "Starting Vite on http://localhost:5173 ..." -ForegroundColor Cyan
  Start-Process -FilePath "powershell" -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$root'; npm --prefix frontend run dev"
  ) | Out-Null
}

Write-Host ""
Write-Host "Backend : http://localhost:8000" -ForegroundColor Green
Write-Host "Frontend: http://localhost:5173" -ForegroundColor Green
Write-Host "API docs: http://localhost:8000/docs" -ForegroundColor Green
