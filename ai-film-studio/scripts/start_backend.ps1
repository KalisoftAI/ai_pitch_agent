param(
    [int]$Port = 8000,
    [switch]$Reload
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$requirements = Join-Path $root "backend\requirements.txt"

if (-not (Test-Path -LiteralPath $python)) {
    Write-Host "Creating virtual environment..."
    python -m venv (Join-Path $root ".venv")
}

Write-Host "Installing backend dependencies..."
& $python -m pip install --quiet --disable-pip-version-check -r $requirements

$uvicornArgs = @("-m", "uvicorn", "app.main:app", "--port", "$Port")
if ($Reload) { $uvicornArgs += "--reload" }

Push-Location (Join-Path $root "backend")
try {
    Write-Host "API: http://127.0.0.1:$Port"
    Write-Host "Docs: http://127.0.0.1:$Port/docs"
    & $python @uvicornArgs
} finally {
    Pop-Location
}
