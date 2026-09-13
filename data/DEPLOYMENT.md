# AI Sales Agent — Cloud Run Deployment Guide (Cloud Shell)

Complete, step-by-step instructions to deploy this repository to Google Cloud Run
from Cloud Shell.

## Current CI/CD status

This repository contains two separate Cloud Run applications:

- **Django AI Sales Agent:** `deploy.sh`, `Dockerfile`, and the manual deployment
  path documented below.
- **FastAPI sales pipeline:** `deploy_sales.sh`, `deploy_sales.ps1`,
  `Dockerfile.sales`, and `cloudbuild.sales.yaml`; this path still requires a
  real Cloud SQL instance and project-specific substitutions.

There is currently no checked-in GitHub Actions workflow, Django Cloud Build
configuration, or configured Cloud Build trigger. The CI/CD setup in §10 is the
recommended next step and does not claim to be active until a trigger is
created and tested.

- **Project ID (target):** `Project ID`
- **Repository:** `https://github.com/aisolutions-hash/ai_pitch_agent.git`
- **Branch:** `main`
- **Deploy script to use:** `deploy.sh` (Django app)

---

## 1. Understand what is in the repository

This repo contains **two** applications:

| App | Stack | Deploy script | Status |
|---|---|---|---|
| **AI Sales Agent (main)** | Django (`sales_project`, `extractor`, `scraper`, `dashboard`, `pitch_generator`, `ai_agent_pitch`) | `deploy.sh` + `Dockerfile` + `cloudrun.env.yaml` | **Deploy this now** |
| FastAPI sales pipeline | FastAPI (`sales_fastapi/`) | `deploy_sales.sh` + `Dockerfile.sales` + `cloudbuild.sales.yaml` | Future migration target — **do NOT deploy yet** |

> **Why not `deploy_sales.sh`?** It requires a Cloud SQL Postgres instance
> (`INSTANCE_CONNECTION_NAME` is still a placeholder). The live Django app uses
> an external **Neon PostgreSQL** database, which is already configured in
> `cloudrun.env.yaml`. Deploying the FastAPI pipeline without a real Cloud SQL
> instance will fail.

---

## 2. Prerequisites

- A Google Cloud account with billing enabled.
- Owner/editor access to project `gen-lang-client-0132243782`.
- The following service credentials (explained in §4):
  - Google Sheets / GCS service-account key: `credentials.json`
  - The env config file: `cloudrun.env.yaml`
- `gcloud` CLI (pre-installed in Cloud Shell).

---

## 3. Files you must have ready

These two files are **gitignored** and **dockerignored** — they are NOT in the
GitHub repository and are NOT baked into the Docker image. You must upload them
manually to Cloud Shell and keep them out of git.

| File | Purpose | Where it lives at runtime |
|---|---|---|
| `cloudrun.env.yaml` | All app env vars (`DB_*`, API keys, Gmail/SMTP, Sheets IDs, etc.) | Passed to Cloud Run via `--env-vars-file` |
| `credentials.json` | Google service-account JSON (Sheets + GCS access) | Pushed to **Secret Manager** as `google-app-credentials`, mounted as `GOOGLE_CREDENTIALS_JSON` |

`deploy.sh` errors out if either file is missing, so prepare both first.

---

## 4. Prepare: `cloudrun.env.yaml`

1. Create `cloudrun.env.yaml` locally or upload an existing protected file.
  There is currently no committed `cloudrun.env.yaml.example` in this
  repository. If you add a reviewed, secret-free template later, use:

   ```bash
  cp cloudrun.env.yaml.example cloudrun.env.yaml
   ```
