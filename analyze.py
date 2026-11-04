"""Comprehensive analysis of Kalika Enterprises GCS data -> analysis.json"""
import os, re, json, glob, zipfile
import pandas as pd
import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "gcs_data")
OUT = os.path.join(BASE, "analysis.json")

R = {}  # results


# ---------------------------------------------------------------- contacts
def series_counts(df, col):
    if col not in df.columns:
        return {}
    s = df[col].dropna().astype(str).str.strip()
    s = s[s != ""]
    return s.value_counts().to_dict()


def clean_phone(v):
    d = re.sub(r"\D", "", str(v))
    return d if len(d) >= 10 else None


def analyze_sheet(df, name_map):
    """name_map: logical->actual column names"""
    out = {}
    for logical, actual in name_map.items():
        if actual and actual in df.columns:
            s = df[actual].dropna().astype(str).str.strip()
            s = s[(s != "") & (s.str.lower() != "nan")]
            out[logical + "_filled"] = int(len(s))
    return out


def contacts_analysis():
    res = {}

    # ---- marketing_list_kalika
    f = os.path.join(DATA, "sales-contacts__marketing_list_kalika_(1).xlsx")
    xl = pd.ExcelFile(f)
    m = {}

    ded = xl.parse("removed duplicates - mail list")
    ded.columns = [str(c).strip() for c in ded.columns]
    m["dedup_list"] = {
        "total_rows": int(len(ded)),
        "names": int(ded["NAME"].notna().sum()),
        "phones": int(ded["Contact NO."].notna().sum()),
        "emails": int(ded["Email no."].notna().sum()),
        "addresses": int(ded["Address"].notna().sum()),
        "categories": series_counts(ded, "Category"),
        "call_status": series_counts(ded, "Call status"),
        "requirements_logged": int(ded["Requirements"].notna().sum()),
    }

    main = xl.parse("main list ")
    main.columns = [str(c).strip() for c in main.columns]
    m["main_list"] = {
        "total_rows": int(len(main)),
        "companies": int(main["Company"].notna().sum()),
        "contacts": int(main["Contact"].notna().sum()),
        "purchase_dept_contacts": int(main["Purchase_Dept_Contact"].notna().sum()),
        "emails": int(main["Email"].notna().sum()),
        "purchase_dept_emails": int(main["Purchase_Dept_Email"].notna().sum()),
        "websites": int(main["Website"].notna().sum()),
        "categories": series_counts(main, "Category"),
        "call_status": series_counts(main, "Call status"),
        "requirements_logged": int(main["Requirements"].notna().sum()),
        "sources": series_counts(main, "Source_Title"),
    }

    s1 = xl.parse("Sheet1")
    s1.columns = [str(c).strip() for c in s1.columns]
    m["sheet1"] = {
        "total_rows": int(len(s1)),
        "names": int(s1["NAME"].notna().sum()),
        "phones": int(s1["Contact NO."].notna().sum()),
        "emails": int(s1["Email no."].notna().sum()),
    }

    s3 = xl.parse("Sheet3")
    s3.columns = [str(c).strip() for c in s3.columns]
    date_col = next((c for c in s3.columns if c.lower().startswith("date")), s3.columns[0])
    m["calling_log"] = {
        "days_logged": int(s3[date_col].notna().sum()),
        "rows": s3.fillna("").astype(str).values.tolist()[:12],
        "columns": list(s3.columns),
    }

    # unique phones across dedup + main + sheet1
    phones = set()
    for df_, col in [(ded, "Contact NO."), (s1, "Contact NO.")]:
        for v in df_[col].dropna():
            p = clean_phone(v)
            if p:
                phones.add(p)
    for v in main["Contact"].dropna():
        p = clean_phone(v)
        if p:
            phones.add(p)
    for v in main["Purchase_Dept_Contact"].dropna():
        p = clean_phone(v)
        if p:
            phones.add(p)
    m["unique_phones_overall"] = len(phones)

    emails = set()
    for df_, col in [(ded, "Email no."), (s1, "Email no."), (main, "Email"), (main, "Purchase_Dept_Email")]:
        for v in df_[col].dropna():
            v = str(v).strip().lower()
            if "@" in v:
                emails.add(v)
    m["unique_emails_overall"] = len(emails)

    res["marketing_list_kalika"] = m

    # ---- pune region contacts
    f = os.path.join(DATA, "sales-contacts__pune_region_contacts_(1).xlsx")
    xl = pd.ExcelFile(f)
    p = {}

    prod = xl.parse("Products details")
    prod.columns = [str(c).strip() for c in prod.columns]
    p["products_rate_list"] = prod.dropna(how="all").fillna("").astype(str).values.tolist()

    s1 = xl.parse("Sheet1")
    s1.columns = [str(c).strip() for c in s1.columns]
    p["sheet1"] = {
        "companies": int(s1["Company Name"].notna().sum()),
        "phones": int(s1["Phone"].notna().sum()),
        "emails": int(s1["Email"].notna().sum()),
        "industry_categories": series_counts(s1, "Industry Category"),
        "business_categories": series_counts(s1, "Business Category"),
        "sectors": series_counts(s1, "Sector"),
        "call_status": series_counts(s1, "Call Status"),
        "requirements_logged": int(s1["Requirements"].notna().sum()),
        "followups_logged": int(s1["Follow ups"].notna().sum()) if "Follow ups" in s1.columns else 0,
    }

    gad = xl.parse("gadekar sir contacts")
    gad.columns = [str(c).strip() for c in gad.columns]
    p["gadekar_sir"] = {
        "contact_names": int(gad["Contact Name"].notna().sum()),
        "phones": int(gad["Phone Number"].notna().sum()),
        "followup_report_rows": int(gad["Company Calling & Follow-up Report"].notna().sum()),
    }

    s2 = xl.parse("Sheet2")
    s2.columns = [str(c).strip() for c in s2.columns]
    p["sheet2"] = {
        "companies": int(s2["Company Name"].notna().sum()),
        "call_status": series_counts(s2, "Call status"),
        "followups_logged": int(s2["Follow ups"].notna().sum()),
    }

    s11 = xl.parse("Sheet11")
    s11.columns = [str(c).strip() for c in s11.columns]
    comp_col = next((c for c in s11.columns if "company" in c.lower()), s11.columns[0])
    req_col = next((c for c in s11.columns if c.lower().startswith("requirement")), None)
    p["sheet11_requirements"] = {
        "companies": int(s11[comp_col].notna().sum()),
        "requirements": s11[req_col].dropna().astype(str).str.strip().tolist()[:30] if req_col else [],
        "followups": int(s11["follow ups"].notna().sum()) if "follow ups" in s11.columns else 0,
    }
    res["pune_region_contacts"] = p

    # ---- Sales-data.xlsx
    f = os.path.join(DATA, "sales-contacts__Sales-data.xlsx")
    xl = pd.ExcelFile(f)
    sd = {}
    oos = xl.parse("out-off-state")
    sd["out_of_state_rows"] = int(oos.dropna(how="all").shape[0])
    pv = xl.parse("Packvision")
    pv.columns = [str(c).strip() for c in pv.columns]
    sd["packvision"] = {
        "rows": int(len(pv)),
        "companies": int(pv["Company"].notna().sum()),
        "names": int(pv["Name"].notna().sum()),
        "phones": int(pv["Phone"].notna().sum()),
        "emails": int(pv["Email"].notna().sum()),
        "call_status": series_counts(pv, "Call status"),
    }
    sp1 = xl.parse("sales-person1")
    sp1.columns = [str(c).strip() for c in sp1.columns]
    sd["sales_person1"] = {
        "contact_names": int(sp1["Contact Name"].notna().sum()),
        "phones": int(sp1["Phone Number"].notna().sum()),
        "followup_report_rows": int(sp1["Company Calling & Follow-up Report"].notna().sum()),
        "followup_samples": [x for x in sp1["Company Calling & Follow-up Report"].dropna().astype(str).tolist()[:15]],
    }
    res["sales_data_file"] = sd
    return res


