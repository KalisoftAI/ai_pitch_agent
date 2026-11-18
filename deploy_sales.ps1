# Cloud Run deployment (PowerShell) for the FastAPI sales pipeline.
# Usage:  ./deploy_sales.ps1 -ProjectId my-proj -CloudSqlInstance my-proj:asia-south1:sales-db -GmailAddressKalisoftAI ai.solutions@kalisoftai.in -GmailAddressKalika kalikaenterprises@gmail.com
param(
  [string]$ProjectId = "",
  [string]$Region = "asia-south1",
  [string]$Service = "kalisoft-sales",
  [string]$CloudSqlInstance = "",
  [string]$Bucket = "kalisoftai-datahub",
  [string]$ContactsPath = "all-sales-contacts-data",
  [string]$CorsOrigins = "*",
  [string]$GmailAddressKalisoftAI = "",
  [string]$GmailAddressKalika = "",
  [string]$GmailAddressKalika2 = ""
)

if (-not $ProjectId) { $ProjectId = (gcloud config get-value project) }
Write-Host "Project: $ProjectId  Region: $Region  Service: $Service"

if (-not $GmailAddressKalisoftAI) { $GmailAddressKalisoftAI = $env:GMAIL_ADDRESS_KALISOFTAI }
if (-not $GmailAddressKalika) { $GmailAddressKalika = $env:GMAIL_ADDRESS_KALIKA }
if (-not $GmailAddressKalika2) { $GmailAddressKalika2 = $env:GMAIL_ADDRESS_KALIKA2 }
foreach ($gmail in @(
    @{ Name = "GmailAddressKalisoftAI"; Value = $GmailAddressKalisoftAI },
    @{ Name = "GmailAddressKalika"; Value = $GmailAddressKalika },
    @{ Name = "GmailAddressKalika2"; Value = $GmailAddressKalika2 }
)) {
  if ([string]::IsNullOrWhiteSpace($gmail.Value) -or $gmail.Value -notmatch "@") {
    throw "Required Gmail address is missing or invalid: $($gmail.Name)"
  }
}
foreach ($secretName in @("GMAIL_APP_PASSWORD_KALISOFTAI", "GMAIL_APP_PASSWORD_KALIKA", "GMAIL_APP_PASSWORD_KALIKA2")) {
  gcloud secrets versions access latest --secret $secretName --project $ProjectId > $null 2>&1
  if ($LASTEXITCODE -ne 0) { throw "Required Secret Manager secret is not accessible: $secretName" }
}

gcloud services enable run.googleapis.com cloudbuild.googleapis.com `
  secretmanager.googleapis.com sqladmin.googleapis.com storage.googleapis.com `
  --project $ProjectId

$sa = "kalisoft-sales-run@$ProjectId.iam.gserviceaccount.com"
gcloud iam service-accounts create kalisoft-sales-run `
  --display-name "Kalisoft Sales Cloud Run" --project $ProjectId 2>$null
gcloud storage buckets add-iam-policy-binding "gs://$Bucket" `
  --member="serviceAccount:$sa" --role="roles/storage.objectAdmin" 2>$null
gcloud projects add-iam-policy-binding $ProjectId `
  --member="serviceAccount:$sa" --role="roles/cloudsql.client" 2>$null
foreach ($secretName in @("GMAIL_APP_PASSWORD_KALISOFTAI", "GMAIL_APP_PASSWORD_KALIKA", "GMAIL_APP_PASSWORD_KALIKA2")) {
  gcloud secrets add-iam-policy-binding $secretName `
    --member="serviceAccount:$sa" --role="roles/secretmanager.secretAccessor" --project $ProjectId 2>$null
}

$dbUrl = Read-Host "SALES_DATABASE_URL (postgresql+psycopg2://user:pass@/db?host=/cloudsql/$CloudSqlInstance)"

gcloud builds submit --config cloudbuild.sales.yaml `
  --substitutions="_REGION=$Region,_CLOUD_SQL_INSTANCE=$CloudSqlInstance,_CORS_ORIGINS=$CorsOrigins,_GMAIL_ADDRESS_KALISOFTAI=$GmailAddressKalisoftAI,_GMAIL_ADDRESS_KALIKA=$GmailAddressKalika,_GMAIL_ADDRESS_KALIKA2=$GmailAddressKalika2" `
  --project $ProjectId

gcloud run services describe $Service --region $Region --format="value(status.url)"