2. Or upload your existing file (recommended — it already contains working values).

   ```yaml
   DJANGO_SECRET_KEY: "..."            # REQUIRED - was missing before, added
   GCS_BUCKET_NAME: "kalisoft-contacts"
   DJANGO_DEBUG: "false"
   ALLOWED_HOSTS: ".run.app"
   APP_USERNAME: "kalisoftai"
   APP_PASSWORD: "..."
   DB_HOST: "...neon.tech"
   DB_SSLMODE: "require"
   GEMINI_API_KEY: "..."
   SERPAPI_API_KEY: "..."
   API_KEYS: "..."
   GCS_PROJECT_ID: "gen-lang-client-0681178392"
   GOOGLE_SHEET_ID: "..."
   LINKEDIN_SHEET_ID: "..."
   PITCH_SHEET_ID: "..."
   SCHEDULER_SECRET: "..."
   EMAIL_USER: "..."
   EMAIL_PASS: "..."
   IMAP_SERVER: "imap.gmail.com"
   PITCH_EMAIL_HOST_USER: "..."
   PITCH_GMAIL_APP_PASSWORD: "..."
   DEFAULT_FROM_NAME: "KalisoftAI"
   ```

3. Mandatory checks before deploying:

   - **`DJANGO_SECRET_KEY` is present.** Without it Django falls back to
     `change-me-in-production` (works, but insecure and signs sessions with a
     fixed key).
   - No **duplicate keys** (YAML last-wins or errors — the old file had
     `GCS_BUCKET_NAME` twice; it was cleaned up).
   - **`GCS_PROJECT_ID`** should match the project that owns `credentials.json`
     (currently `gen-lang-client-0681178392`). GCS/Sheets access is governed by
     the service account, not by the Cloud Run deploy project.

4. After the **first** deploy, come back and fill in the Cloud Run URL
   (see §8):

   ```yaml
   CSRF_TRUSTED_ORIGINS: "https://sales-agent-xxxx.a.run.app"
   SITE_URL: "https://sales-agent-xxxx.a.run.app"
   ```

5. **Never commit this file.** It contains live secrets. It is already in
   `.gitignore` (`cloudrun.env*`) and `.dockerignore`.

---

## 5. Prepare: `credentials.json`

- A Google service-account key with access to:
  - The GCS bucket `kalisoft-contacts` (read/write).
  - The Google Sheets referenced by `GOOGLE_SHEET_ID`, `LINKEDIN_SHEET_ID`,
    `PITCH_SHEET_ID` (share the sheets with the service-account email).
- Download the JSON from the GCP Console:
  `IAM & Admin → Service Accounts → your SA → Keys → Add key → JSON`.
- Keep it out of git: it is already in `.gitignore` and `.dockerignore`.

`deploy.sh` uploads it to Secret Manager automatically:

```bash
# if the secret doesn't exist yet:
gcloud secrets create google-app-credentials --data-file=credentials.json
# if it exists (re-deploy): adds a new version
gcloud secrets versions add google-app-credentials --data-file=credentials.json
```

---

## 6. Push the deploy script changes

`deploy.sh` is the Django deployment script for this project:

- Defaults `PROJECT_ID` to `gen-lang-client-0132243782` (overridable via
  `GOOGLE_CLOUD_PROJECT`).
- It accepts `cloudrun.env.yaml` by default and can also convert an `ENV_FILE`
  ending in `.env` to temporary YAML.
- It uploads or reuses the `google-app-credentials` Secret Manager secret.
- `deploy_sales.sh` and `deploy_sales.ps1` are for the separate FastAPI/Cloud
  SQL path and should not be used for this Django service.

`deploy.sh` IS tracked by git, so commit and push it (the two credential files
must NOT be pushed):

```bash
git add deploy.sh
git commit -m "chore: point deploy.sh at cloud run project and simplify env handling"
git push origin main
```

---

## 7. Deploy from Cloud Shell

### 7.1 Open Cloud Shell and set the project

```bash
gcloud config set project gen-lang-client-0132243782
gcloud config get-value project   # verify: gen-lang-client-0132243782
```

### 7.2 Clone the repository

```bash
git clone https://github.com/aisolutions-hash/ai_pitch_agent.git
cd ai_pitch_agent
git checkout main
git pull origin main
```

### 7.3 Upload the credential files

Use the Cloud Shell toolbar menu (**⋮ → Upload file**) to upload, into
`~/ai_pitch_agent/`:

1. `cloudrun.env.yaml`
2. `credentials.json`

Verify both landed in the project root:

