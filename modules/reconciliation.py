"""
Feature 10: Reconciliation Controls
Generates reconciliation metrics and summary dashboard data.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass
class FinancialSummary:
    field_name: str
    total: float
    average: float
    minimum: float
    maximum: float
    count_non_null: int
    count_null: int
    pct_null: float


@dataclass
class ReconciliationReport:
    sheet_name: str
    total_rows: int
    unique_policy_count: int
    duplicate_count: int
    missing_key_count: int
    financial_summaries: List[FinancialSummary]
    key_fields_used: List[str]
    financial_fields_used: List[str]


def build_reconciliation_report(
    df: pd.DataFrame,
    key_fields: List[str],
    financial_fields: List[str],
    sheet_name: str = "Sheet1",
) -> ReconciliationReport:
    """Compute all reconciliation metrics."""
    n = len(df)

    # Key field stats
    valid_keys = [k for k in key_fields if k in df.columns]
    if valid_keys:
        key_combo = df[valid_keys].fillna("").astype(str).agg("|".join, axis=1)
        unique_count = key_combo.nunique()
        dup_count = int(key_combo.duplicated(keep=False).sum())
        blank_key = df[valid_keys[0]].isna() | (df[valid_keys[0]].astype(str).str.strip() == "")
        missing_key_count = int(blank_key.sum())
    else:
        unique_count = 0
        dup_count = 0
        missing_key_count = 0

    # Financial summaries
    financial_summaries: List[FinancialSummary] = []
    for ff in financial_fields:
        if ff not in df.columns:
            continue
        series = pd.to_numeric(df[ff], errors="coerce")
        null_count = int(series.isna().sum())
        non_null_count = n - null_count
        pct_null = round(null_count / n * 100, 2) if n > 0 else 0.0
        financial_summaries.append(FinancialSummary(
            field_name=ff,
            total=float(series.sum()),
            average=float(series.mean()) if non_null_count > 0 else 0.0,
            minimum=float(series.min()) if non_null_count > 0 else 0.0,
            maximum=float(series.max()) if non_null_count > 0 else 0.0,
            count_non_null=non_null_count,
            count_null=null_count,
            pct_null=pct_null,
        ))

    return ReconciliationReport(
        sheet_name=sheet_name,
        total_rows=n,
        unique_policy_count=unique_count,
        duplicate_count=dup_count,
        missing_key_count=missing_key_count,
        financial_summaries=financial_summaries,
        key_fields_used=valid_keys,
        financial_fields_used=[ff for ff in financial_fields if ff in df.columns],
    )


def format_currency(value: float) -> str:
    """Format a float as a currency string."""
    if abs(value) >= 1_000_000:
        return f"${value:,.0f}"
    return f"${value:,.2f}"