# ---------------------------------------------------------------- ERP report
def erp_analysis():
    f = os.path.join(DATA, "ERP-V1__kalika_report_2026-10-30.xlsx")
    xl = pd.ExcelFile(f)
    e = {}
    for sh in xl.sheet_names:
        df = xl.parse(sh)
        df.columns = [str(c).strip() for c in df.columns]
        e[sh] = {"rows": int(len(df))}

    orders = xl.parse("Orders"); orders.columns = [str(c).strip() for c in orders.columns]
    orders["Total Value"] = pd.to_numeric(orders["Total Value"], errors="coerce")
    e["Orders"].update({
        "total_value": float(orders["Total Value"].sum()),
        "status": series_counts(orders, "Status"),
        "unique_customers": int(orders["Customer"].nunique()),
        "with_required_date": int(orders["Required Date"].notna().sum()),
    })

    disp = xl.parse("Dispatch"); disp.columns = [str(c).strip() for c in disp.columns]
    disp["% Comp"] = pd.to_numeric(disp["% Comp"], errors="coerce")
    disp["Schedule"] = pd.to_numeric(disp["Schedule"], errors="coerce")
    disp["Dispatched"] = pd.to_numeric(disp["Dispatched"], errors="coerce")
    e["Dispatch"].update({
        "status": series_counts(disp, "Status"),
        "unique_customers": int(disp["Customer"].nunique()),
        "avg_completion_pct": float(disp["% Comp"].mean()),
        "total_scheduled_qty": float(disp["Schedule"].sum()),
        "total_dispatched_qty": float(disp["Dispatched"].sum()),
        "plants": series_counts(disp, "Plant"),
    })

    prodn = xl.parse("Production"); prodn.columns = [str(c).strip() for c in prodn.columns]
    prodn["% Comp"] = pd.to_numeric(prodn["% Comp"], errors="coerce")
    e["Production"].update({
        "status": series_counts(prodn, "Status"),
        "avg_completion_pct": float(prodn["% Comp"].mean()),
    })

    inv = xl.parse("Inventory"); inv.columns = [str(c).strip() for c in inv.columns]
    inv["Current Stock"] = pd.to_numeric(inv["Current Stock"], errors="coerce")
    e["Inventory"].update({
        "categories": series_counts(inv, "Category"),
        "plants": series_counts(inv, "Plant"),
    })

    pur = xl.parse("Purchases"); pur.columns = [str(c).strip() for c in pur.columns]
    pur["Total Amount"] = pd.to_numeric(pur["Total Amount"], errors="coerce")
    e["Purchases"].update({
        "total_amount": float(pur["Total Amount"].sum()),
        "status": series_counts(pur, "Status"),
        "unique_suppliers": int(pur["Supplier"].nunique()),
    })
    return {"report_file": "kalika_report_2026-10-30.xlsx", "sheets": e}


