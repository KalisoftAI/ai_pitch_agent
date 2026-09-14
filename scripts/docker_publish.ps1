# Build and push the Kalisoft image.
#   ./scripts/docker_publish.ps1 -Registry ghcr -Image ghcr.io/kalisoftai/ai_pitch_agent
#   ./scripts/docker_publish.ps1 -Registry artifact -ProjectId my-proj -Region asia-south1
param(
  [ValidateSet("ghcr", "artifact")]
  [string]$Registry = "ghcr",
  [string]$Image = "ghcr.io/kalisoftai/ai_pitch_agent",
  [string]$Tag = "latest",
  [string]$ProjectId = "",
  [string]$Region = "asia-south1",
  [string]$Repository = "sales-pipeline",
  [string]$Service = "kalisoft-sales"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Error "Docker is not installed or not on PATH. Install Docker Desktop, or build remotely with: gcloud builds submit --config cloudbuild.fastapi.yaml"
}

if ($Registry -eq "artifact") {
  if (-not $ProjectId) { $ProjectId = (gcloud config get-value project) }
  $Image = "$Region-docker.pkg.dev/$ProjectId/$Repository/${Service}:$Tag"
  Write-Host "Configuring Docker for Artifact Registry $Region-docker.pkg.dev ..."
  gcloud auth configure-docker "$Region-docker.pkg.dev" --quiet
}

Write-Host "Building $Image ..."
docker build -f Dockerfile.sales -t $Image .
docker push $Image
Write-Host "Pushed $Image"
