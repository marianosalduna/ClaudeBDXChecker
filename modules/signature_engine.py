"""
Feature 7: Row Signature / Integrity Hash Engine
Creates SHA-256 row fingerprints from selected key + financial fields.
"""
from __future__ import annotations

import hashlib
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


def build_row_signature(
    df: pd.DataFrame,
    key_fields: List[str],
    financial_fields: List[str],
    separator: str = "|",
) -> pd.Series:
    """
    Compute SHA-256 hash for each row using the selected columns.

    The hash input is:
        key_field_1 | key_field_2 | ... | financial_field_1 | ...

    NaN values are normalised to the string "NULL" before hashing so
    blank cells produce a deterministic (and flaggable) hash.
    """
    all_fields = key_fields + financial_fields
    existing = [f for f in all_fields if f in df.columns]

    if not existing:
        return pd.Series([""] * len(df), index=df.index)

    def _hash_row(row) -> str:
        parts = []
        for f in existing:
            val = row[f]
            if pd.isna(val) or str(val).strip() == "":
                parts.append("NULL")
            else:
                parts.append(str(val).strip())
        raw = separator.join(parts).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    return df[existing].apply(_hash_row, axis=1)


def add_signatures(
    df: pd.DataFrame,
    key_fields: List[str],
    financial_fields: List[str],
) -> pd.DataFrame:
    """Return df with a new column '__row_signature__' appended."""
    df = df.copy()
    df["__row_signature__"] = build_row_signature(df, key_fields, financial_fields)
    return df


def find_duplicate_signatures(df: pd.DataFrame, sig_col: str = "__row_signature__") -> pd.DataFrame:
    """Return rows where the signature appears more than once."""
    if sig_col not in df.columns:
        return pd.DataFrame()
    counts = df[sig_col].value_counts()
    dup_sigs = counts[counts > 1].index
    return df[df[sig_col].isin(dup_sigs)].copy()


def signature_change_count(
    original_sigs: pd.Series,
    sorted_sigs: pd.Series,
) -> int:
    """Count how many positional row signatures differ after a sort."""
    if len(original_sigs) != len(sorted_sigs):
        return max(len(original_sigs), len(sorted_sigs))
    orig = original_sigs.reset_index(drop=True)
    srtd = sorted_sigs.reset_index(drop=True)
    return int((orig != srtd).sum())
