"""
Feature 5: Excel Table Validation
Detects whether worksheet data is stored in a formal Excel Table (ListObject).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import openpyxl


@dataclass
class TableInfo:
    table_name: str
    sheet_name: str
    table_range: str
    display_name: str
    row_count: int
    col_count: int


@dataclass
class TableValidationResult:
    sheet_name: str
    has_table: bool
    tables: List[TableInfo]
    risk_level: str
    message: str
    recommendation: str


def validate_excel_tables(
    wb: openpyxl.Workbook,
    sheet_name: str,
) -> TableValidationResult:
    """Check if the sheet contains Excel Table structures."""
    ws = wb[sheet_name]
    tables: List[TableInfo] = []

    # openpyxl exposes tables as a dict {name: Table}
    if hasattr(ws, "tables") and ws.tables:
        for tname, table in ws.tables.items():
            ref = table.ref  # e.g. "A1:BM50000"
            # Parse range
            try:
                parts = ref.split(":")
                if len(parts) == 2:
                    from openpyxl.utils import range_boundaries
                    min_col, min_row, max_col, max_row = range_boundaries(ref)
                    rows = max_row - min_row
                    cols = max_col - min_col + 1
                else:
                    rows = 0
                    cols = 0
            except Exception:
                rows = 0
                cols = 0

            tables.append(
                TableInfo(
                    table_name=tname,
                    sheet_name=sheet_name,
                    table_range=ref,
                    display_name=getattr(table, "displayName", tname),
                    row_count=rows,
                    col_count=cols,
                )
            )

    has_table = len(tables) > 0

    if has_table:
        tnames = ", ".join(t.table_name for t in tables)
        return TableValidationResult(
            sheet_name=sheet_name,
            has_table=True,
            tables=tables,
            risk_level="LOW",
            message=f"Sheet contains {len(tables)} Excel Table(s): {tnames}. "
                    "Sort and filter operations will move all columns together.",
            recommendation=(
                "Maintain the existing Excel Table structure. "
                "Avoid deleting or modifying the table definition."
            ),
        )
    else:
        return TableValidationResult(
            sheet_name=sheet_name,
            has_table=False,
            tables=[],
            risk_level="MEDIUM",
            message=(
                "This dataset is NOT stored as an Excel Table. "
                "When users apply sort or filter to a plain range, Excel may use "
                "blank columns as the automatic boundary of the selection region."
            ),
            recommendation=(
                "Convert the data range into an Excel Table using Ctrl+T (or Insert → Table). "
                "Excel Tables always sort and filter all columns together, eliminating "
                "the blank-column split risk."
            ),
        )
