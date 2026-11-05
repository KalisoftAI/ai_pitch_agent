# Secrets Rotation Runbook

> Rotate any credential that was ever shared in a `.env` attachment or chat.
> Values are **never** stored in this repo. This is a procedure, not a place for secrets.

## 1. Where secrets live

| Layer | Location | Used by |
|-------|----------|---------|
| Runtime (prod/UAT/DEV) | GCP **Secret Manager** -> bound at deploy via `--update-secrets` | Cloud Run env `SECRET_KEY`, `DATABASE_URL`, optional `GEMINI_API_KEY`, `GOOGLE_CLIENT_SECRET`, `SMTP_PASSWORD` |
| CI/CD | GitHub **Actions secrets** | `GCP_SERVICE_ACCOUNT`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` |
| Non-secret config | GitHub **Actions variables** | `GCP_PROJECT_ID`, `GCP_REGION`, `CLOUD_SQL_INSTANCE`, `GCS_BUCKET`, `GCS_PATH`, `CORS_ORIGINS*`, `ALLOWED_HOSTS*`, `FRONTEND_URL*`, `GOOGLE_ALLOWED_DOMAINS` |

Project: `gen-lang-client-0132243782` . Region: `asia-south1`.

## 2. Rotate a Secret Manager secret (runtime)

```bash
# 1) create the new value (prompted, not echoed)
printf '%s' "NEW_VALUE" | gcloud secrets versions add SALES_SECRET_KEY \
  --project gen-lang-client-0132243782 --data-file=-

# 2) redeploy so Cloud Run picks :latest (push to main, or dispatch CD)
#    cd.yml binds SECRET_KEY=SALES_SECRET_KEY:latest, DATABASE_URL=SALES_DATABASE_URL:latest

# 3) confirm the app starts
curl -fsS https://kalisoft-sales-19782268668.asia-south1.run.app/api/health
```

`SALES_SECRET_KEY` rotation invalidates existing JWTs - users simply sign in again.

## 3. Rotate an optional secret

Same command with the matching name (`GEMINI_API_KEY`, `GOOGLE_CLIENT_SECRET`,
`SMTP_PASSWORD`). The deploy binds it **only if the secret exists**, so create it
first, then redeploy.

## 4. Rotate a GitHub Actions secret

```bash
gh secret set GOOGLE_CLIENT_ID --repo KalisoftAI/ai_pitch_agent   # prompts for value
gh secret set GOOGLE_CLIENT_SECRET --repo KalisoftAI/ai_pitch_agent
```

(If `gh` is unavailable, use GitHub UI: Settings -> Secrets and variables -> Actions.)

## 5. Checklist - rotate these now

- [ ] `SECRET_KEY` (JWT signing) - invalidates sessions
- [ ] `DATABASE_URL` password (Cloud SQL user) - update Secret Manager + SQL user
- [ ] `GEMINI_API_KEY`
- [ ] `GOOGLE_CLIENT_SECRET` (OAuth)
- [ ] `SMTP_PASSWORD` / `GMAIL_APP_PASSWORD` (Gmail app password)
- [ ] `WHATSAPP_API_KEY`, `WECHATY_GATEWAY_TOKEN`, `WECHATY_WEBHOOK_SECRET`
- [ ] `LINKEDIN_CLIENT_SECRET`, `REDDIT_CLIENT_SECRET`, SerpAPI key

## 6. After rotation

1. Verify `GET /api/health` -> `{"db":"ok",...}` and `GET /api/system/config` shows expected flags.
2. Confirm password login works; confirm no `AUTH_DEV_MODE` in prod.
3. Revoke/expire old provider credentials at the provider (Google Cloud, Gmail, Meta, etc.).
4. Do **not** commit `.env`; keep it in a password manager only.
