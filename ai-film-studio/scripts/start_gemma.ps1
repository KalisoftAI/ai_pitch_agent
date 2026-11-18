param(
    [int]$Port = 8081,
    [int]$Context = 1024,
    [int]$Threads = 4
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$server = Join-Path $root "storage\tools\llama.cpp\llama-server.exe"
$modelDir = Join-Path $root "storage\models\gemma-4-12b-it-qat-q4_0"
$model = Join-Path $modelDir "gemma-4-12b-it-qat-q4_0.gguf"
$mmproj = Join-Path $modelDir "mmproj-gemma-4-12b-it-qat-q4_0.gguf"
$logDir = Join-Path $root "storage\temp"
$log = Join-Path $logDir "llama-server.log"

if (-not (Test-Path -LiteralPath $server)) {
    throw "llama-server.exe not found at $server. Download the llama.cpp Windows CPU release into storage\tools\llama.cpp."
}
if (-not (Test-Path -LiteralPath $model)) {
    throw "Model not found at $model. Run: .\.venv\Scripts\python scripts\download_models.py"
}

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$serverArgs = @(
    "-m", $model,
    "--host", "127.0.0.1",
    "--port", "$Port",
    "-c", "$Context",
    "-t", "$Threads",
    "-ngl", "0",
    "--alias", "gemma-4-12b-it-qat-q4_0",
    "--no-webui"
)
if (Test-Path -LiteralPath $mmproj) {
    $serverArgs += @("--mmproj", $mmproj)
}

Write-Host "Starting llama-server on http://127.0.0.1:$Port/v1 (context $Context, threads $Threads)"
Write-Host "Logs: $log"
& $server @serverArgs *>&1 | Tee-Object -FilePath $log