# ---------------------------------------------------------------- sales registers
def parse_register(path):
    df = pd.read_excel(path, sheet_name="Sales Register", header=None)
    hdr_idx = None
    for i in range(min(20, len(df))):
        if str(df.iloc[i, 0]).strip() == "Date":
            hdr_idx = i
            break
    if hdr_idx is None:
        return None
    # map header names -> column index (robust to FY format changes)
    cmap = {}
    for j, v in df.iloc[hdr_idx].items():
        if pd.notna(v):
            cmap[str(v).strip()] = j
    ci = {
        "date": cmap.get("Date", 0),
        "particulars": cmap.get("Particulars", 1),
        "vch_no": cmap.get("Voucher No.", 7),
        "gstin": cmap.get("GSTIN/UIN", 9),
        "pay_terms": cmap.get("Terms of Payment"),
        "qty": cmap.get("Quantity"),
        "rate": cmap.get("Rate"),
        "value": cmap.get("Value"),
        "gross": cmap.get("Gross Total"),
    }

    def g(row, key):
        idx = ci[key]
        return row[idx] if idx is not None and idx in row.index else None

    data = df.iloc[hdr_idx + 1:].reset_index(drop=True)
    vouchers, items = [], []
    current = None
    for _, row in data.iterrows():
        c0, c1 = g(row, "date"), g(row, "particulars")
        if isinstance(c0, pd.Timestamp) or hasattr(c0, "year"):
            if str(c1).strip().lower() in ("total", "grand total"):
                current = None
                continue
            v = {
                "date": str(c0)[:10],
                "customer": str(c1).strip(),
                "vch_no": str(g(row, "vch_no") or "").strip(),
                "gstin": str(g(row, "gstin") or "").strip(),
                "payment_terms": str(g(row, "pay_terms") or "").strip(),
                "qty": pd.to_numeric(g(row, "qty"), errors="coerce"),
                "value": pd.to_numeric(g(row, "value"), errors="coerce"),
                "gross": pd.to_numeric(g(row, "gross"), errors="coerce"),
            }
            vouchers.append(v)
            current = v
        elif pd.isna(c0) and pd.notna(c1) and current is not None:
            item_name = str(c1).strip()
            if item_name.lower() in ("grand total", "total"):
                continue
            items.append({
                "customer": current["customer"],
                "item": item_name,
                "qty": pd.to_numeric(g(row, "qty"), errors="coerce"),
                "rate": pd.to_numeric(g(row, "rate"), errors="coerce"),
                "value": pd.to_numeric(g(row, "value"), errors="coerce"),
            })
    return vouchers, items