```bash
ls -la cloudrun.env.yaml credentials.json
```

### 7.4 Run the deploy script

```bash
chmod +x deploy.sh
bash deploy.sh
```

What the script does, in order:

1. Resolves `PROJECT_ID` (default `gen-lang-client-0132243782`).
2. Verifies `gcloud` is installed and `cloudrun.env.yaml` exists.
3. Enables required APIs (idempotent):
   `run`, `cloudbuild`, `artifactregistry`, `secretmanager`, `storage`,
   `sheets`, `drive`.
4. Pushes `credentials.json` to Secret Manager as `google-app-credentials` and
   grants the Cloud Run runtime service account
   `<PROJECT_NUMBER>-compute@developer.gserviceaccount.com` the role
   `roles/secretmanager.secretAccessor`.
5. Creates the Artifact Registry repository `cloud-run-source-deploy`
   (us-central1) if missing.
6. Builds + pushes the image:
   `gcr`/`run` image `us-central1-docker.pkg.dev/gen-lang-client-0132243782/cloud-run-source-deploy/sales-agent`.
7. Deploys the Cloud Run service **`sales-agent`** with:
   - `--platform managed --region us-central1`
   - `--allow-unauthenticated` (public entry; app login still protects pages)
   - `--memory 1Gi --cpu 1 --timeout 600`
   - `--no-cpu-throttling` (keeps background scrape/campaign threads alive)
   - `--env-vars-file cloudrun.env.yaml`
   - `--set-secrets GOOGLE_CREDENTIALS_JSON=google-app-credentials:latest`
8. Prints the service URL and post-deploy checklist.

### 7.5 Re-run once for the service URL

Cloud Run URLs are `https://sales-agent-<random-hash>.<region>.run.app` and the
hash is only known after the first deploy. Because `CSRF_TRUSTED_ORIGINS` and
`SITE_URL` depend on that URL:

```bash
bash deploy.sh        # second run picks up the new values
```

---

## 8. Post-deploy steps

### 8.1 Get the service URL

```bash
gcloud run services describe sales-agent \
  --region us-central1 \
  --format='value(status.url)'
```

### 8.2 Add the URL to the env file

Edit `cloudrun.env.yaml` (Cloud Shell editor or `nano`):

```yaml
CSRF_TRUSTED_ORIGINS: "https://sales-agent-xxxx.a.run.app"
SITE_URL: "https://sales-agent-xxxx.a.run.app"
```

- `CSRF_TRUSTED_ORIGINS` — required so login/CSRF form POSTs succeed over HTTPS.
- `SITE_URL` — used for password-reset email links.
- `ALLOWED_HOSTS` can stay `.run.app` (accepts every `.run.app` subdomain).

### 8.3 Redeploy so the new env takes effect

```bash
bash deploy.sh
```

### 8.4 Verify with diagnostics

1. Open `https://sales-agent-xxxx.a.run.app/login/` and sign in as `kalisoftai`.
2. Open `https://sales-agent-xxxx.a.run.app/app/api/diagnostics/`.
3. The report shows:
   - `env` — presence of required vars (`DJANGO_SECRET_KEY`, `DB_*`,
     `GEMINI_API_KEY`, `GOOGLE_CREDENTIALS_JSON`, Sheet IDs, GCS vars, etc.)
   - `checks` — `database` (user count), `gcs` (bucket blobs), `sheets` (opens
     the configured sheet), `gemini` (models visible)
   - `overall_ok` — boolean summary
4. Fix anything marked `env missing` or `ok: False`, then re-run `bash deploy.sh`.

---

## 9. Updating the app later

```bash
# on your machine
git add -A && git commit -m "feat: your change"
git push origin main

# Cloud Shell
git pull origin main
bash deploy.sh
```

New revisions only need `bash deploy.sh` — the env file and credentials/
secret is reused.

---

## FastAPI runtime modes

