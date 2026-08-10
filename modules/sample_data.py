"""
Feature 16: Sample Data Generator
Creates a demonstration XLSX workbook with four sheets:
  1. Healthy_BDX       — clean, table-formatted sheet
  2. Split_Blank_Col   — has a blank column (AY) between AX and AZ
  3. Duplicate_Policies — multiple rows per policy with conflicting amounts
  4. Missing_Values    — blank key fields and missing financial values
"""
from __future__ import annotations

import io
import random
import string
from typing import List

import numpy as np
import openpyxl
import pandas as pd
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter


def _policy_id(i: int) -> str:
    return f"POL-{i:05d}"


def _cert_id(i: int) -> str:
    return f"CERT-{i:06d}"


def _rand_premium() -> float:
    return round(random.uniform(500, 50_000), 2)


def _rand_commission(premium: float) -> float:
    return round(premium * random.uniform(0.10, 0.20), 2)


def _rand_tax(premium: float) -> float:
    return round(premium * random.uniform(0.02, 0.06), 2)


def _make_healthy_df(n: int = 200) -> pd.DataFrame:
    random.seed(42)
    np.random.seed(42)
    rows = []
    for i in range(1, n + 1):
        prem = _rand_premium()
        comm = _rand_commission(prem)
        tax = _rand_tax(prem)
        rows.append({
            "Policy Number": _policy_id(i),
            "Certificate Number": _cert_id(i),
            "Insured Name": f"Company {i} Ltd",
            "Inception Date": pd.Timestamp("2024-01-01") + pd.Timedelta(days=i % 365),
            "Expiry Date": pd.Timestamp("2025-01-01") + pd.Timedelta(days=i % 365),
            "Class of Business": random.choice(["Property", "Liability", "Marine", "Cyber"]),
            "Country": random.choice(["US", "UK", "DE", "FR", "AU"]),
            "Currency": random.choice(["USD", "GBP", "EUR"]),
            "Net Premium": prem,
            "Commission": comm,
            "Tax": tax,
            "Gross Premium": round(prem + comm + tax, 2),
            "Net Due": round(prem - comm, 2),
            "Status": random.choice(["Active", "Cancelled", "Renewed"]),
        })
    return pd.DataFrame(rows)


def _make_split_blank_df(n: int = 150) -> pd.DataFrame:
    """
    Creates a dataframe that, when written to Excel, has a blank column
    injected between two populated groups (simulating the AX|AY|AZ scenario).
    We write it with a blank column at position 8 (0-indexed).
    """
    random.seed(7)
    np.random.seed(7)
    rows = []
    for i in range(1, n + 1):
        prem = _rand_premium()
        comm = _rand_commission(prem)
        tax = _rand_tax(prem)
        rows.append({
            "Policy Number": _policy_id(1000 + i),
            "Certificate Number": _cert_id(2000 + i),
            "Insured Name": f"Risk Entity {i}",
            "Inception Date": pd.Timestamp("2024-03-01") + pd.Timedelta(days=i % 200),
            "Expiry Date": pd.Timestamp("2025-03-01") + pd.Timedelta(days=i % 200),
            "Class of Business": random.choice(["Property", "Liability"]),
            "Country": random.choice(["US", "UK"]),
            "Currency": "USD",
            # ← blank column will be inserted here (column I) ←
            "Net Premium": prem,
            "Commission": comm,
            "Tax": tax,
            "Gross Premium": round(prem + comm + tax, 2),
            "Net Due": round(prem - comm, 2),
        })
    return pd.DataFrame(rows)


def _make_duplicate_policies_df(n: int = 100) -> pd.DataFrame:
    random.seed(99)
    np.random.seed(99)
    rows = []
    # 30 unique policies, each appearing 2–4 times with slightly different amounts
    pol_ids = [_policy_id(5000 + i) for i in range(30)]
    for pol in pol_ids:
        repeats = random.randint(2, 4)
        for _ in range(repeats):
            prem = _rand_premium()
            comm = _rand_commission(prem)
            rows.append({
                "Policy Number": pol,
                "Certificate Number": _cert_id(random.randint(9000, 9999)),
                "Insured Name": f"Insured for {pol}",
                "Net Premium": prem,
                "Commission": comm,
                "Net Due": round(prem - comm, 2),
                "Transaction Type": random.choice(["Original", "Endorsement", "Return"]),
            })
    return pd.DataFrame(rows[:n])


