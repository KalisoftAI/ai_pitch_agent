#!/usr/bin/env bash
# Build and push the Kalisoft image.
#   ./scripts/docker_publish.sh ghcr ghcr.io/kalisoftai/ai_pitch_agent latest
#   ./scripts/docker_publish.sh artifact "" latest my-proj asia-south1 sales-pipeline
set -euo pipefail

REGISTRY="${1:-ghcr}"
IMAGE="${2:-ghcr.io/kalisoftai/ai_pitch_agent}"
TAG="${3:-latest}"
PROJECT_ID="${4:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${5:-asia-south1}"
REPOSITORY="${6:-sales-pipeline}"
SERVICE="${7:-kalisoft-sales}"

command -v docker >/dev/null 2>&1 || {
  echo "Docker is not installed. Build remotely with: gcloud builds submit --config cloudbuild.fastapi.yaml" >&2
  exit 1
}

if [ "$REGISTRY" = "artifact" ]; then
  IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${SERVICE}:${TAG}"
  gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
fi

echo "Building ${IMAGE} ..."
docker build -f Dockerfile.sales -t "${IMAGE}" .
docker push "${IMAGE}"
echo "Pushed ${IMAGE}"
