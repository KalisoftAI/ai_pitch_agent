param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$tools = Join-Path $root "storage\tools\llama.cpp"
$server = Join-Path $tools "llama-server.exe"

if ((Test-Path -LiteralPath $server) -and -not $Force) {
    Write-Host "llama-server already present at $server (use -Force to reinstall)."
    exit 0
}

Write-Host "Finding the latest llama.cpp Windows CPU build..."
$headers = @{ "User-Agent" = "ai-film-studio" }
$releases = Invoke-RestMethod -Uri "https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=20" -Headers $headers

$asset = $null
foreach ($release in $releases) {
    $candidate = $release.assets | Where-Object { $_.name -match "bin-win-cpu-x64\.zip$" } | Select-Object -First 1
    if ($candidate) {
        $asset = $candidate
        Write-Host "Using $($release.tag_name): $($candidate.name)"
        break
    }
}

if (-not $asset) {
    throw "No Windows CPU x64 build found in recent llama.cpp releases."
}

$temp = Join-Path $root "storage\temp"
New-Item -ItemType Directory -Force -Path $temp, $tools | Out-Null
$zip = Join-Path $temp "llama-cpu.zip"

Write-Host "Downloading $($asset.name) ($([math]::Round($asset.size / 1MB, 1)) MB)..."
Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zip
Expand-Archive -LiteralPath $zip -DestinationPath $tools -Force
Remove-Item -LiteralPath $zip -Force

if (-not (Test-Path -LiteralPath $server)) {
    throw "Extraction finished, but llama-server.exe was not found."
}
Write-Host "Installed llama-server at $server"