def _make_missing_values_df(n: int = 120) -> pd.DataFrame:
    random.seed(13)
    np.random.seed(13)
    rows = []
    for i in range(1, n + 1):
        prem = _rand_premium() if random.random() > 0.15 else None
        policy = _policy_id(8000 + i) if random.random() > 0.12 else None
        comm = _rand_commission(prem) if prem is not None else None
        rows.append({
            "Policy Number": policy,
            "Certificate Number": _cert_id(7000 + i),
            "Net Premium": prem,
            "Commission": comm,
            "Net Due": round(prem - comm, 2) if prem and comm else None,
            "Notes": f"Row {i} note" if i % 10 == 0 else None,
        })
    return pd.DataFrame(rows)


def create_sample_workbook() -> bytes:
    """Create and return the sample XLSX file as bytes."""
    output = io.BytesIO()
    wb = openpyxl.Workbook()

    # ---- Sheet 1: Healthy BDX ----
    ws1 = wb.active
    ws1.title = "Healthy_BDX"
    df1 = _make_healthy_df()
    _write_df_as_table(ws1, df1, table_name="HealthyData")

    # ---- Sheet 2: Split Blank Column ----
    ws2 = wb.create_sheet("Split_Blank_Col")
    df2 = _make_split_blank_df()
    _write_df_with_blank_col(ws2, df2, blank_col_index=8)

    # ---- Sheet 3: Duplicate Policies ----
    ws3 = wb.create_sheet("Duplicate_Policies")
    df3 = _make_duplicate_policies_df()
    _write_df_plain(ws3, df3)

    # ---- Sheet 4: Missing Values ----
    ws4 = wb.create_sheet("Missing_Values")
    df4 = _make_missing_values_df()
    _write_df_plain(ws4, df4)

    wb.save(output)
    return output.getvalue()


def _write_df_as_table(ws, df: pd.DataFrame, table_name: str):
    """Write DataFrame as an Excel Table."""
    from openpyxl.worksheet.table import Table, TableStyleInfo

    # Header row
    for ci, col in enumerate(df.columns, start=1):
        cell = ws.cell(row=1, column=ci, value=col)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1976D2")

    # Data rows
    for ri, row in df.iterrows():
        for ci, val in enumerate(row, start=1):
            ws.cell(row=ri + 2, column=ci, value=val)

    # Create table
    end_col = get_column_letter(len(df.columns))
    end_row = len(df) + 1
    tbl = Table(displayName=table_name, ref=f"A1:{end_col}{end_row}")
    tbl.tableStyleInfo = TableStyleInfo(
        name="TableStyleMedium9", showFirstColumn=False,
        showLastColumn=False, showRowStripes=True, showColumnStripes=False,
    )
    ws.add_table(tbl)


def _write_df_with_blank_col(ws, df: pd.DataFrame, blank_col_index: int):
    """Write DataFrame with a deliberately blank column inserted."""
    cols_before = list(df.columns[:blank_col_index])
    cols_after = list(df.columns[blank_col_index:])

    all_headers = cols_before + [""] + cols_after

    header_fill = PatternFill("solid", fgColor="F57C00")
    blank_fill = PatternFill("solid", fgColor="FFCCCC")

    for ci, h in enumerate(all_headers, start=1):
        cell = ws.cell(row=1, column=ci, value=h)
        if h == "":
            cell.fill = blank_fill
        else:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = header_fill

    for ri, row in df.iterrows():
        values_before = [row[c] for c in cols_before]
        values_after = [row[c] for c in cols_after]
        all_values = values_before + [None] + values_after
        for ci, val in enumerate(all_values, start=1):
            ws.cell(row=ri + 2, column=ci, value=val)

    # Add a note
    ws["A1"].comment = None
    note_cell = ws.cell(row=len(df) + 3, column=1)
    note_cell.value = "NOTE: Column I is intentionally blank to demonstrate the split-column risk."
    note_cell.font = Font(italic=True, color="CC0000")


def _write_df_plain(ws, df: pd.DataFrame):
    """Write DataFrame without an Excel Table."""
    header_fill = PatternFill("solid", fgColor="455A64")
    for ci, col in enumerate(df.columns, start=1):
        cell = ws.cell(row=1, column=ci, value=col)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = header_fill

    for ri, row in df.iterrows():
        for ci, val in enumerate(row, start=1):
            ws.cell(row=ri + 2, column=ci, value=val)
