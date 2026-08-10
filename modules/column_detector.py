"""
Feature 2: Automatic Column Detection & Header Matching
Scores headers against known patterns and recommends likely mappings.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pandas as pd


# ---------------------------------------------------------------------------
# Pattern libraries
# ---------------------------------------------------------------------------

POLICY_ID_PATTERNS = [
    (r"\bpolicy\s*(number|no|#|num|id)\b", 98),
    (r"\bpolicy\b", 80),
    (r"\bcertificate\s*(number|no|#|num|id|cert)\b", 96),
    (r"\bcert\s*(number|no|#|num|id)\b", 92),
    (r"\bclaim\s*(number|no|#|num|id)\b", 90),
    (r"\bclaim\s*id\b", 90),
    (r"\brecord\s*(number|no|#|num|id)\b", 85),
    (r"\bcontract\s*(number|no|#|num|id)\b", 88),
    (r"\binsured\s*(id|number|no)\b", 82),
    (r"\bref(erence)?\s*(number|no|#|id)?\b", 70),
    (r"\bpol\s*(no|#|num|id)\b", 88),
]

FINANCIAL_PATTERNS = [
    (r"\bnet\s*due\b", 98),
    (r"\bnet\s*premium\b", 96),
    (r"\bnet\s*amount\b", 90),
    (r"\bnet\b", 70),
    (r"\bgross\s*premium\b", 96),
    (r"\bgross\b", 72),
    (r"\bpremium\b", 88),
    (r"\bcommission\b", 92),
    (r"\bagent\s*commission\b", 94),
    (r"\btax(es)?\b", 86),
    (r"\bdue\s*to\s*broker\b", 92),
    (r"\bdue\s*to\s*insurer\b", 92),
    (r"\bamount\s*due\b", 90),
    (r"\bwritten\s*premium\b", 94),
    (r"\bfee\b", 65),
    (r"\bcharge\b", 60),
    (r"\bpayment\b", 62),
    (r"\bvalue\b", 55),
    (r"\bsum\b", 55),
]

DATE_PATTERNS = [
    (r"\binception\b", 88),
    (r"\bexpiry\b", 88),
    (r"\bexpiration\b", 86),
    (r"\beffective\b", 80),
    (r"\bstart\s*date\b", 82),
    (r"\bend\s*date\b", 82),
    (r"\bdate\b", 65),
    (r"\byear\b", 55),
    (r"\bmonth\b", 50),
]


@dataclass
class ColumnMatch:
    column_name: str
    column_index: int
    category: str          # "policy_id", "financial", "date", "unknown"
    confidence: int        # 0-100
    pattern_matched: str
    sample_values: List[str] = field(default_factory=list)


def _score_header(header: str, patterns: List[Tuple[str, int]]) -> Tuple[int, str]:
    """Return (best_score, pattern_that_matched)."""
    h = str(header).lower().strip()
    best_score = 0
    best_pat = ""
    for pattern, score in patterns:
        if re.search(pattern, h):
            if score > best_score:
                best_score = score
                best_pat = pattern
    return best_score, best_pat


def detect_columns(df: pd.DataFrame) -> Dict[str, List[ColumnMatch]]:
    """
    Analyse DataFrame headers and return categorised matches.

    Returns dict with keys: "policy_id", "financial", "date", "unknown".
    """
    results: Dict[str, List[ColumnMatch]] = {
        "policy_id": [],
        "financial": [],
        "date": [],
        "unknown": [],
    }

    for idx, col in enumerate(df.columns):
        pol_score, pol_pat = _score_header(col, POLICY_ID_PATTERNS)
        fin_score, fin_pat = _score_header(col, FINANCIAL_PATTERNS)
        dat_score, dat_pat = _score_header(col, DATE_PATTERNS)

        # Sample non-null values
        sample = df[col].dropna().head(5).astype(str).tolist()

        best = max(pol_score, fin_score, dat_score)

        if best == 0:
            results["unknown"].append(
                ColumnMatch(col, idx, "unknown", 0, "", sample)
            )
        elif best == pol_score and pol_score >= fin_score and pol_score >= dat_score:
            results["policy_id"].append(
                ColumnMatch(col, idx, "policy_id", pol_score, pol_pat, sample)
            )
        elif best == fin_score and fin_score >= dat_score:
            results["financial"].append(
                ColumnMatch(col, idx, "financial", fin_score, fin_pat, sample)
            )
        else:
            results["date"].append(
                ColumnMatch(col, idx, "date", dat_score, dat_pat, sample)
            )

    # Sort each category by confidence descending
    for cat in results:
        results[cat].sort(key=lambda x: x.confidence, reverse=True)

    return results


def get_top_recommendations(
    matches: Dict[str, List[ColumnMatch]],
    n_policy: int = 3,
    n_financial: int = 5,
) -> Dict[str, List[ColumnMatch]]:
    """Return top-N recommendations per category."""
    return {
        "policy_id": matches["policy_id"][:n_policy],
        "financial": matches["financial"][:n_financial],
        "date": matches["date"][:3],
    }


def confidence_label(score: int) -> str:
    if score >= 90:
        return "Very High"
    elif score >= 75:
        return "High"
    elif score >= 55:
        return "Medium"
    elif score > 0:
        return "Low"
    return "None"
