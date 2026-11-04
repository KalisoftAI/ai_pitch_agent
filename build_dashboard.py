"""Build Kalika Enterprises dashboard-summary Excel from analysis.json + whatsapp analysis."""
import json, os
import pandas as pd
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

BASE = os.path.dirname(os.path.abspath(__file__))
A = json.load(open(os.path.join(BASE, "analysis.json"), encoding="utf-8"))
W = json.load(open(os.path.join(BASE, "whatsapp_orders_analysis.json"), encoding="utf-8"))
OUT = os.path.join(BASE, "Kalika_Dashboard_Summary.xlsx")

HDR_FILL = PatternFill("solid", fgColor="1F4E79")
HDR_FONT = Font(color="FFFFFF", bold=True, size=11)
TITLE_FONT = Font(bold=True, size=14, color="1F4E79")
SUB_FONT = Font(bold=True, size=11, color="2E74B5")
KPI_FILL = PatternFill("solid", fgColor="DDEBF7")
THIN = Border(*[Side(style="thin", color="BFBFBF")] * 4)


def write_df(ws, df, start_row, start_col=1, header=True):
    r = start_row
    if header:
        for j, col in enumerate(df.columns):
            c = ws.cell(row=r, column=start_col + j, value=str(col))
            c.fill = HDR_FILL; c.font = HDR_FONT; c.border = THIN
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        r += 1
    for _, row in df.iterrows():
        for j, v in enumerate(row):
            if isinstance(v, float):
                v = round(v, 2)
            c = ws.cell(row=r, column=start_col + j, value=v)
            c.border = THIN
            c.alignment = Alignment(vertical="top", wrap_text=True)
        r += 1
    return r


def autowidth(ws, max_w=55):
    for col in ws.columns:
        letter = get_column_letter(col[0].column)
        width = 10
        for cell in col:
            if cell.value is not None:
                width = max(width, min(max_w, len(str(cell.value)) + 2))
        ws.column_dimensions[letter].width = width


def title(ws, text, row=1, sub=None):
    ws.cell(row=row, column=1, value=text).font = TITLE_FONT
    r = row + 1
    if sub:
        ws.cell(row=r, column=1, value=sub).font = Font(italic=True, size=9, color="808080")
        r += 1
    return r + 1