The FastAPI application supports local SQLite, hosted PostgreSQL, and Cloud SQL
PostgreSQL. Leave `DATABASE_URL`, `CLOUD_SQL_CONNECTION_NAME`, and
`POSTGRES_HOST` empty for local SQLite. Set `DATABASE_URL` for a normal
PostgreSQL server. For Cloud SQL, attach the instance to Cloud Run and provide
the Unix-socket URL through the `SALES_DATABASE_URL` Secret Manager secret.

FastAPI authentication currently verifies Google Sign-In ID tokens and then
issues an application JWT. Production deployments force `AUTH_DEV_MODE=false`,
so synthetic `dev:<email>` tokens are rejected. Firebase Authentication is not
implemented in this codebase; Firebase tokens must not be sent to
`/api/auth/google` until a Firebase token verifier is added and tested.

The repository includes `cloudbuild.fastapi.yaml`. Before using it:

1. Create `SALES_SECRET_KEY`, `SALES_DATABASE_URL`, `GOOGLE_CLIENT_ID`,
   `GOOGLE_CLIENT_SECRET`, and `GEMINI_API_KEY` in Secret Manager.
2. Grant the Cloud Run runtime service account access to those secrets.
3. Replace `_CLOUD_SQL_INSTANCE` and `_CORS_ORIGINS` in the build config.
4. Create the Artifact Registry repository named by `_AR_REPOSITORY`.

## 10. CI/CD with Cloud Build (Django)

Cloud Build is the natural CI/CD option already supported by this repository.
The current Django script is not suitable as an unattended build trigger
because it expects a private env file and a local credential file. Use a
dedicated `cloudbuild.django.yaml` instead.

That config should:

1. Build the root `Dockerfile`.
2. Push an immutable `$SHORT_SHA` image to Artifact Registry.
3. Deploy that image to `sales-agent` in `us-central1`.
4. Inject secrets with Secret Manager or protected runtime configuration.
5. Run a post-deploy smoke check against `/login/` or a public health endpoint.

Do not store `cloudrun.env.yaml`, `credentials.json`, or secret values in the
repository, GitHub Actions, or Cloud Build substitutions. Give the build
service account only the permissions it needs: Cloud Build builder, Artifact
Registry writer, Cloud Run admin, and Service Account User. Give the Cloud Run
runtime service account Secret Manager access only to its required secrets.

In Google Cloud Console, open **Cloud Build > Triggers** and:

1. Connect the GitHub repository.
2. Create a push trigger for `main`.
3. Select `cloudbuild.django.yaml` as the configuration file.
4. Add non-secret substitutions such as `_REGION`, `_SERVICE`, and
  `_AR_REPOSITORY`.
5. Run the trigger manually once and review the build log and Cloud Run
  revision before enabling automatic pushes.

Keep the FastAPI trigger separate. `cloudbuild.sales.yaml` currently contains
the placeholders `PROJECT:REGION:INSTANCE` and
`https://kalisoft-sales-HASH.a.run.app`; replace and test those values before
using that pipeline.

After a successful trigger, verify the revision and application diagnostics:

```bash
gcloud run revisions list --service sales-agent --region us-central1
gcloud run services describe sales-agent --region us-central1 \
  --format='value(status.url)'
```

An image build passing does not prove that database, GCS, Sheets, Gemini, and
email integrations work.

---

## 11. Rollback

Cloud Run keeps previous revisions:

```bash
gcloud run services update-traffic sales-agent \
  --to-revisions=sales-agent-<REVISION>=100 \
  --region us-central1
```

List revisions:

```bash
gcloud run revisions list --service sales-agent --region us-central1
```

---

## 12. Common problems and fixes

