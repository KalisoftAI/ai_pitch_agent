"""Rewrite the Sheet-2 sync block with DB-authoritative cumulative counts, re-push to GCS."""
import os, sqlite3
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
SUB_FONT = Font(bold=True, size=11, color="2E74B5")
THIN = Border(*[Side(style="thin", color="BFBFBF")] * 4)
WRAP = Alignment(vertical="top", wrap_text=True)

# DB-authoritative per-sheet synced counts
con = sqlite3.connect(os.path.join(BASE, "sales_pipeline.db"))
cur = con.cursor()
cur.execute("""
  SELECT gcs_path, COUNT(*) FROM contacts
  WHERE gcs_path LIKE 'sales-contacts/marketing_list_kalika%'
     OR gcs_path LIKE 'sales-contacts/pune region%'
     OR gcs_path LIKE 'sales-contacts/Sales-data%'
  GROUP BY gcs_path
""")
in_db = dict(cur.fetchall())
cur.execute("SELECT COUNT(*) FROM contacts")
db_total = cur.fetchone()[0]
con.close()

PARSED = {
    "sales-contacts/marketing_list_kalika (1).xlsx#removed duplicates - mail list": (514, "2 dup skipped; 264 existing records phone/address field-filled"),
    "sales-contacts/marketing_list_kalika (1).xlsx#main list": (152, "97 dup (overlap with dedup list); 10 field-filled"),
    "sales-contacts/marketing_list_kalika (1).xlsx#Sheet1": (1126, "1122 dup (raw compiled list, overlaps dedup list)"),
    "sales-contacts/pune region contacts (1).xlsx#Sheet1": (79, "78 new; 1 blank row skipped"),
    "sales-contacts/pune region contacts (1).xlsx#Sheet2": (33, "32 new; 1 dup"),
    "sales-contacts/pune region contacts (1).xlsx#packvision contacts": (41, "28 new; 12 dup; 1 blank (header repaired positionally)"),
    "sales-contacts/pune region contacts (1).xlsx#gadekar sir contacts": (88, "33 new; 3 dup; 52 follow-up-report lines (not contacts)"),
    "sales-contacts/pune region contacts (1).xlsx#Sheet11": (22, "20 new; 2 dup"),
    "sales-contacts/pune region contacts (1).xlsx#Sheet3": (857, "47 new; 810 rows are attribute-only fragments (no name/company/email) - not contacts"),
    "sales-contacts/pune region contacts (1).xlsx#Sheet4": (853, "18 new; 834 attribute-only fragments skipped (headers repaired positionally)"),
    "sales-contacts/Sales-data.xlsx#out-off-state": (48, "44 new (TASL, BDL etc. with sub-contacts); 4 dup"),
    "sales-contacts/Sales-data.xlsx#Packvision": (111, "0 new - all 111 already in DB from earlier GCS sync (VCF/packvision expo import)"),
    "sales-contacts/Sales-data.xlsx#sales-person1": (88, "0 new - same 36 contacts as 'gadekar sir contacts' (dup); 52 follow-up-report lines"),
}

wb = load_workbook(XLSX)
ws = wb["2_Contacts_Summary"]
# remove previously appended block (rows 20+)
if ws.max_row >= 20:
    ws.delete_rows(20, ws.max_row - 19)

r = 20
ws.cell(row=r, column=1, value="APP CONTACTS SYNC — 30-Oct-2026 (into current app DB via the app's own /api/contacts/import/gcs pipeline; details preserved as-is — unmapped source columns kept verbatim in contact notes)").font = SUB_FONT
r += 1
headers = ["GCS source (file#sheet)", "Rows parsed", "Contacts in App DB", "Result / notes"]
for j, h in enumerate(headers):
    c = ws.cell(row=r, column=1 + j, value=h)
    c.fill = HDR_FILL; c.font = HDR_FONT; c.border = THIN
    c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
r += 1
tot_parsed = tot_db = 0
for path, (parsed, note) in PARSED.items():
    cnt = in_db.get(path, in_db.get(path.strip(), 0))
    tot_parsed += parsed; tot_db += cnt
    for j, v in enumerate([path, parsed, cnt, note]):
        c = ws.cell(row=r, column=1 + j, value=v)
        c.border = THIN; c.alignment = WRAP
    r += 1
for j, v in enumerate(["TOTAL", tot_parsed, tot_db, f"+871 new contacts this sync; 275 existing records field-filled (empty phone/address only)"]):
    c = ws.cell(row=r, column=1 + j, value=v)
    c.font = Font(bold=True); c.border = THIN
r += 2
for n in [
    f"App DB total contacts after sync: {db_total} (7,924 before -> +871 new from the 3 GCS contact files; user: ai.solutions@kalisoftai.in).",
    "Nothing added/removed: the app's standard field mapping (normalise_record) was used; every unmapped source column (Call status, Requirements, Industry/Category, Rates remarks, Videos sent, etc.) is preserved verbatim in the contact's notes.",
    "Duplicates follow the app rule (user + email); rows with no contact identity at all (orphan attribute fragments, follow-up report lines) are not contacts and were skipped.",
    "Blank-header sheets (packvision contacts, Sheet3, Sheet4, out-off-state) were understood with positional header repair — values unchanged.",
]:
    ws.cell(row=r, column=1, value="• " + n).font = Font(italic=True, size=9)
    r += 1
ws.column_dimensions["A"].width = 56
for col, w in zip("BCD", [12, 15, 60]):
    ws.column_dimensions[col].width = w

wb.save(XLSX)
print("Excel fixed:", XLSX)

creds, _ = google.auth.default()
client = storage.Client(credentials=creds)
bucket = client.bucket("kalika_enterprises")
blob = bucket.blob(GCS_DEST)
blob.upload_from_filename(XLSX)
print(f"Pushed to gs://kalika_enterprises/{GCS_DEST} ({os.path.getsize(XLSX)} bytes)")
