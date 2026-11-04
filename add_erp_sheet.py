"""Add '13_ERP_Sync_Forecast' to the dashboard Excel and push to GCS."""
import json, os
import google.auth
from google.cloud import storage
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

BASE = os.path.dirname(os.path.abspath(__file__))
XLSX = os.path.join(BASE, "Kalika_Dashboard_Summary_v2.xlsx")
GCS_DEST = "sales-metadata/Kalika_Dashboard_Summary.xlsx"

HDR_FILL = PatternFill("solid", fgColor="1F4E79")
HDR_FONT = Font(color="FFFFFF", bold=True, size=11)
TITLE_FONT = Font(bold=True, size=14, color="1F4E79")
SUB_FONT = Font(bold=True, size=11, color="2E74B5")
THIN = Border(*[Side(style="thin", color="BFBFBF")] * 4)
WRAP = Alignment(vertical="top", wrap_text=True)

wb = load_workbook(XLSX)
if "13_ERP_Sync_Forecast" in wb.sheetnames:
    del wb["13_ERP_Sync_Forecast"]
ws = wb.create_sheet("13_ERP_Sync_Forecast")


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


ws.cell(row=1, column=1, value="ERP SYNC, FORECAST & YOUTUBE — 30-Oct-2026").font = TITLE_FONT
ws.cell(row=2, column=1, value="Source: gs://kalika_enterprises/ERP-V1/Reports (Dispatch + Orders) | ERP app (D:\\KaliSoftAI\\ERP-System, branch master) untouched | crons: erp_dispatch_sync 06:00, youtube_channel_sync 07:00").font = Font(italic=True, size=9, color="808080")
r = 4

r = table(r, ["Metric", "Value", "Notes"], [
    ["Report date", "2026-10-30", "latest ERP workbook"],
    ["Dispatch records", 117, "73 Completed · 44 Partially Dispatched"],
    ["Scheduled / dispatched qty", "69,538 / 46,405", "66.7% completion"],
    ["Customers served", 52, "distinct dispatch customers"],
    ["Orders", 89, "₹94.83 L total value"],
    ["Pending follow-up", 44, "partially dispatched records"],
    ["Top customer (dispatch qty)", "WHITE POLLY — 7,473", "then BROSLINESS 3,500 · ASMITA 2,495"],
    ["Rate calc sample", "500mm x 1000m x 23µm @ ₹92/kg", "10.58 kg · cost ₹1,187.08 · price ₹1,282.04 (₹118.8/kg)"],
])

ws.cell(row=r, column=1, value="ERP API ENDPOINTS").font = SUB_FONT; r += 1
r = table(r, ["Method", "Endpoint", "Access", "Purpose"], [
    ["GET", "/api/erp/status", "user", "KPIs, report date, last sync, admin flag, YouTube config"],
    ["POST", "/api/erp/sync", "admin", "Pull latest report from GCS → upsert Dispatch + Orders"],
    ["GET", "/api/erp/dispatch", "user", "Dispatch rows (status filter, limit)"],
    ["GET", "/api/erp/orders", "user", "Order rows (status filter, value sorted)"],
    ["GET", "/api/erp/forecast", "user", "Monthly series + next-month projection"],
    ["GET", "/api/erp/analytics", "user", "GA-style funnel, top customers, plants, pending"],
    ["POST", "/api/erp/rate-calculator", "user", "Film costing (weight → price)"],
    ["GET/PUT", "/api/erp/settings", "admin", "YouTube API key + channel id (DB or env)"],
    ["GET", "/api/erp/youtube/status", "user", "Configured flag + cached channel stats"],
    ["POST", "/api/erp/youtube/sync", "admin", "YouTube Data API v3 channels fetch"],
])

ws.cell(row=r, column=1, value="ROLES & CRONS").font = SUB_FONT; r += 1
r = table(r, ["Item", "Detail", "Status"], [
    ["Admin", "ai.solutions@kalisoftai.in (ADMIN_EMAILS) — sync, settings, youtube", "active"],
    ["Field executive / sales", "read-only dashboards, dispatch, forecast, calculator", "active"],
    ["ERP users", "untouched — continue on ERP branch master", "unchanged"],
    ["erp_dispatch_sync", "0 6 * * * — daily ERP report → DB", "active"],
    ["youtube_channel_sync", "0 7 * * * — Data API stats refresh", "active"],
    ["YouTube Analytics API", "needs OAuth consent + token storage", "next scope"],
    ["Graph/RL event patterns", "events.jsonl → networkx → pattern reports in UI stories", "next scope"],
])
for i, w in enumerate([30, 46, 62], start=1):
    ws.column_dimensions[get_column_letter(i)].width = w

order = ["1_Dashboard_Overview", "2_Contacts_Summary", "3_Call_Status_Followups", "4_Sales_2026_Monthly",
         "5_Top_Customers_Products", "6_ERP_Dispatch_Orders", "7_Product_Rate_List", "8_WhatsApp_Data",
         "9_API_Details_Features", "10_Data_Sources_GCS", "11_Crons_Sync", "12_Graph_Preprocessing",
         "13_ERP_Sync_Forecast"]
wb._sheets = [wb[n] for n in order if n in wb.sheetnames]

wb.save(XLSX)
print("Excel updated:", XLSX)

creds, _ = google.auth.default()
blob = storage.Client(credentials=creds).bucket("kalika_enterprises").blob(GCS_DEST)
blob.upload_from_filename(XLSX)
print(f"Pushed to gs://kalika_enterprises/{GCS_DEST} ({os.path.getsize(XLSX)} bytes)")