with pd.ExcelWriter(OUT, engine="openpyxl") as xw:
    wb = xw.book

    # ---------------------------------------------------------- 1. OVERVIEW
    ws = wb.create_sheet("1_Dashboard_Overview")
    r = title(ws, "KALIKA ENTERPRISES — SALES & MARKETING DATA DASHBOARD (High-Level Summary)",
              sub=f"Source: gs://kalika_enterprises | Generated from live GCS data on 30-Oct-2026 | Auth: ADC (gcloud application-default)")
    kpis = [
        ("TOTAL CONTACT RECORDS (all lists)", "≈ 2,260 rows across 3 contact files / 11 sheets", "marketing_list_kalika (517 dedup + 152 main + 1126 sheet1), pune region (78+33+43+113+22), Sales-data (111+49+113)"),
        ("UNIQUE PHONE NUMBERS (marketing list)", A["contacts"]["marketing_list_kalika"]["unique_phones_overall"], "deduplicated 10+ digit numbers across sheets"),
        ("UNIQUE EMAIL IDs (marketing list)", A["contacts"]["marketing_list_kalika"]["unique_emails_overall"], "deduplicated emails incl. purchase-dept emails"),
        ("REQUIREMENTS LOGGED", 91 + 29 + 46, "marketing dedup 91 + main list 29 + pune sheet1 46"),
        ("FOLLOW-UPS LOGGED", 76 + 76 + 23 + 13, "pune sheet1 76, gadekar sir 76, sheet2 23, sheet11 13"),
        ("TOTAL SALES INVOICES (Jan–Sep 2026)", A["sales_2026"]["total_invoices"], "9 monthly Tally sales registers parsed"),
        ("TOTAL SALES VALUE (GROSS)", f"₹ {A['sales_2026']['total_gross']/1e7:,.2f} Cr", f"taxable ₹ {A['sales_2026']['total_taxable']/1e7:,.2f} Cr"),
        ("ACTIVE CUSTOMERS (sales 2026)", A["sales_2026"]["unique_customers"], "unique buyer names in registers"),
        ("ERP OPEN/PIPELINE ORDERS", A["erp_latest"]["sheets"]["Orders"]["rows"], f"value ₹ {A['erp_latest']['sheets']['Orders']['total_value']/1e5:,.1f} L | status: " + ", ".join(f"{k}:{v}" for k, v in A["erp_latest"]["sheets"]["Orders"]["status"].items())),
        ("DISPATCH RECORDS (latest report)", A["erp_latest"]["sheets"]["Dispatch"]["rows"], f"avg completion {A['erp_latest']['sheets']['Dispatch']['avg_completion_pct']*100:.1f}% | 73 completed, 44 partial"),
        ("WHATSAPP CHAT EXPORTS", 48, "~137.5 MB | internal order group 429 msgs (Nov-24 → Oct-26)"),
        ("PRODUCT RATE LIST ITEMS", len(A["contacts"]["pune_region_contacts"]["products_rate_list"]), "VCI bags, stretch film, BOPP tape, gloves, polybags with current rates"),
    ]
    df = pd.DataFrame(kpis, columns=["Metric", "Value", "Notes / Source"])
    r = write_df(ws, df, r)
    autowidth(ws)

    # ---------------------------------------------------------- 2. CONTACTS SUMMARY
    ws = wb.create_sheet("2_Contacts_Summary")
    r = title(ws, "CONTACT DATABASE — STRUCTURE & STATS", sub="All contact lists under gs://kalika_enterprises/sales-contacts/")
    C = A["contacts"]
    rows = [
        ["marketing_list_kalika (1).xlsx", "removed duplicates - mail list", "517 rows", "514 names, 266 phones, 239 emails, 167 addresses", "168 categorized, 174 call-status entries, 91 requirements"],
        ["marketing_list_kalika (1).xlsx", "main list", "152 companies", "110 contacts, 24 purchase-dept contacts, 56 emails, 77 purchase-dept emails, 81 websites", "64 categorized, 74 call-status, 29 requirements, 66 source URLs"],
        ["marketing_list_kalika (1).xlsx", "Sheet1", "1,126 rows", "1,126 names, 106 phones, 96 emails", "raw compiled list"],
        ["marketing_list_kalika (1).xlsx", "Sheet3 (daily calling log)", "10 days", "21-Oct: 51 calls/31 answered; 22-Oct: 64 calls/46 answered/29 details sent", "1 quotation sent 21-Oct, 1 on 22-Oct"],
        ["pune region contacts (1).xlsx", "Sheet1", "78 companies", "77 phones, 77 emails, full addresses", "34 call-status, 46 requirements, 76 follow-ups"],
        ["pune region contacts (1).xlsx", "Sheet2", "33 companies", "32 contacts, 32 phones, 32 emails, 25 websites", "15 call-status, 23 follow-ups"],
        ["pune region contacts (1).xlsx", "gadekar sir contacts", "113 rows", "36 named contacts with phones", "76 follow-up report lines"],
        ["pune region contacts (1).xlsx", "packvision contacts", "43 rows", "expo leads (Packvision)", "42 rows filled"],
        ["pune region contacts (1).xlsx", "Sheet11 (requirement tracker)", "22 companies", "requirement + follow-up type tracking", "13 follow-ups; statuses: Details sent / Not answered / No requirement"],
        ["pune region contacts (1).xlsx", "Products details", "13 products", "specs + current rates", "rate list — see sheet 7"],
        ["Sales-data.xlsx", "Packvision", "111 rows", "83 companies, 87 names, 111 phones, 44 emails", "19 call-status entries"],
        ["Sales-data.xlsx", "out-off-state", "49 rows", "out-of-state company details", "—"],
        ["Sales-data.xlsx", "sales-person1", "113 rows", "36 contacts, 36 phones", "76-line calling & follow-up report (38 companies contacted)"],
    ]
    df = pd.DataFrame(rows, columns=["File", "Sheet", "Size", "Contact Details Present", "Follow-up / Status Info"])
    r = write_df(ws, df, r)
    ws.cell(row=r + 1, column=1, value="Patterns observed: high share of 'invalid number' & 'not answered' in cold lists; follow-up tracking exists but scattered across sheets; purchase-dept emails captured separately in main list (77).").font = Font(italic=True, size=9)
    autowidth(ws)

    # ---------------------------------------------------------- 3. CALL STATUS & FOLLOW-UPS
    ws = wb.create_sheet("3_Call_Status_Followups")
    r = title(ws, "CALLING ACTIVITY, STATUS DISTRIBUTION & FOLLOW-UPS")
    def norm_status(d):
        norm = {}
        for k, v in d.items():
            k2 = k.strip().lower()
            if "invalid" in k2 or "wrong" in k2: k2 = "invalid/wrong number"
            elif "not answered" in k2 or "not received" in k2: k2 = "not answered"
            elif "busy" in k2: k2 = "busy now"
            elif "switch" in k2: k2 = "switched off"
            elif "call later" in k2 or "later" in k2: k2 = "call later"
            elif "not interested" in k2 or "no requirement" in k2 or "no req" in k2: k2 = "not interested / no requirement"
            elif "details" in k2 or "mail" in k2 or "catalog" in k2: k2 = "details/catalog sent"
            elif "unavailable" in k2 or "not available" in k2 or "out of service" in k2: k2 = "unavailable/out of service"
            elif "meeting" in k2: k2 = "in meeting - call later"
            norm[k2] = norm.get(k2, 0) + v
        return norm
    combined = {}
    for src in [C["marketing_list_kalika"]["dedup_list"]["call_status"],
                C["marketing_list_kalika"]["main_list"]["call_status"],
                C["pune_region_contacts"]["sheet1"]["call_status"],
                C["pune_region_contacts"]["sheet2"]["call_status"],
                C["sales_data_file"]["packvision"]["call_status"]]:
        n = norm_status(src)
        for k, v in n.items():
            combined[k] = combined.get(k, 0) + v
    df = pd.DataFrame(sorted(combined.items(), key=lambda x: -x[1]), columns=["Call Outcome (normalized)", "Count (all lists combined)"])
    r = write_df(ws, df, r)
    r += 1
    ws.cell(row=r, column=1, value="Sample follow-up report entries (sales-person1 / gadekar sir):").font = SUB_FONT; r += 1
    for sline in C["sales_data_file"]["sales_person1"]["followup_samples"]:
        ws.cell(row=r, column=1, value=sline); r += 1
    autowidth(ws)

    # ---------------------------------------------------------- 4. SALES MONTHLY
    ws = wb.create_sheet("4_Sales_2026_Monthly")
    r = title(ws, "ACTUAL SALES 2026 — MONTHLY REGISTER SUMMARY", sub="Source: gs://kalika_enterprises/kalika_sales2026/ (Tally 'Sales Register' exports)")
    df = pd.DataFrame(A["sales_2026"]["monthly"])
    df["taxable_value"] = df["taxable_value"].round(0)
    df["gross_total"] = df["gross_total"].round(0)
    df.columns = ["Month", "Invoices", "Unique Customers", "Taxable Value (₹)", "Gross Total (₹)", "Line Items*"]
    r = write_df(ws, df, r)
    tot = pd.DataFrame([["TOTAL", A["sales_2026"]["total_invoices"], A["sales_2026"]["unique_customers"],
                         round(A["sales_2026"]["total_taxable"]), round(A["sales_2026"]["total_gross"]), "—"]],
                       columns=df.columns)
    r = write_df(ws, tot, r, header=False)
    ws.cell(row=r + 1, column=1, value="* Jan–Mar registers are itemized; Apr–Sep registers are invoice-level (one row per invoice). Payment terms: 45 Days (859), 60 Days (384), 40 Days (308), 30 Days (80), 15 Days (37).").font = Font(italic=True, size=9)
    autowidth(ws)

    # ---------------------------------------------------------- 5. TOP CUSTOMERS & PRODUCTS
    ws = wb.create_sheet("5_Top_Customers_Products")
    r = title(ws, "TOP CUSTOMERS (by gross value, Jan–Sep 2026)")
    df = pd.DataFrame(A["sales_2026"]["top_customers"])
    df["gross"] = df["gross"].round(0)
    df.columns = ["Customer", "Gross Value (₹)"]
    r = write_df(ws, df, r)
    r += 1
    ws.cell(row=r, column=1, value="TOP PRODUCTS (itemized registers Jan–Mar 2026)").font = SUB_FONT; r += 1
    tp = [p for p in A["sales_2026"]["top_products"] if p["item"] != "Grand Total"]
    df = pd.DataFrame(tp)
    df["value"] = df["value"].round(0)
    df.columns = ["Product / Item", "Sales Value (₹)"]
    r = write_df(ws, df, r)
    autowidth(ws)

    # ---------------------------------------------------------- 6. ERP DISPATCH & ORDERS
    ws = wb.create_sheet("6_ERP_Dispatch_Orders")
    r = title(ws, "ERP-V1 LATEST REPORT (30-Oct-2026) — ORDERS, DISPATCH, PRODUCTION, INVENTORY",
              sub="Source: gs://kalika_enterprises/ERP-V1/Reports/kalika_report_2026-10-30.xlsx")
    E = A["erp_latest"]["sheets"]
    rows = [
        ["Orders", E["Orders"]["rows"], f"₹ {E['Orders']['total_value']/1e5:,.1f} L total value", "; ".join(f"{k}: {v}" for k, v in E["Orders"]["status"].items()), f"{E['Orders']['unique_customers']} customers, {E['Orders']['with_required_date']} with required-date"],
        ["Dispatch", E["Dispatch"]["rows"], f"qty {E['Dispatch']['total_dispatched_qty']:,.0f} / {E['Dispatch']['total_scheduled_qty']:,.0f} dispatched", "; ".join(f"{k}: {v}" for k, v in E["Dispatch"]["status"].items()), f"avg completion {E['Dispatch']['avg_completion_pct']*100:.1f}% | {E['Dispatch']['unique_customers']} customers"],
        ["Production", E["Production"]["rows"], "—", "; ".join(f"{k}: {v}" for k, v in E["Production"]["status"].items()), f"avg completion {E['Production']['avg_completion_pct']*100:.1f}%"],
        ["Inventory", E["Inventory"]["rows"], "—", "; ".join(f"{k}: {v}" for k, v in E["Inventory"]["categories"].items()), "; ".join(f"{k}: {v}" for k, v in E["Inventory"]["plants"].items())],
        ["Purchases", E["Purchases"]["rows"], f"₹ {E['Purchases']['total_amount']/1e5:,.1f} L", "; ".join(f"{k}: {v}" for k, v in E["Purchases"]["status"].items()), f"{E['Purchases']['unique_suppliers']} suppliers"],
        ["Customers", E["Customers"]["rows"], "—", "master data", "—"],
        ["Suppliers", E["Suppliers"]["rows"], "—", "master data", "—"],
        ["Products", E["Products"]["rows"], "—", "master data (models/categories/UOM)", "—"],
    ]
    df = pd.DataFrame(rows, columns=["Module", "Records", "Value", "Status Breakdown", "Notes"])
    r = write_df(ws, df, r)
    ws.cell(row=r + 1, column=1, value="Dispatch process: Order → Production → Dispatch plant → Customer. 44 dispatches partially completed = follow-up opportunity list for the dashboard.").font = Font(italic=True, size=9)
    autowidth(ws)

    # ---------------------------------------------------------- 7. RATE LIST
    ws = wb.create_sheet("7_Product_Rate_List")
    r = title(ws, "CURRENT PRODUCT RATE LIST", sub="Source: pune region contacts (1).xlsx / Products details")
    df = pd.DataFrame(A["contacts"]["pune_region_contacts"]["products_rate_list"], columns=["Product", "Specifications / Sizes", "Rate"])
    r = write_df(ws, df, r)
    autowidth(ws)

    # ---------------------------------------------------------- 8. WHATSAPP
    ws = wb.create_sheet("8_WhatsApp_Data")
    r = title(ws, "WHATSAPP SALES DATA — CHAT INVENTORY & ORDER-GROUP PATTERNS",
              sub="Source: gs://kalika_enterprises/kalika backup/ (48 chat exports, ~137.5 MB, uploaded 30-Oct-2026)")
    rows = [
        ["Total chat exports (zip)", 48, "individual customer/supplier/internal chats"],
        ["Internal order group messages", W["total_messages"], f"'{W['chat']}' | {W['date_range']['first']} → {W['date_range']['last']} | {W['active_days']} active days"],
        ["Order-related messages", W["keyword_patterns"].get("order", 0), "order placement, urgent orders, PO references"],
        ["Quantity mentions", W["keyword_patterns"].get("quantity", 0), "kg / boxes / pcs / cartons / rolls"],
        ["Follow-up messages", W["keyword_patterns"].get("follow-up", 0), "reminders, 'tomorrow', pending checks, @mentions to team"],
        ["Dispatch/delivery msgs", W["keyword_patterns"].get("dispatch/delivery", 0), "dispatch confirmations, TATA dispatch checks, transport refs"],
        ["Rate/price msgs", W["keyword_patterns"].get("rate/price", 0), "rate revision, tarpaulin rate requests"],
        ["Payment msgs", W["keyword_patterns"].get("payment", 0), "PI received / make payment"],
        ["Key participants", "—", "; ".join(f"{k} ({v})" for k, v in list(W["participants"].items())[:6])],
    ]
    df = pd.DataFrame(rows, columns=["Metric", "Value", "Detail"])
    r = write_df(ws, df, r)
    r += 1
    ws.cell(row=r, column=1, value="Sample real messages (orders / follow-ups / dispatch / rates):").font = SUB_FONT; r += 1
    for cat in ["order", "follow-up", "dispatch/delivery", "rate/price"]:
        for sline in W["samples"].get(cat, [])[:4]:
            ws.cell(row=r, column=1, value=sline); r += 1
    autowidth(ws)

    # ---------------------------------------------------------- 9. API DETAILS
    ws = wb.create_sheet("9_API_Details_Features")
    r = title(ws, "CURRENT APP — API DETAILS, FEATURES & APPLICATIONS",
              sub="Source: gs://kalika_enterprises/sales-metadata/Kalika_Real_Time_Customer_Feedback_System.md (updated 30-Oct-2026)")
    apis = [
        ["Feedback Collection API", "Capture star ratings, category & comments from QR/WhatsApp flows", "Delivery/product/service feedback types; conditional follow-up questions; rating scale; optional comments; duplicate-submission handling", "Post-delivery surveys; product quality tracking; general suggestions"],
        ["Complaint / Ticket Management API", "Create, route, track support tickets end-to-end", "Ticket ID, priority, assignment, status flow (Open→Assigned→In Progress→Resolved→Closed/Reopened), timestamps for first response & resolution, attachments/photos", "Issue reporting; resolution tracking; escalation; SLA monitoring"],
        ["QR Code Service", "Unique QR entry points per placement type", "General / Delivery / Product QR types; secure order references (no personal data in URLs); source identifiers for analytics", "Invoices, challans, product labels, brochures, reception"],
        ["WhatsApp Business Messaging", "Interactive customer conversations", "Approved templates; interactive buttons/lists; 7 ready message flows (welcome, delivery, product feedback, issue, catalogue, suggestion, thank-you); opt-in/opt-out consent; reminder limits (1 reminder after 24–48h)", "Customer engagement; automated follow-ups; notifications"],
        ["ERP Integration / Lookup API", "Fetch customer, order, product, delivery data from Kalika ERP", "Order/invoice reference lookup; live price/stock/delivery estimates; stable references; retry-safe; audit trail", "Auto-identify order from scan; verified pricing in messages; dispatch-triggered messages"],
        ["Catalogue API", "Serve product catalogue to customers", "13 product categories (stretch/shrink film, BOPP & masking tape, VCI bags/boxes, tarpaulin, HDPE/poly bags & boxes, shade net, gloves, sleeves, straps & buckles); images + specs from catalogue; enquiry & quotation request actions", "Mobile product browsing; enquiry generation; sales-assist"],
        ["Notification / Alert API", "Internal team alerts & customer status updates", "Low-rating alerts to quality/sales; delivery complaints to dispatch; repeated-complaint flagging; unassigned-complaint supervisor alerts; resolved-ticket follow-up", "Team routing; supervisor escalation; customer status notifications"],
        ["Analytics / Dashboard API", "Management dashboard data", "KPIs: avg rating, rating distribution, feedback volume, complaints by product/category, open/resolved tickets, time-to-first-response, time-to-resolution, improvement-category frequency, QR scan vs submission rate; filters (date, product, source, team, status); export", "Management reporting; quality improvement; delivery performance tracking"],
    ]
    df = pd.DataFrame(apis, columns=["API / Module", "Purpose / Description", "Key Features", "Applications"])
    r = write_df(ws, df, r)
    r += 1
    ws.cell(row=r, column=1, value="Recommended stack: React/Next.js frontend, Django REST / FastAPI backend, PostgreSQL DB, WhatsApp Business Platform, QR with secure refs. Roadmap: Phase 1 Feedback MVP → Phase 2 Workflow Automation (WhatsApp + ERP lookup) → Phase 3 Customer Intelligence (trends, recurring-complaint detection).").font = Font(italic=True, size=9, )
    ws.cell(row=r + 1, column=1).alignment = Alignment(wrap_text=True)
    ws.row_dimensions[r + 1].height = 30
    autowidth(ws)

    # ---------------------------------------------------------- 10. DATA SOURCES
    ws = wb.create_sheet("10_Data_Sources_GCS")
    r = title(ws, "GCS DATA SOURCE MAP", sub="Bucket: gs://kalika_enterprises")
    rows = [
        ["Marketing contacts (Vishal.K updated)", "sales-contacts/marketing_list_kalika (1).xlsx", "Contact lists", "517+152+1126 rows; call status; requirements", "Marketing Experts", "Updated 30-Oct-2026"],
        ["Pune region contacts", "sales-contacts/pune region contacts (1).xlsx", "Contact lists + rates", "78+33 companies; gadekar sir (113); packvision (43); 13-product rate list", "Marketing Experts (Gadekar sir, Packvision)", "Updated 29-Oct-2026"],
        ["Sales-data (out-of-state, Packvision, sales-person1)", "sales-contacts/Sales-data.xlsx", "Contact lists + follow-ups", "111 Packvision rows; 49 out-of-state; 76-line follow-up report", "Marketing Experts", "Updated 29-Oct-2026"],
        ["ERP dispatch/delivery reports", "ERP-V1/Reports/kalika_report_2026-10-28.xlsx & 2026-10-30.xlsx", "ERP-APP-Delivery-data", "Inventory, Production, Dispatch, Orders, Purchases, Customers, Suppliers, Products", "ERP app (daily report)", "Latest 30-Oct-2026"],
        ["WhatsApp sales data samples", "kalika backup/ (48 chat zips + PDFs)", "WhatsApp chat exports", "Follow-ups, order updates, rates; internal order group 429 msgs", "Kalika marketing mobiles", "Backed up 30-Oct-2026"],
        ["Actual sales data", "kalika_sales2026/ (9 monthly .xls registers)", "Sales data (Tally)", "5,149 invoices; ₹27.58 Cr gross; 124 customers; Jan–Sep 2026", "Accounts/Tally", "Jan–Sep 2026"],
        ["App feature & API spec", "sales-metadata/Kalika_Real_Time_Customer_Feedback_System.md", "System design doc", "Feedback system: QR flows, 7 WhatsApp templates, ticket workflow, dashboard KPIs, roadmap", "Product/Engineering", "Updated 30-Oct-2026"],
    ]
    df = pd.DataFrame(rows, columns=["Data Area", "GCS Path", "Type", "Key Contents", "Owner / Source", "Freshness"])
    r = write_df(ws, df, r)
    autowidth(ws)

    # remove default sheet
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]

print("Saved:", OUT)
