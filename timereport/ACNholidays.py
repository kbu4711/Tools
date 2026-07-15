# -*- coding: utf-8 -*-
"""
Ermittelt aus Accenture 'Personal Vacation/Expense Detail' Reports pro Monat:
- CYTD Ending Vacation Hours Balance (Urlaub)
- CYTD Ending Balance Hours (Überstunden)
"""

import re
import glob
import html
import os
from datetime import datetime
import pandas as pd  # type: ignore[import-untyped]

# Ordnerpfad 
BASE_DIR = r"C:/Users/karen.bugge/timereport/files"   

RE_DATE = re.compile(r"Period\s+end\s+date:\s*([0-3]?\d\.[01]?\d\.\d{4})")
RE_VAC  = re.compile(r"CYTD\s+Ending\s+Vacation\s+Hours\s+Balance\s*([\-+]?\d+[\.,]?\d*)")
RE_OT   = re.compile(r"CYTD\s+Ending\s+Balance\s+Hours\s*([\-+]?\d+[\.,]?\d*)")

def extract_from_file(path: str):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        raw = f.read()

    text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)

    m_date = RE_DATE.search(text)
    m_vac  = RE_VAC.search(text)
    m_ot   = RE_OT.search(text)
    if not (m_date and m_vac and m_ot):
        return None

    dt = datetime.strptime(m_date.group(1), "%d.%m.%Y")

    def to_float(s):
        return float(s.replace(",", "."))

    return {
        "date": dt,
        "month": dt.strftime("%Y-%m"),
        "file": path,
        "CYTD_Ending_Vacation_Hours_Balance": to_float(m_vac.group(1)),
        "CYTD_Ending_Balance_Hours": to_float(m_ot.group(1)),
    }

def main():
    pattern = os.path.join(BASE_DIR, "*.htm*")
    records = []

    for path in sorted(glob.glob(pattern)):
        if "vacation" not in path.lower():
            continue
        rec = extract_from_file(path)
        if rec:
            records.append(rec)

    if not records:
        raise SystemExit("Keine passenden Daten gefunden.")

    df = pd.DataFrame(records)
    idx = df.groupby("month")["date"].idxmax()
    monthly = pd.DataFrame(df.loc[idx]).sort_values("date").reset_index(drop=True)

    monthly_out = monthly.rename(columns={
        "month": "Monat",
        "date": "Stichtag",
        "CYTD_Ending_Vacation_Hours_Balance": "Urlaub_CYTD_Stunden",
        "CYTD_Ending_Balance_Hours": "Ueberstunden_CYTD_Stunden"
    })[["Monat", "Stichtag", "Urlaub_CYTD_Stunden", "Ueberstunden_CYTD_Stunden"]]

    monthly_out["Urlaubstage"] = monthly_out["Urlaub_CYTD_Stunden"] / 8
    monthly_out = monthly_out[["Monat", "Stichtag", "Urlaub_CYTD_Stunden", "Urlaubstage", "Ueberstunden_CYTD_Stunden"]]

    monthly_out["Jahr"] = monthly_out["Monat"].str[:4]
    yearly_with_totals = []
    for year, group in monthly_out.groupby("Jahr", sort=True):
        year_rows = group.drop(columns=["Jahr"]).sort_values("Monat")
        yearly_with_totals.append(year_rows)

        last_row = year_rows.iloc[-1]
        yearly_with_totals.append(pd.DataFrame([{
            "Monat": f"Stand {year}",
            "Stichtag": pd.NaT,
            "Urlaub_CYTD_Stunden": last_row["Urlaub_CYTD_Stunden"],
            "Urlaubstage": last_row["Urlaubstage"],
            "Ueberstunden_CYTD_Stunden": last_row["Ueberstunden_CYTD_Stunden"],
        }]))

    monthly_out = pd.concat(yearly_with_totals, ignore_index=True)

    reports_dir = os.path.normpath(os.path.join(BASE_DIR, "..", "reports"))
    os.makedirs(reports_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(reports_dir, f"holiday_report_{timestamp}.csv")
    monthly_out.to_csv(out_path, index=False, decimal=",")

    print("CSV geschrieben:", out_path)
    print_df = monthly_out.copy()
    print_df["Stichtag"] = print_df["Stichtag"].apply(lambda x: x.strftime("%Y-%m-%d") if pd.notna(x) else "")
    print(print_df.to_string(index=False))

if __name__ == "__main__":
    main()
