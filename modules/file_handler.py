"""
Feature 1: File Upload & Worksheet Handler
Handles XLSX file loading, sheet selection, and large-file processing.
"""
from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import openpyxl
import pandas as pd
import streamlit as st


@dataclass
class SheetInfo:
    name: str
    row_count: int
    col_count: int
    has_data: bool
    tables: List[str] = field(default_factory=list)
    hidden: bool = False


@dataclass
class WorkbookInfo:
    filename: str
    sheet_names: List[str]
    sheets: Dict[str, SheetInfo]
    workbook: openpyxl.Workbook


def load_workbook_info(uploaded_file) -> WorkbookInfo:
    """Load workbook metadata without reading all data into memory."""
    file_bytes = uploaded_file.read()
    uploaded_file.seek(0)

    wb = openpyxl.load_workbook(
        io.BytesIO(file_bytes),
        read_only=False,
        data_only=True,
        keep_vba=False,
    )

    sheets: Dict[str, SheetInfo] = {}
    for name in wb.sheetnames:
        ws = wb[name]
        tables = list(ws.tables.keys()) if hasattr(ws, "tables") else []
        info = SheetInfo(
            name=name,
            row_count=ws.max_row or 0,
            col_count=ws.max_column or 0,
            has_data=(ws.max_row or 0) > 1,
            tables=tables,
            hidden=(ws.sheet_state != "visible"),
        )
        sheets[name] = info

    return WorkbookInfo(
        filename=uploaded_file.name,
        sheet_names=wb.sheetnames,
        sheets=sheets,
        workbook=wb,
    )


def load_sheet_dataframe(
    uploaded_file,
    sheet_name: str,
    progress_callback=None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load a worksheet into two DataFrames:
      - df_raw  : raw values (used for analysis)
      - df_display : formatted for display (first 1000 rows)

    Returns (df_raw, df_display).
    """
    uploaded_file.seek(0)

    if progress_callback:
        progress_callback(0.1, "Reading file…")

    # Read with pandas – handles large files efficiently
    df_raw = pd.read_excel(
        uploaded_file,
        sheet_name=sheet_name,
        header=0,
        dtype=str,          # keep everything as string initially
        engine="openpyxl",
        na_values=[""],
        keep_default_na=False,
    )

    if progress_callback:
        progress_callback(0.8, "Processing data…")

    # Normalise column names: strip whitespace, keep originals
    df_raw.columns = [str(c).strip() for c in df_raw.columns]

    # Replace literal 'nan' strings that openpyxl sometimes produces
    df_raw = df_raw.replace("nan", np.nan)

    df_display = df_raw.head(1000).copy()

    if progress_callback:
        progress_callback(1.0, "Done.")

    return df_raw, df_display


def get_column_letter(col_index: int) -> str:
    """Convert 0-based column index to Excel letter (A, B, … Z, AA, …)."""
    result = ""
    col = col_index + 1
    while col:
        col, remainder = divmod(col - 1, 26)
        result = chr(65 + remainder) + result
    return result


def get_used_range_info(wb: openpyxl.Workbook, sheet_name: str) -> Dict:
    """Return used-range boundaries and per-column emptiness for a sheet."""
    ws = wb[sheet_name]
    max_row = ws.max_row or 0
    max_col = ws.max_column or 0

    col_has_data: List[bool] = []
    for c in range(1, max_col + 1):
        has_value = False
        for r in range(1, max_row + 1):
            cell = ws.cell(row=r, column=c)
            if cell.value is not None and str(cell.value).strip() != "":
                has_value = True
                break
        col_has_data.append(has_value)

    headers = []
    for c in range(1, max_col + 1):
        cell = ws.cell(row=1, column=c)
        headers.append(cell.value)

    return {
        "max_row": max_row,
        "max_col": max_col,
        "col_has_data": col_has_data,
        "headers": headers,
        "sheet": ws,
    }
