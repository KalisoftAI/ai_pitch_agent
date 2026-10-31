"""Add '14_Sales_Deploy_UAT' sheet to the dashboard Excel + push; also push the runbook."""
import os
import google.auth
from google.cloud import storage
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

BASE = os.path.dirname(os.path.abspath(__file__))
XLSX = os.path.join(BASE, "Kalika_Dashboard_Summary_v2.xlsx")
GCS_XLSX = "sales-metadata/Kalika_Dashboard_Summary.xlsx"
RUNBOOK = os.path.join(BASE, "Kalika_Sales_Deploy_UAT_Runbook.md")

HDR_FILL = PatternFill("solid", fgColor="1F4E79")
HDR_FONT = Font(color="FFFFFF", bold=True, size=11)
TITLE_FONT = Font(bold=True, size=14, color="1F4E79")
SUB_FONT = Font(bold=True, size=11, color="2E74B5")
THIN = Border(*[Side(style="thin", color="BFBFBF")] * 4)
WRAP = Alignment(vertical="top", wrap_text=True)

wb = load_workbook(XLSX)
if "14_Sales_Deploy_UAT" in wb.sheetnames:
    del wb["14_Sales_Deploy_UAT"]
ws = wb.create_sheet("14_Sales_Deploy_UAT")


def table(r, headers, rows):
    for j, h in enumerate(headers):
        c = ws.cell(row=r, column=1 + j, value=h)
        c.fill = HDR_FILL; c.font = HDR_FONT; c.border = THIN
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    r += 1
    for row in rows:
        for j, v in enumerate(row):
            c = ws.cell(row=r, column=1 + j, value=v)
            c.border = THIN; c.alignment = WRAP
        r += 1
    return r + 1


ws.cell(row=1, column=1, value="SALES DEPLOY, GUARDRAILS & ERP-UAT — 30-Oct-2026").font = TITLE_FONT
ws.cell(row=2, column=1, value="Runbook: sales-metadata/Kalika_Sales_Deploy_UAT_Runbook.md | ERP master stays prod (read-only feed) | UAT until 2026-11-06").font = Font(italic=True, size=9, color="808080")
r = 4

r = table(r, ["Item", "Value", "Notes"], [
    ["Deploy readiness", "READY", "21 pass · 1 warn · 0 fail"],
    ["Env / phase", "preprod · ERP-UAT", "DEPLOY_ENV=preprod, UAT_ENABLED_UNTIL=2026-11-06 (7 days)"],
    ["Model default", "gemini-2.5-flash", "Google Flash; gemma-4-27b-it also available; HUMAN_REVIEW_REQUIRED=true"],
    ["Tests", "128 passing", "full suite (graph tests auto-skip without networkx on system python)"],
    ["Cron tasks", 17, "incl. daily_guardrail_checks 20:00 IST, daily_llm_prompt_refine 21:00, daily_uat_report 22:00"],
    ["Journey patterns", 4, "new_customer · repeat_customer · at_risk · high_value"],
    ["Prompt samples", "5 (PR-01..PR-05)", "gs://kalika_enterprises/sales-metadata/weekly_prompts.json"],
])

ws.cell(row=r, column=1, value="GUARDRAIL LAYERS").font = SUB_FONT; r += 1
r = table(r, ["Layer", "Checks", "Status"], [
    ["config", "deploy env, secret strength, dev-login posture", "pass"],
    ["security", "allowed hosts, CORS, body limit, PII redaction, audit log", "pass"],
    ["auth", "admin emails, Google sign-in", "pass"],
    ["data", "core tables, contacts loaded (8,795)", "pass"],
    ["erp", "dispatch synced (117) + report freshness (0 days)", "pass"],
    ["scheduler", "17 tasks + IST window present", "pass"],
    ["llm", "enabled (warn), flash + gemma models, human review", "1 warn"],
    ["uat", "window active, 7 days left", "pass"],
    ["storage", "GCS available", "pass"],
])

