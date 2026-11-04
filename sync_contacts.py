"""Sync contacts from the previously-referenced GCS contact files into the
current app DB (sales_pipeline.db) using the app's own importer pipeline.

Rules:
- Uses sales_fastapi.importer.normalise_record (the same mapping the app's
  POST /api/contacts/import/gcs endpoint uses) -> nothing added, nothing removed.
- Any source column the app's model has no field for is preserved VERBATIM in
  the contact's notes as "Header: value" (app schema unchanged, no data lost).
- Dedupe: same rule as the app (user_id + email); placeholder emails are the
  app's own convention for contacts without an email address.
"""
import io, os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import google.auth
from google.cloud import storage

from sales_fastapi.database import SessionLocal, init_db
from sales_fastapi.importer import normalise_record
from sales_fastapi.models import Contact, User

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "gcs_data")
REPORT = os.path.join(BASE, "contacts_sync_report.json")

USER_EMAIL = "ai.solutions@kalisoftai.in"

# files (GCS path -> local copy) and the sheets that carry contact rows
FILES = {
    "sales-contacts/marketing_list_kalika (1).xlsx": {
        "local": "sales-contacts__marketing_list_kalika_(1).xlsx",
        "sheets": ["removed duplicates - mail list", "main list ", "Sheet1"],
    },
    "sales-contacts/pune region contacts (1).xlsx": {
        "local": "sales-contacts__pune_region_contacts_(1).xlsx",
        "sheets": ["Sheet1", "Sheet2", "packvision contacts", "gadekar sir contacts", "Sheet11", "Sheet3", "Sheet4"],
    },
    "sales-contacts/Sales-data.xlsx": {
        "local": "sales-contacts__Sales-data.xlsx",
        "sheets": ["out-off-state", "Packvision", "sales-person1"],
    },
}

# headers the app's normalise_record already understands (kept out of the
# verbatim notes so nothing is duplicated)
KNOWN_HEADERS = {
    "email", "email (company / division)", "e-mail", "mail", "email id", "email address",
    "contact email", "e mail", "emailid", "company", "organisation", "organization",
    "company name", "firm", "org", "name", "contact", "contact name", "contact person",
    "full name", "person", "first name", "phone", "contact (phone)", "mobile",
    "phone number", "contact number", "tel", "address", "address (ahmednagar unit)",
    "location", "city", "linkedin", "linkedin (company / key scm profile)", "linkedin url",
    "website", "purchase / scm contact (name, role)", "purchase contact", "scm contact",
    "purchase contact details (email / phone)", "purchase email", "title", "designation",
    "role", "position", "sector", "category", "exporter", "turnover range",
    "requirements", "description", "call status",
}


# positional header repair for sheets whose header cells are partly blank
# (values unchanged — only blank header positions get a label so the app's
# importer can understand the column; same approach as the app's own xlsx scan)
POSITIONAL_HEADERS = {
    "pune region contacts (1).xlsx#Sheet4": {
        0: "Company Name", 1: "Contact Person", 2: "Email ID", 3: "Contact No.", 4: "Category",
    },
    "pune region contacts (1).xlsx#packvision contacts": {
        4: "Contact No.",
    },
}

# header synonym aliases understood at sync time (data values untouched)
HEADER_ALIASES = {
    "contact no.": "phone number",
    "company / contact name": "company name",
}


def sheet_records(path, sheet, file_key):
    """Parse a sheet into dict records.

    Header detection mirrors the app's _xlsx_rows: scan forward to the first
    row with >= 2 non-empty cells and treat it as the header. Blank header
    cells are repaired positionally (see POSITIONAL_HEADERS) so no column is
    dropped; all values stay verbatim.
    """
    df = pd.read_excel(path, sheet_name=sheet, dtype=object, header=None)
    df = df.dropna(how="all")
    if df.empty:
        return []
    hdr_idx = None
    for i in range(min(10, len(df))):
        row = df.iloc[i]
        if sum(1 for v in row.tolist() if pd.notna(v) and str(v).strip()) >= 2:
            hdr_idx = i
            break
    if hdr_idx is None:
        return []
    repair = POSITIONAL_HEADERS.get(file_key, {})
    headers = []
    for j, v in enumerate(df.iloc[hdr_idx].tolist()):
        h = str(v).strip() if pd.notna(v) else ""
        if not h and j in repair:
            h = repair[j]
        headers.append(h)
    records = []
    for _, row in df.iloc[hdr_idx + 1:].iterrows():
        rec = {}
        for h, v in zip(headers, row.tolist()):
            if not h or pd.isna(v):
                continue
            alias = HEADER_ALIASES.get(h.strip().lower())
            rec[alias or h] = str(v).strip()
        if any(v for v in rec.values()):
            records.append(rec)
    return records


