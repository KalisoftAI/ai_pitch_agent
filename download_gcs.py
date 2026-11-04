"""Download key files from GCS kalika_enterprises bucket for analysis."""
import os
import sys
import google.auth
from google.cloud import storage

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gcs_data")
os.makedirs(OUT_DIR, exist_ok=True)

FILES = [
    # Contacts
    "sales-contacts/marketing_list_kalika (1).xlsx",
    "sales-contacts/pune region contacts (1).xlsx",
    "sales-contacts/Sales-data.xlsx",
    # ERP reports (dispatch/delivery)
    "ERP-V1/Reports/kalika_report_2026-10-28.xlsx",
    "ERP-V1/Reports/kalika_report_2026-10-30.xlsx",
    # Actual sales data 2026 (monthly)
    "kalika_sales2026/SALE MAR-26 (1).xls",
    "kalika_sales2026/SALE R APRIL-26.xls",
    "kalika_sales2026/SALE R MAY-26.xls",
    "kalika_sales2026/SALE R JUNE-26.xls",
    "kalika_sales2026/SALE R JULY -26.xls",
    "kalika_sales2026/SALE R AUG 26.xls",
    "kalika_sales2026/SALE R SEP-26.xls",
    "kalika_sales2026/SALES-FEB-26.xls",
    "kalika_sales2026/Sales Jan-26.xls",
    # App / API doc
    "sales-metadata/Kalika_Real_Time_Customer_Feedback_System.md",
]

def safe_name(gcs_name: str) -> str:
    parts = gcs_name.split("/")
    prefix = parts[0].replace(" ", "_")
    fname = parts[-1].replace(" ", "_")
    return os.path.join(OUT_DIR, f"{prefix}__{fname}")

def main():
    creds, _ = google.auth.default()
    client = storage.Client(credentials=creds)
    bucket = client.bucket("kalika_enterprises")
    for f in FILES:
        dest = safe_name(f)
        try:
            blob = bucket.blob(f)
            blob.download_to_filename(dest)
            print(f"OK   {f} -> {os.path.basename(dest)} ({os.path.getsize(dest)} bytes)")
        except Exception as e:
            print(f"FAIL {f}: {e}")

if __name__ == "__main__":
    main()
