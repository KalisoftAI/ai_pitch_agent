param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$renderer = Join-Path $root "renderer"

Write-Host "Checking motion renderer prerequisites..."

$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) {
    throw "Node.js 20+ is required. Install it from https://nodejs.org and run this script again."
}
$nodeVersion = (& node -p "process.versions.node").Trim()
if ([int]($nodeVersion.Split(".")[0]) -lt 20) {
    throw "Node.js 20+ is required. Found $nodeVersion."
}
Write-Host "Node.js: $nodeVersion"

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm is required. Install Node.js 20+ and run this script again."
}
Write-Host "npm: $(& npm --version)"

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    throw "FFmpeg is required for motion rendering. Install it and ensure 'ffmpeg -version' works."
}
Write-Host "FFmpeg: $(& ffmpeg -version | Select-Object -First 1)"

$chromeCandidates = @()
foreach ($candidate in @($env:MOTION_CHROME_PATH, $env:PLAYWRIGHT_CHROME)) {
    if ($candidate) { $chromeCandidates += $candidate }
}
foreach ($base in @($env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:LOCALAPPDATA)) {
    if (-not $base) { continue }
    $chromeCandidates += Join-Path $base "Google\Chrome\Application\chrome.exe"
    $chromeCandidates += Join-Path $base "Microsoft\Edge\Application\msedge.exe"
}
$chromeCandidates = $chromeCandidates | Where-Object { Test-Path -LiteralPath $_ }

if (-not $chromeCandidates) {
    throw "Chrome or Edge was not found. Install one, or set MOTION_CHROME_PATH to the browser executable."
}
Write-Host "Browser: $($chromeCandidates[0])"

if (-not (Test-Path -LiteralPath (Join-Path $renderer "package.json"))) {
    throw "Renderer package was not found at $renderer."
}

if (-not $SkipInstall) {
    Write-Host "Installing renderer dependencies..."
    Push-Location $renderer
    try {
        if (Test-Path -LiteralPath "package-lock.json") {
            npm ci --no-audit --no-fund
        } else {
            npm install --no-audit --no-fund
        }
    } finally {
        Pop-Location
    }
}

if (-not (Test-Path -LiteralPath (Join-Path $renderer "node_modules\playwright-core\package.json"))) {
    throw "playwright-core was not installed. Run this script without -SkipInstall."
}

if (-not (Test-Path -LiteralPath (Join-Path $renderer "node_modules\three\package.json"))) {
    throw "Three.js was not installed. Run this script without -SkipInstall."
}

Write-Host "Motion renderer is ready."
Write-Host "Renderer: $renderer"
Write-Host "Set MOTION_CHROME_PATH only if automatic browser detection picks the wrong executable."
