"""
Feature 9: Sort Corruption Simulation
Simulates a partial sort (only the pre-split region) and measures row corruption.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from modules.signature_engine import build_row_signature, signature_change_count
from modules.blank_column_detector import DataRegionReport


@dataclass
class SortSimulationResult:
    sheet_name: str
    sort_column: str
    total_rows: int
    corrupted_rows: int
    corruption_pct: float
    split_column: str
    before_split_cols: List[str]
    after_split_cols: List[str]
    before_sample: pd.DataFrame    # first 10 rows before sort
    after_sample: pd.DataFrame     # first 10 rows after partial sort
    full_sort_sample: pd.DataFrame # first 10 rows after full sort
    risk_level: str
    description: str


def simulate_sort_corruption(
    df: pd.DataFrame,
    region_report: DataRegionReport,
    key_fields: List[str],
    financial_fields: List[str],
    sort_column: Optional[str] = None,
) -> Optional[SortSimulationResult]:
    """
    Simulate a partial sort using only the pre-split region.

    Returns None if there is no split point (no blank column).
    """
    if not region_report.split_points:
        return None

    first_split = region_report.split_points[0]
    regions = region_report.regions

    if len(regions) < 2:
        return None

    # Columns before and after the split
    pre_split_cols = [c for r in regions[:1] for c in r["cols"]]
    post_split_cols = [c for r in regions[1:] for c in r["cols"]]

    # Restrict to actual DataFrame columns
    df_cols = list(df.columns)
    pre_split_df_cols = [c for c in pre_split_cols if c in df_cols]
    post_split_df_cols = [c for c in post_split_cols if c in df_cols]

    if not pre_split_df_cols:
        return None

    # Choose a sort column from pre-split region
    if sort_column and sort_column in pre_split_df_cols:
        sc = sort_column
    elif key_fields and key_fields[0] in pre_split_df_cols:
        sc = key_fields[0]
    elif pre_split_df_cols:
        sc = pre_split_df_cols[0]
    else:
        return None

    n = len(df)

    # Original signatures (using all configured fields)
    all_fields = key_fields + financial_fields
    existing_fields = [f for f in all_fields if f in df.columns]

    orig_sigs = build_row_signature(df, key_fields, financial_fields)

    # --- Partial sort: sort only the pre-split portion of columns ---
    # In the corruption scenario, rows in the pre-split region are sorted
    # but rows in the post-split region are NOT. We simulate by:
    # 1. Computing sort order from pre-split columns
    # 2. Rearranging pre-split columns but leaving post-split columns at original positions

    sort_order = (
        df[sc]
        .astype(str)
        .rank(method="first")
        .argsort()
        .reset_index(drop=True)
    )

    # Build the "partially sorted" dataframe
    df_partial = df.copy().reset_index(drop=True)

    # Reorder pre-split cols by sort order
    for col in pre_split_df_cols:
        df_partial[col] = df[col].iloc[sort_order].values

    # post-split cols stay as-is (the corruption!)

    # Now compute signatures on the partial-sort result
    partial_sigs = build_row_signature(df_partial, key_fields, financial_fields)

    corrupted = signature_change_count(orig_sigs, partial_sigs)
    corruption_pct = round(corrupted / n * 100, 2) if n > 0 else 0.0

    # Full sort (what should happen)
    df_full_sorted = df.sort_values(by=sc, na_position="last").reset_index(drop=True)

    # Sample views (use only a subset of columns for display clarity)
    display_cols = _select_display_cols(df, key_fields, financial_fields, pre_split_df_cols, post_split_df_cols)

    before_sample = df[display_cols].head(10).reset_index(drop=True)
    after_sample = df_partial[display_cols].head(10).reset_index(drop=True)
    full_sort_sample = df_full_sorted[display_cols].head(10).reset_index(drop=True)

    risk = "CRITICAL" if corruption_pct > 50 else ("HIGH" if corruption_pct > 20 else "MEDIUM")

    desc = (
        f"Simulated partial sort on column '{sc}' using only the pre-split region "
        f"({regions[0]['start']}:{regions[0]['end']}). "
        f"An estimated {corrupted:,} of {n:,} rows ({corruption_pct}%) have mismatched "
        "key-to-value relationships in the post-split region after a user performs a "
        f"standard Excel sort. Split caused by blank column {first_split}."
    )

    return SortSimulationResult(
        sheet_name=region_report.sheet_name,
        sort_column=sc,
        total_rows=n,
        corrupted_rows=corrupted,
        corruption_pct=corruption_pct,
        split_column=first_split,
        before_split_cols=pre_split_df_cols,
        after_split_cols=post_split_df_cols,
        before_sample=before_sample,
        after_sample=after_sample,
        full_sort_sample=full_sort_sample,
        risk_level=risk,
        description=desc,
    )


def _select_display_cols(df, key_fields, financial_fields, pre_cols, post_cols):
    """Pick up to 6 columns for the before/after sample display."""
    chosen = []
    for f in key_fields:
        if f in df.columns and f not in chosen:
            chosen.append(f)
            if len(chosen) >= 2:
                break
    for f in financial_fields:
        if f in df.columns and f not in chosen:
            chosen.append(f)
            if len(chosen) >= 4:
                break
    # Add first pre and post col if not already present
    if pre_cols and pre_cols[0] not in chosen and pre_cols[0] in df.columns:
        chosen.append(pre_cols[0])
    if post_cols and post_cols[0] not in chosen and post_cols[0] in df.columns:
        chosen.append(post_cols[0])
    return chosen if chosen else list(df.columns[:6])
