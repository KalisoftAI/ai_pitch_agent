$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $root "frontend"

if (-not (Test-Path -LiteralPath (Join-Path $frontend "node_modules"))) {
    Write-Host "Installing frontend dependencies..."
    Push-Location $frontend
    try {
        npm install --no-audit --no-fund
    } finally {
        Pop-Location
    }
}

Push-Location $frontend
try {
    Write-Host "UI: http://localhost:5173"
    npm run dev
} finally {
    Pop-Location
}