| Symptom | Fix |
|---|---|
| `ERROR: cloudrun.env.yaml not found` | Upload the file to `~/ai_pitch_agent/` (Cloud Shell ⋮ → Upload) |
| `ERROR: credentials.json missing AND no existing secret` | Upload `credentials.json`, or create the secret manually once |
| Login page loads but login POST fails (CSRF / 403) | Set `CSRF_TRUSTED_ORIGINS` to the service URL, redeploy |
| `/app/api/diagnostics/` shows `GOOGLE_CREDENTIALS_JSON` missing | Secret not mounted — check Secret Manager access for the runtime SA and re-deploy so `--set-secrets` applies |
| GCS check `ok: False` | Share bucket `kalisoft-contacts` with the service account in `credentials.json` |
| Sheets check `ok: False` | Share `GOOGLE_SHEET_ID` / `LINKEDIN_SHEET_ID` / `PITCH_SHEET_ID` with the service-account email |
| Database check `ok: False` | Verify `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_SSLMODE=require` (Neon is reachable over the internet) |
| `--allow-unauthenticated` = public | Intended: the home/login page is public; all `/app/*` pages are protected by `LoginRequiredMiddleware` + per-owner access controls |
| `bash deploy.sh` on Windows PowerShell | Use Git Bash / WSL / Cloud Shell. `deploy_sales.ps1` is for the separate FastAPI path and is not a Django counterpart. |
| FastAPI PowerShell deployment asks for a database URL but does not deploy it | The current script prompts for the value without creating the documented Secret Manager value; use the reviewed Bash path or fix the script before production use. |

---

## 13. Security notes

- **Never** commit `cloudrun.env.yaml`, `credentials.json`, `.env`, or any file
  containing real passwords/API keys. They are gitignored and dockerignored.
- Rotate keys via Secret Manager:
  `gcloud secrets versions add google-app-credentials --data-file=credentials.json`
  then redeploy. Old versions are retained until you destroy them.
- The exposed `DJANGO_SECRET_KEY` in the env file signs sessions — rotate it to
  any long random string when desired (invalidates active sessions).
- The config currently uses `APP_PASSWORD` (the admin app password) directly in
  the env file — move it to Secret Manager (`--set-secrets`) for tighter
  control if this app is shared with other developers.

## 14. FastAPI security and data-governance checklist

The FastAPI service now enforces these application-level controls:

- Production rejects default or short JWT secrets, rejects `AUTH_DEV_MODE`,
  requires Google OAuth configuration, and requires explicit CORS and host
  allowlists.
- Cloud Run responses include `nosniff`, frame denial, referrer, permissions,
  CSP, and production HSTS headers. Production API docs are disabled.
- Requests are limited to `MAX_REQUEST_BYTES`; sign-in and API rate limits are
  enabled by the FastAPI Cloud Build config. Use Cloud Armor for distributed
  rate limiting and WAF rules across Cloud Run instances.
- Authenticated API routes use bearer JWTs and user-scoped database queries.
  GCS imports cannot read outside `GCS_PATH_CONTACTS`.
- Contact, email, and outbound-message fields have bounded sizes. Mailbox
  passwords are encrypted with a key derived from `SECRET_KEY` and are never
  returned by the API.

Before production release in GCP, verify:

1. Secret Manager contains `SALES_SECRET_KEY`, `SALES_DATABASE_URL`,
   `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GEMINI_API_KEY`; no secret
   is placed in Git, a Docker layer, or Cloud Build substitutions.
2. The Cloud Run runtime service account has only the required Secret Manager,
   Cloud SQL, and GCS permissions. The build service account is separate from
   the runtime identity and uses Service Account User only for the target
   runtime account.
3. Cloud SQL uses private IP or the Cloud SQL connector where available,
   automated backups, point-in-time recovery, deletion protection, and an
   appropriate maintenance window. Do not use local SQLite in production.
4. GCS bucket access is uniform bucket-level IAM, public access prevention is
   enabled, object versioning/retention is set to the organization policy, and
   the bucket is not broader than the contacts data domain.
5. Cloud Audit Logs are enabled for Admin Activity and Data Access where
   required by policy. Export security-relevant logs to a restricted log sink
   with a defined retention period.
6. Cloud Armor protects the public Cloud Run URL, and the OAuth consent/client
   configuration restricts the authorized JavaScript origins and redirect
   origins to the real application domains.
7. Data retention, deletion, export, and incident-response procedures are
   defined for contacts, email metadata, and GCS objects. Application access
   controls do not replace organization-level GDPR or privacy review.

Use `/api/health` for unauthenticated liveness only. Use the authenticated
`/api/integrations` endpoint for integration verification, and do not expose
secret values in health responses or logs.