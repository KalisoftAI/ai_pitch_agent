# Deployment Guide — Build, Push & CI/CD

Covers: building the Docker image, pushing it, and the GitHub Actions pipelines.
The app runtime is `sales_fastapi` (FastAPI) and the image is defined by
`Dockerfile.sales` (runtime-only deps, non-root, healthcheck).

---

## 1. Prerequisites

| Tool | Needed for |
|---|---|
| Docker (or Podman) | local image build/push |
| `gcloud` CLI (authenticated) | Cloud Build, Artifact Registry, Cloud Run |
| GitHub repo admin | Actions secrets/variables |

> On this machine Docker is not installed and `gcloud` needs `gcloud auth login`.
> Until then, use **Cloud Build** (remote) or the **GitHub Actions** workflows.

---

## 2. Option A — Remote build with Cloud Build (no local Docker)

```bash
gcloud auth login
gcloud config set project <PROJECT_ID>
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com secretmanager.googleapis.com sqladmin.googleapis.com

# Release gate + image build + Trivy scan
gcloud builds submit --config cloudbuild.checks.yaml

# Build + push + deploy to Cloud Run (Secret Manager + Cloud SQL attached)
gcloud builds submit --config cloudbuild.fastapi.yaml \
  --substitutions="_REGION=asia-south1,_SERVICE=kalisoft-sales,_AR_REPOSITORY=sales-pipeline,_CLOUD_SQL_INSTANCE=<PROJECT>:asia-south1:<INSTANCE>,_CORS_ORIGINS=https://kalisoft-sales-<HASH>.a.run.app,_ALLOWED_HOSTS=*.a.run.app,_GCS_BUCKET=kalisoftai-datahub,_GCS_PATH=all-sales-contacts-data"
```

`cloudbuild.fastapi.yaml` builds `Dockerfile.sales`, pushes to Artifact Registry
(`${_REGION}-docker.pkg.dev/$PROJECT_ID/${_AR_REPOSITORY}/${_SERVICE}`), and deploys.

---

## 3. Option B — Local build & push

```powershell
# GitHub Container Registry (login first: docker login ghcr.io)
./scripts/docker_publish.ps1 -Registry ghcr -Image ghcr.io/kalisoftai/ai_pitch_agent

# Google Artifact Registry (gcloud auth required)
./scripts/docker_publish.ps1 -Registry artifact -ProjectId my-proj -Region asia-south1
```

```bash
./scripts/docker_publish.sh ghcr ghcr.io/kalisoftai/ai_pitch_agent latest
./scripts/docker_publish.sh artifact "" latest my-proj asia-south1 sales-pipeline
```

Direct equivalent:

```bash
docker build -f Dockerfile.sales -t <IMAGE> .
docker push <IMAGE>
```

---

## 4. Option C — GitHub Actions (recommended)

| Workflow | Trigger | What it does |
|---|---|---|
| `.github/workflows/ci.yml` | PR / push | ruff, bandit, gitleaks, pytest+coverage (70%), alembic parity, pip-audit, docker build |
| `.github/workflows/docker-publish.yml` | push to main/UAT/DEV, tags `v*` | Build + push image to **GHCR**; optionally **Artifact Registry** |
| `.github/workflows/cd.yml` | push to main/UAT/DEV | Cloud Build → Cloud Run deploy + `/api/health` smoke test |

### Required GitHub configuration

Secrets:
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_SERVICE_ACCOUNT`

Variables:
- `GCP_PROJECT_ID`, `GCP_REGION`, `ARTIFACT_REPOSITORY`
- `CLOUD_SQL_INSTANCE`, `CORS_ORIGINS`, `ALLOWED_HOSTS`, `GCS_BUCKET`

The Artifact Registry job in `docker-publish.yml` runs only when `GCP_PROJECT_ID`
is set, so GHCR-only publishing works out of the box.

---

## 5. Secrets (Secret Manager) — DB & mail

Never commit real values. Create secrets and reference them in the deploy config:

```bash
printf '%s' "$SECRET_KEY"     | gcloud secrets create SALES_SECRET_KEY --data-file=- --project <PROJECT>
printf '%s' "$DATABASE_URL"   | gcloud secrets create SALES_DATABASE_URL --data-file=- --project <PROJECT>
printf '%s' "$GOOGLE_CLIENT_ID"     | gcloud secrets create GOOGLE_CLIENT_ID --data-file=- --project <PROJECT>
printf '%s' "$GOOGLE_CLIENT_SECRET" | gcloud secrets create GOOGLE_CLIENT_SECRET --data-file=- --project <PROJECT>
printf '%s' "$GEMINI_API_KEY" | gcloud secrets create GEMINI_API_KEY --data-file=- --project <PROJECT>