def sales_analysis():
    files = {
        "Jan-26": "kalika_sales2026__Sales_Jan-26.xls",
        "Feb-26": "kalika_sales2026__SALES-FEB-26.xls",
        "Mar-26": "kalika_sales2026__SALE_MAR-26_(1).xls",
        "Apr-26": "kalika_sales2026__SALE_R_APRIL-26.xls",
        "May-26": "kalika_sales2026__SALE_R_MAY-26.xls",
        "Jun-26": "kalika_sales2026__SALE_R_JUNE-26.xls",
        "Jul-26": "kalika_sales2026__SALE_R_JULY_-26.xls",
        "Aug-26": "kalika_sales2026__SALE_R_AUG_26.xls",
        "Sep-26": "kalika_sales2026__SALE_R_SEP-26.xls",
    }
    monthly, all_v, all_i = [], [], []
    for mon, fn in files.items():
        parsed = parse_register(os.path.join(DATA, fn))
        if not parsed:
            monthly.append({"month": mon, "error": "header not found"})
            continue
        vouchers, items = parsed
        vdf = pd.DataFrame(vouchers)
        idf = pd.DataFrame(items)
        gross = vdf["gross"].sum(min_count=1)
        monthly.append({
            "month": mon,
            "invoices": int(len(vdf)),
            "unique_customers": int(vdf["customer"].nunique()),
            "taxable_value": float(vdf["value"].sum(min_count=1) or 0),
            "gross_total": float(gross if pd.notna(gross) else 0),
            "line_items": int(len(idf)),
        })
        vdf["month"] = mon
        all_v.append(vdf)
        if len(idf):
            idf["month"] = mon
            all_i.append(idf)

    V = pd.concat(all_v, ignore_index=True)
    I = pd.concat(all_i, ignore_index=True) if all_i else pd.DataFrame()

    top_cust = (V.groupby("customer")["gross"].sum().sort_values(ascending=False).head(15))
    pay_terms = V["payment_terms"].replace("", np.nan).dropna().value_counts().head(10).to_dict()

    res = {
        "monthly": monthly,
        "total_invoices": int(len(V)),
        "total_gross": float(V["gross"].sum()),
        "total_taxable": float(V["value"].sum()),
        "unique_customers": int(V["customer"].nunique()),
        "top_customers": [{"customer": k, "gross": float(v)} for k, v in top_cust.items()],
        "payment_terms": {str(k): int(v) for k, v in pay_terms.items()},
    }
    if len(I):
        top_items = I.groupby("item")["value"].sum().sort_values(ascending=False).head(15)
        res["top_products"] = [{"item": k, "value": float(v)} for k, v in top_items.items()]
    return res


# ---------------------------------------------------------------- whatsapp
def whatsapp_analysis():
    lst = []
    with open(os.path.join(BASE, "wa_list.txt"), encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("kalika backup/") and " | " in line:
                name, size = line.rsplit(" | ", 1)
                try:
                    lst.append({"file": name.replace("kalika backup/", ""), "size_bytes": int(size)})
                except ValueError:
                    pass
    zips = [x for x in lst if x["file"].endswith(".zip")]
    return {"chat_zip_count": len(zips), "files": lst}


def main():
    R["contacts"] = contacts_analysis()
    print("contacts done")
    R["erp_latest"] = erp_analysis()
    print("erp done")
    R["sales_2026"] = sales_analysis()
    print("sales done")
    R["whatsapp"] = whatsapp_analysis()
    print("whatsapp done")
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(R, fh, indent=2, ensure_ascii=False, default=str)
    print("saved", OUT)


if __name__ == "__main__":
    main()
