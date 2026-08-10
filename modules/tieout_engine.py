"""
Feature 11: Advanced Policy/Value Tie-Out Engine
Builds policy-to-value relationship maps and integrity fingerprints.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass
class TieOutAnomaly:
    anomaly_type: str       # "conflicting_amounts", "blank_key_with_value",
                            # "key_with_blank_values", "value_inconsistency"
    risk_level: str
    count: int
    affected_keys: List[str]
    description: str
    sample_data: Optional[pd.DataFrame] = None


@dataclass
class TieOutReport:
    sheet_name: str
    total_relationships: int
    unique_keys: int
    anomalies: List[TieOutAnomaly]
    overall_risk: str
    integrity_score: int    # 0-100, higher = better
    policy_value_map: Optional[pd.DataFrame] = None


def run_tieout(
    df: pd.DataFrame,
    key_fields: List[str],
    financial_fields: List[str],
    sheet_name: str = "Sheet1",
) -> TieOutReport:
    """Run the full tie-out analysis."""
    anomalies: List[TieOutAnomaly] = []
    n = len(df)

    valid_keys = [k for k in key_fields if k in df.columns]
    valid_fin = [f for f in financial_fields if f in df.columns]

    if not valid_keys or not valid_fin:
        return TieOutReport(
            sheet_name=sheet_name,
            total_relationships=0,
            unique_keys=0,
            anomalies=[],
            overall_risk="LOW",
            integrity_score=100,
        )

    df2 = df.copy()

    # Normalise financial to numeric
    for ff in valid_fin:
        df2[ff] = pd.to_numeric(df2[ff], errors="coerce")

    key_combo = df2[valid_keys].fillna("").astype(str).agg("|".join, axis=1)
    df2["__key_combo__"] = key_combo
    unique_keys = int(key_combo.nunique())

    # 1. Blank key with populated amounts
    blank_key_mask = df2[valid_keys[0]].isna() | (
        df2[valid_keys[0]].astype(str).str.strip() == ""
    )
    has_fin_mask = df2[valid_fin].notna().any(axis=1)
    blank_key_with_value = blank_key_mask & has_fin_mask
    if blank_key_with_value.sum() > 0:
        anomalies.append(TieOutAnomaly(
            anomaly_type="blank_key_with_value",
            risk_level="HIGH",
            count=int(blank_key_with_value.sum()),
            affected_keys=[],
            description=(
                f"{blank_key_with_value.sum():,} row(s) have a blank key field "
                "but non-blank financial amounts. These records cannot be tied out "
                "to any policy identifier."
            ),
            sample_data=df2[blank_key_with_value][valid_keys + valid_fin].head(5),
        ))

    # 2. Populated key with all blank financial fields
    has_key_mask = ~blank_key_mask
    all_fin_blank = df2[valid_fin].isna().all(axis=1)
    key_no_value = has_key_mask & all_fin_blank
    if key_no_value.sum() > 0:
        anomalies.append(TieOutAnomaly(
            anomaly_type="key_with_blank_values",
            risk_level="MEDIUM",
            count=int(key_no_value.sum()),
            affected_keys=df2[key_no_value]["__key_combo__"].head(10).tolist(),
            description=(
                f"{key_no_value.sum():,} row(s) have a policy key but ALL selected "
                "financial fields are blank. These may be placeholder or summary rows."
            ),
            sample_data=df2[key_no_value][valid_keys + valid_fin].head(5),
        ))

    # 3. Duplicate policy with conflicting financial amounts
    dup_keys = key_combo[key_combo.duplicated(keep=False)]
    if len(dup_keys) > 0:
        grouped = df2[df2["__key_combo__"].isin(dup_keys.unique())].groupby("__key_combo__")
        conflicting = []
        for key_val, group in grouped:
            for ff in valid_fin:
                if group[ff].nunique(dropna=False) > 1:
                    conflicting.append(key_val)
                    break

        conflicting = list(set(conflicting))
        if conflicting:
            anomalies.append(TieOutAnomaly(
                anomaly_type="conflicting_amounts",
                risk_level="HIGH",
                count=len(conflicting),
                affected_keys=conflicting[:10],
                description=(
                    f"{len(conflicting):,} policy key(s) appear multiple times with "
                    "different financial amounts — indicating potential double-counting, "
                    "endorsements without clear labelling, or data integrity issues."
                ),
                sample_data=df2[df2["__key_combo__"].isin(conflicting[:3])][valid_keys + valid_fin].head(10),
            ))

    # 4. Build policy-value map
    agg = {ff: ["sum", "count", "nunique"] for ff in valid_fin}
    policy_map = df2.groupby(valid_keys, as_index=False).agg(agg)
    policy_map.columns = [
        "_".join(filter(None, c)).strip("_") if isinstance(c, tuple) else c
        for c in policy_map.columns
    ]

    # Integrity score
    penalty = sum(
        10 if a.risk_level == "CRITICAL" else
        7 if a.risk_level == "HIGH" else
        4 if a.risk_level == "MEDIUM" else 1
        for a in anomalies
    )
    integrity_score = max(0, 100 - penalty)

    overall_risk = (
        "CRITICAL" if any(a.risk_level == "CRITICAL" for a in anomalies) else
        "HIGH" if any(a.risk_level == "HIGH" for a in anomalies) else
        "MEDIUM" if any(a.risk_level == "MEDIUM" for a in anomalies) else
        "LOW"
    )

    return TieOutReport(
        sheet_name=sheet_name,
        total_relationships=n,
        unique_keys=unique_keys,
        anomalies=anomalies,
        overall_risk=overall_risk,
        integrity_score=integrity_score,
        policy_value_map=policy_map,
    )
