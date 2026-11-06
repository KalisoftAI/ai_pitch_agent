# Build, check and deploy by pushing to the CD branch (main / DEV).
# Pushing a branch triggers .github/workflows/cd.yml.
#
# Usage:
#   .\scripts\deploy.ps1 -Target prod -Message "feat: my change"
#   .\scripts\deploy.ps1 -Target prod
#   .\scripts\deploy.ps1 -Target dev -SkipChecks -SkipBuild
#
# Target -> branch:
#   prod -> main  (production)
#   dev  -> DEV   (development)
[CmdletBinding()]
param(
  [ValidateSet("prod", "dev")]
  [string]$Target = "prod",
  [string]$Message = "",
  [switch]$SkipChecks,
  [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$branch = switch ($Target) {
  "prod" { "main" }
  "dev"  { "DEV" }
}

$python = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }

function Invoke-Step {
  param([string]$Label, [scriptblock]$Block)
  Write-Host "==> $Label" -ForegroundColor Cyan
  & $Block
  if ($LASTEXITCODE -ne 0) { throw "$Label failed (exit $LASTEXITCODE)" }
}

if (-not $SkipChecks) {
  Invoke-Step "ruff" { & $python -m ruff check sales_fastapi }
  Invoke-Step "pytest" { & $python -m pytest -q }
}

if (-not $SkipBuild) {
  Invoke-Step "frontend build" { npm --prefix frontend run build }
}

$dirty = git status --porcelain
if ($dirty) {
  if (-not $Message) {
    Write-Host "Working tree is dirty. Re-run with -Message \"...\" to commit, or commit manually." -ForegroundColor Yellow
    git status --short
    exit 1
  }
  Invoke-Step "commit" { git add -A; git commit -m $Message }
}

Invoke-Step "fetch origin" { git fetch origin }
git merge-base --is-ancestor "origin/$branch" HEAD
if ($LASTEXITCODE -ne 0) {
  Write-Host "HEAD is not a fast-forward of origin/$branch. Merge or rebase first." -ForegroundColor Red
  exit 1
}

Invoke-Step "push HEAD -> $branch" { git push origin "HEAD:$branch" }

$sha = (git rev-parse --short HEAD)
Write-Host ""
Write-Host "Deployed $sha to $branch." -ForegroundColor Green
Write-Host "Watch the CD run: https://github.com/KalisoftAI/ai_pitch_agent/actions/workflows/cd.yml" -ForegroundColor Green
