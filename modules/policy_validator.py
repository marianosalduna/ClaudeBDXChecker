"""
Feature 8: Policy-to-Value Validation
Validates that financial values remain properly tied to policy identifiers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass
class PolicyFinding:
    finding_type: str       # "missing_key", "blank_key", "duplicate_policy",
                            # "duplicate_signature", "blank_financial", "unexpected_null"
    severity: str           # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    count: int
    affected_rows: List[int]
    description: str
    example_values: List[str] = field(default_factory=list)


def validate_policies(
    df: pd.DataFrame,
    key_fields: List[str],
    financial_fields: List[str],
    sig_col: str = "__row_signature__",
) -> Tuple[List[PolicyFinding], pd.DataFrame]:
    """
    Run all policy validation checks. Returns (findings, annotated_df).
    """
    findings: List[PolicyFinding] = []
    df = df.copy()
    df["__row_num__"] = range(1, len(df) + 1)

    # 1. Missing / blank key fields
    for kf in key_fields:
        if kf not in df.columns:
            findings.append(PolicyFinding(
                finding_type="missing_key",
                severity="HIGH",
                count=len(df),
                affected_rows=[],
                description=f"Key field '{kf}' not found in the dataset.",
            ))
            continue

        blank_mask = df[kf].isna() | (df[kf].astype(str).str.strip() == "")
        blank_rows = df[blank_mask]["__row_num__"].tolist()
        if blank_rows:
            examples = df[blank_mask].head(5).get(
                financial_fields[0] if financial_fields and financial_fields[0] in df.columns else df.columns[0],
                pd.Series()
            ).astype(str).tolist()
            findings.append(PolicyFinding(
                finding_type="blank_key",
                severity="HIGH",
                count=len(blank_rows),
                affected_rows=blank_rows[:100],
                description=f"Key field '{kf}' is blank in {len(blank_rows):,} row(s).",
                example_values=examples,
            ))

    # 2. Duplicate policy identifiers
    if key_fields:
        valid_keys = [k for k in key_fields if k in df.columns]
        if valid_keys:
            key_combo = df[valid_keys].fillna("").astype(str).agg("|".join, axis=1)
            dup_mask = key_combo.duplicated(keep=False)
            dup_count = dup_mask.sum()
            if dup_count > 0:
                examples = key_combo[dup_mask].head(5).tolist()
                findings.append(PolicyFinding(
                    finding_type="duplicate_policy",
                    severity="HIGH",
                    count=int(dup_count),
                    affected_rows=df[dup_mask]["__row_num__"].tolist()[:100],
                    description=(
                        f"{dup_count:,} row(s) share duplicate key field combination(s). "
                        "Duplicate keys may indicate data entry errors or legitimate "
                        "endorsements — review carefully."
                    ),
                    example_values=examples,
                ))

    # 3. Duplicate row signatures
    if sig_col in df.columns:
        dup_sig_mask = df[sig_col].duplicated(keep=False) & (df[sig_col] != "")
        dup_sig_count = dup_sig_mask.sum()
        if dup_sig_count > 0:
            findings.append(PolicyFinding(
                finding_type="duplicate_signature",
                severity="MEDIUM",
                count=int(dup_sig_count),
                affected_rows=df[dup_sig_mask]["__row_num__"].tolist()[:100],
                description=(
                    f"{dup_sig_count:,} row(s) have identical row-integrity signatures. "
                    "These rows are exact duplicates of key+financial combinations."
                ),
            ))

    # 4. Blank financial values
    for ff in financial_fields:
        if ff not in df.columns:
            continue
        blank_fin_mask = df[ff].isna() | (df[ff].astype(str).str.strip() == "")
        blank_fin_count = blank_fin_mask.sum()
        if blank_fin_count > 0:
            findings.append(PolicyFinding(
                finding_type="blank_financial",
                severity="MEDIUM",
                count=int(blank_fin_count),
                affected_rows=df[blank_fin_mask]["__row_num__"].tolist()[:100],
                description=f"Financial field '{ff}' is blank in {blank_fin_count:,} row(s).",
            ))

    # 5. Populated key with blank ALL financial fields (suspicious nulls)
    if key_fields and financial_fields:
        valid_keys = [k for k in key_fields if k in df.columns]
        valid_fin = [f for f in financial_fields if f in df.columns]
        if valid_keys and valid_fin:
            has_key = df[valid_keys[0]].notna() & (
                df[valid_keys[0]].astype(str).str.strip() != ""
            )
            all_fin_blank = df[valid_fin].isna().all(axis=1) | (
                df[valid_fin].astype(str).apply(lambda r: r.str.strip()).eq("").all(axis=1)
            )
            suspicious = has_key & all_fin_blank
            if suspicious.sum() > 0:
                findings.append(PolicyFinding(
                    finding_type="unexpected_null",
                    severity="MEDIUM",
                    count=int(suspicious.sum()),
                    affected_rows=df[suspicious]["__row_num__"].tolist()[:100],
                    description=(
                        f"{suspicious.sum():,} row(s) have a populated key field but "
                        "all selected financial fields are blank. These may be header/footer "
                        "rows or data entry omissions."
                    ),
                ))

    return findings, df


def build_policy_summary(
    df: pd.DataFrame,
    key_fields: List[str],
    financial_fields: List[str],
) -> pd.DataFrame:
    """Build per-policy aggregation summary."""
    valid_keys = [k for k in key_fields if k in df.columns]
    valid_fin = [f for f in financial_fields if f in df.columns]

    if not valid_keys:
        return pd.DataFrame()

    # Convert financial fields to numeric
    df2 = df.copy()
    for ff in valid_fin:
        df2[ff] = pd.to_numeric(df2[ff], errors="coerce")

    agg_dict: Dict = {"__row_num__": "count"}
    for ff in valid_fin:
        agg_dict[ff] = ["sum", "mean", "min", "max"]

    summary = df2.groupby(valid_keys).agg(agg_dict)
    summary.columns = ["_".join(c).strip("_") for c in summary.columns]
    summary = summary.rename(columns={"__row_num___count": "row_count"})
    return summary.reset_index()