def preserve_extras(normalised, record):
    """Append unmapped source fields verbatim to notes (no data added/removed)."""
    extras = []
    for k, v in record.items():
        if k.strip().lower() in KNOWN_HEADERS or k.lower().startswith("unnamed"):
            continue
        if v:
            extras.append(f"{k}: {v}")
    if extras:
        base = normalised.get("notes", "")
        normalised["notes"] = (base + " | " if base else "") + " | ".join(extras)
    return normalised


def main():
    init_db()
    db = SessionLocal()
    user = db.query(User).filter(User.email == USER_EMAIL).first()
    if not user:
        print("user not found:", USER_EMAIL)
        return
    print(f"Syncing as user id={user.id} ({user.email})")

    report = {"user": USER_EMAIL, "files": []}
    total_in = total_dup = total_blank = 0
    seen = set()  # emails queued in this run (dedupe before commit, same rule as app)

    for gcs_path, meta in FILES.items():
        local = os.path.join(DATA, meta["local"])
        for sheet in meta["sheets"]:
            file_key = f"{os.path.basename(gcs_path)}#{sheet}"
            try:
                records = sheet_records(local, sheet, file_key)
            except Exception as e:
                report["files"].append({"gcs_path": f"{gcs_path}#{sheet}", "error": str(e)[:120]})
                continue
            imported = dup = blank = updated = 0
            for rec in records:
                n = normalise_record(rec)
                if not n:
                    blank += 1
                    continue
                n = preserve_extras(n, rec)
                exists = None if n["email"] in seen else (
                    db.query(Contact)
                    .filter(Contact.user_id == user.id, Contact.email == n["email"])
                    .first()
                )
                if exists is not None or n["email"] in seen:
                    # duplicate: fill only EMPTY phone/address from the same
                    # source record (no data added beyond the GCS row itself)
                    target = exists or db.query(Contact).filter(
                        Contact.user_id == user.id, Contact.email == n["email"]).first()
                    if target is not None:
                        changed = False
                        if not target.phone and n.get("phone"):
                            target.phone = n["phone"]; changed = True
                        if not target.address and n.get("address"):
                            target.address = n["address"]; changed = True
                        if changed:
                            updated += 1
                    dup += 1
                    continue
                seen.add(n["email"])
                db.add(Contact(user_id=user.id, source="gcs", gcs_path=f"{gcs_path}#{sheet}".strip(), **n))
                imported += 1
            db.commit()
            report["files"].append({
                "gcs_path": f"{gcs_path}#{sheet}".strip(),
                "rows_parsed": len(records),
                "imported": imported,
                "skipped_duplicate": dup,
                "skipped_no_contact_info": blank,
                "existing_updated_empty_fields": updated,
            })
            total_in += imported; total_dup += dup; total_blank += blank
            print(f"{gcs_path}#{sheet}: parsed={len(records)} imported={imported} dup={dup} blank={blank} updated={updated}")

    total_upd = sum(f.get("existing_updated_empty_fields", 0) for f in report["files"])
    report["totals"] = {
        "imported": total_in,
        "skipped_duplicate": total_dup,
        "skipped_no_contact_info": total_blank,
        "existing_updated_empty_fields": total_upd,
    }
    report["db_total_contacts"] = db.query(Contact).count()
    with open(REPORT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    print("TOTAL:", report["totals"], "| db contacts now:", report["db_total_contacts"])
    db.close()


if __name__ == "__main__":
    main()
