#!/usr/bin/env bash
# One-time GCP bootstrap for the cost-effective pipeline.
#
#   ./scripts/setup_gcp.sh <PROJECT_ID> <GITHUB_REPO> [REGION]
#   ./scripts/setup_gcp.sh gen-lang-client-0132243782 KalisoftAI/ai_pitch_agent asia-south1
#
# Idempotent-ish: uses `|| true` on creates and re-applies IAM bindings.
set -euo pipefail

PROJECT_ID="${1:?PROJECT_ID required}"
GITHUB_REPO="${2:?GITHUB_REPO (owner/repo) required}"
REGION="${3:-asia-south1}"

AR_REPO="sales-pipeline"
SERVICE="kalisoft-sales"
SA_NAME="kalisoft-sales-run"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
POOL="github"
PROVIDER="github-provider"

echo "==> Enabling APIs (only what we use)"
gcloud services enable \
  run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com sqladmin.googleapis.com storage.googleapis.com \
  --project "$PROJECT_ID"

echo "==> Artifact Registry repo + cleanup (keep 5, delete >14d)"
gcloud artifacts repositories create "$AR_REPO" \
  --repository-format=docker --location="$REGION" \
  --description="Kalisoft sales images" --project "$PROJECT_ID" 2>/dev/null || true
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
gcloud artifacts repositories set-cleanup-policies "$AR_REPO" \
  --location="$REGION" --project "$PROJECT_ID" \
  --policy="${SCRIPT_DIR}/../deploy/artifact-cleanup-policy.json"

echo "==> Deployer service account"
gcloud iam service-accounts create "$SA_NAME" \
  --display-name "Kalisoft sales CI/CD" --project "$PROJECT_ID" 2>/dev/null || true

for role in roles/run.admin roles/artifactregistry.writer roles/iam.serviceAccountUser \
            roles/cloudsql.client roles/secretmanager.secretAccessor roles/storage.objectAdmin; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" --role="$role" --condition=None --quiet >/dev/null
done

echo "==> Workload Identity Federation for GitHub"
gcloud iam workload-identity-pools create "$POOL" \
  --location=global --project "$PROJECT_ID" \
  --display-name="GitHub Actions" 2>/dev/null || true
gcloud iam workload-identity-pools providers create-oidc "$PROVIDER" \
  --location=global --project "$PROJECT_ID" --workload-identity-pool="$POOL" \
  --display-name="GitHub OIDC" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository=='${GITHUB_REPO}'" 2>/dev/null || true

gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --project "$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/attribute.repository/${GITHUB_REPO}" \
  --quiet >/dev/null

cat <<EOF

==> Set these in GitHub → Settings → Secrets and variables → Actions

Secrets:
  GCP_WORKLOAD_IDENTITY_PROVIDER = projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/providers/${PROVIDER}
  GCP_SERVICE_ACCOUNT            = ${SA_EMAIL}

Variables:
  GCP_PROJECT_ID        = ${PROJECT_ID}
  GCP_REGION            = ${REGION}
  ARTIFACT_REPOSITORY   = ${AR_REPO}
  CLOUD_SQL_INSTANCE    = ${PROJECT_ID}:${REGION}:<instance>
  CORS_ORIGINS          = https://kalisoftai.in
  CORS_ORIGINS_UAT      = https://uat.kalisoftai.in
  CORS_ORIGINS_DEV      = https://dev.kalisoftai.in
  ALLOWED_HOSTS         = *.run.app,kalisoftai.in
  GCS_BUCKET            = kalisoftai-datahub
  GCS_PATH              = all-sales-contacts-data
  GOOGLE_ALLOWED_DOMAINS = kalisoftai.in

Create app secrets (values never go in the repo):
  printf '%s' "<value>" | gcloud secrets create SALES_SECRET_KEY     --data-file=- --project ${PROJECT_ID}
  printf '%s' "<value>" | gcloud secrets create SALES_DATABASE_URL   --data-file=- --project ${PROJECT_ID}
  printf '%s' "<value>" | gcloud secrets create GOOGLE_CLIENT_ID     --data-file=- --project ${PROJECT_ID}
  printf '%s' "<value>" | gcloud secrets create GOOGLE_CLIENT_SECRET --data-file=- --project ${PROJECT_ID}
  printf '%s' "<value>" | gcloud secrets create GEMINI_API_KEY       --data-file=- --project ${PROJECT_ID}
EOF

echo "Bootstrap complete."