ws.cell(row=r, column=1, value="20:00-22:00 IST SCHEDULE (UTC = 14:30-16:30)").font = SUB_FONT; r += 1
r = table(r, ["Job", "IST", "UTC cron", "Purpose"], [
    ["erp_dispatch_sync", "06:00", "0 6 * * *", "ERP report → dispatch/orders"],
    ["youtube_channel_sync", "07:00", "0 7 * * *", "YouTube Data API stats"],
    ["daily_guardrail_checks", "20:00", "30 14 * * *", "preflight → sync_runs"],
    ["daily_llm_prompt_refine", "21:00", "30 15 * * *", "prompt refinement (human review)"],
    ["daily_uat_report", "22:00", "30 16 * * *", "UAT digest"],
    ["weekly_uat_review", "Mon 20:00", "30 14 * * 1", "weekly review + RL candidates"],
])

ws.cell(row=r, column=1, value="NEW ENDPOINTS").font = SUB_FONT; r += 1
r = table(r, ["Method", "Endpoint", "Access", "Purpose"], [
    ["GET", "/api/ops/preflight", "admin", "full guardrail check suite"],
    ["POST", "/api/ops/run-checks", "admin", "execute + persist checks to sync_runs"],
    ["GET", "/api/ops/uat", "user", "phase, window, enabled features"],
    ["GET", "/api/ops/models", "user", "model catalog + human review policy"],
    ["GET", "/api/ops/prompt-samples", "user", "weekly prompts JSON (local or GCS realtime)"],
    ["GET", "/api/ops/logs", "user", "model usage · audit · sync runs"],
    ["POST", "/api/journey/event", "user", "record journey event"],
    ["GET", "/api/journey/stories · behaviours · patterns · summary", "user", "journey analytics"],
    ["POST", "/api/erp/sync", "admin", "ERP dispatch/orders sync"],
    ["POST", "/api/erp/youtube/sync", "admin", "YouTube channel stats"],
])

ws.cell(row=r, column=1, value="UAT FEATURE ENABLEMENT (ONE WEEK)").font = SUB_FONT; r += 1
r = table(r, ["Feature", "Status"], [
    ["ERP dispatch + orders dashboards", "enabled"],
    ["Sales forecast", "enabled"],
    ["Daily rate calculator", "enabled"],
    ["Feedback pipeline (wa.me, human review)", "enabled"],
    ["Customer journey + stories", "enabled"],
    ["YouTube channel sync (Data API)", "enabled"],
    ["YouTube Analytics API (OAuth)", "next scope"],
    ["RL pattern suggestions", "next scope"],
])
for i, w in enumerate([30, 22, 24, 66], start=1):
    ws.column_dimensions[get_column_letter(i)].width = w

order = ["1_Dashboard_Overview", "2_Contacts_Summary", "3_Call_Status_Followups", "4_Sales_2026_Monthly",
         "5_Top_Customers_Products", "6_ERP_Dispatch_Orders", "7_Product_Rate_List", "8_WhatsApp_Data",
         "9_API_Details_Features", "10_Data_Sources_GCS", "11_Crons_Sync", "12_Graph_Preprocessing",
         "13_ERP_Sync_Forecast", "14_Sales_Deploy_UAT"]
wb._sheets = [wb[n] for n in order if n in wb.sheetnames]

wb.save(XLSX)
print("Excel updated:", XLSX)

creds, _ = google.auth.default()
bucket = storage.Client(credentials=creds).bucket("kalika_enterprises")
bucket.blob(GCS_XLSX).upload_from_filename(XLSX)
bucket.blob("sales-metadata/Kalika_Sales_Deploy_UAT_Runbook.md").upload_from_filename(RUNBOOK)
print(f"Pushed {GCS_XLSX} ({os.path.getsize(XLSX)} bytes) + runbook ({os.path.getsize(RUNBOOK)} bytes)")