# Mail (SMTP/IMAP app password) and Wechaty token
printf '%s' "$SMTP_PASSWORD"  | gcloud secrets create SMTP_PASSWORD --data-file=- --project <PROJECT>
printf '%s' "$WECHATY_GATEWAY_TOKEN" | gcloud secrets create SALES_WECHATY_TOKEN --data-file=- --project <PROJECT>
```

`cloudbuild.fastapi.yaml` already injects `SALES_SECRET_KEY`, `SALES_DATABASE_URL`,
`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` and `GEMINI_API_KEY`. Add any others you
need with `--set-secrets=...`.

### Cloud SQL PostgreSQL

The app resolves its connection in this order:
`DATABASE_URL` → `CLOUD_SQL_CONNECTION_NAME` (+ `POSTGRES_*`) → `POSTGRES_HOST` → SQLite.

For Cloud SQL (unix socket), set:

```
CLOUD_SQL_CONNECTION_NAME=<project>:asia-south1:<instance>
POSTGRES_DB=<db>          # already in .env
POSTGRES_USER=<user>      # already in .env
POSTGRES_PASSWORD=<pass>  # already in .env
```

or a single `DATABASE_URL=postgresql+psycopg2://user:pass@/db?host=/cloudsql/<instance>`.
Attach the instance on deploy (`--add-cloudsql-instances`, already set).

---

## 6. Local image run (optional)

```bash
docker build -f Dockerfile.sales -t kalisoft-sales:local .
docker run --rm -p 8080:8080 --env-file .env kalisoft-sales:local
# -> http://localhost:8080/api/health
```

The image excludes `.env`, tests, data and markdown via `.dockerignore`/`.dockerignore.sales`.

---

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| `docker: command not found` | Install Docker Desktop, or use Cloud Build (Option A) |
| `Reauthentication failed` from gcloud | Run `gcloud auth login` (interactive) |
| GHCR push denied | Repo Settings → Actions → enable package write; `GITHUB_TOKEN` needs `packages: write` |
| Cloud Run can't reach DB | attach Cloud SQL instance + grant the runtime SA `cloudsql.client`; check `DATABASE_URL` |
| Mail test fails | store the Gmail **app password**; SMTP 587 STARTTLS, IMAP 993 SSL |
| Health `redis: disabled` | expected — Redis is commented out locally |

---

## 8. Cost-effective pipeline & branch strategy

**Branches deploy directly — no manual prod gate.**

| Branch | GitHub environment | Cloud Run service | `ENV` | max instances |
|---|---|---|---|---|
| `main` | production | `kalisoft-sales` | `production` | 3 |
| `UAT` | staging | `kalisoft-sales-uat` | `staging` | 2 |
| `DEV` | development | `kalisoft-sales-dev` | `development` | 1 |
| `feature/**` | — | CI + GHCR image only | — | — |

Flow: **PR** → CI (ruff/bandit/gitleaks/tests/migrations/pip-audit) → merge →
**CD builds in GitHub Actions**, pushes one image to Artifact Registry, deploys to
Cloud Run, smoke-tests `/api/health`.

### Cost controls

- Cloud Run **scales to zero** (`--min-instances=0`) with `--cpu-throttling`
  (CPU billed only during requests) and `--concurrency=80` (fewer instances).
- Image built in **GitHub Actions**, not Cloud Build, to avoid per-build charges.
- **Artifact Registry cleanup**: keep 5 versions, delete anything older than 14 days
  (`deploy/artifact-cleanup-policy.json`).
- Small footprint: `--cpu=1 --memory=512Mi`, `--timeout=300`.
- Local/dev uses **SQLite**; only prod attaches **Cloud SQL**.
- Redis is disabled locally; enable a serverless tier only when needed.
- Model routing prefers **local SLMs** first; cloud models are fallback only.

### One-time bootstrap

```bash
./scripts/setup_gcp.sh <PROJECT_ID> KalisoftAI/ai_pitch_agent asia-south1
```

Creates the Artifact Registry repo + cleanup policy, the CI/CD service account,
IAM roles, the GitHub Workload Identity Federation pool/provider, and prints the
GitHub secrets/variables to configure. Then create the app secrets
(`SALES_SECRET_KEY`, `SALES_DATABASE_URL`, `GOOGLE_CLIENT_ID`,
`GOOGLE_CLIENT_SECRET`, `GEMINI_API_KEY`) as shown at the end of the script.

### Manual image build (already verified)

```bash
gcloud builds submit --config cloudbuild.image.yaml --project <PROJECT_ID>
# -> asia-south1-docker.pkg.dev/<PROJECT_ID>/sales-pipeline/kalisoft-sales:latest
```

