"""
Feature 15: Recommendation Engine
Generates actionable, prioritised recommendations from all findings.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from modules.blank_column_detector import BlankColumnFinding, DataRegionReport
from modules.excel_table_validator import TableValidationResult
from modules.policy_validator import PolicyFinding
from modules.sort_simulator import SortSimulationResult
from modules.tieout_engine import TieOutReport


@dataclass
class Recommendation:
    priority: int           # 1 = highest
    severity: str
    category: str
    title: str
    detail: str
    action: str


def generate_recommendations(
    blank_findings: List[BlankColumnFinding],
    region_report: Optional[DataRegionReport],
    table_result: Optional[TableValidationResult],
    policy_findings: List[PolicyFinding],
    sort_sim: Optional[SortSimulationResult],
    tieout: Optional[TieOutReport],
) -> List[Recommendation]:
    """Generate a prioritised list of actionable recommendations."""
    recs: List[Recommendation] = []
    priority = 1

    # Blank column recommendations
    for bf in blank_findings:
        recs.append(Recommendation(
            priority=priority,
            severity="CRITICAL",
            category="Structure",
            title=f"Remove blank column {bf.col_letter}",
            detail=(
                f"Column {bf.col_letter} is completely blank and sits between populated columns. "
                "This causes Excel to treat it as the boundary of the data range, "
                "so sorting or filtering operations will only move the columns before it."
            ),
            action=(
                f"Delete column {bf.col_letter} from the worksheet, or populate it with a "
                "meaningful value. After deletion, verify that the data range is contiguous "
                "from column A to the last populated column."
            ),
        ))
        priority += 1

    # Sort simulation
    if sort_sim and sort_sim.corruption_pct > 0:
        recs.append(Recommendation(
            priority=priority,
            severity="CRITICAL",
            category="Sort Risk",
            title="Avoid sorting partial data ranges",
            detail=(
                f"The sort simulation shows that {sort_sim.corruption_pct}% of rows "
                f"({sort_sim.corrupted_rows:,} of {sort_sim.total_rows:,}) may have "
                "their policy-to-value relationships broken if a user sorts only the "
                f"pre-split region ({', '.join(sort_sim.before_split_cols[:3])} …)."
            ),
            action=(
                "Instruct users to always select the entire data range (Ctrl+Shift+End) "
                "before sorting, or convert the data into an Excel Table which enforces "
                "full-range sorting automatically."
            ),
        ))
        priority += 1

    # Excel Table
    if table_result and not table_result.has_table:
        recs.append(Recommendation(
            priority=priority,
            severity="MEDIUM",
            category="Structure",
            title="Convert data range to an Excel Table",
            detail=(
                "The dataset is stored as a plain range, not an Excel Table. "
                "Excel Tables automatically include all columns in sort and filter operations, "
                "eliminating the blank-column split risk."
            ),
            action=(
                "Select any cell in the data range and press Ctrl+T (or go to Insert → Table). "
                "Ensure 'My table has headers' is checked. The table will highlight the full "
                "data boundary and protect against partial sorts."
            ),
        ))
        priority += 1

    # Policy findings
    for pf in policy_findings:
        if pf.finding_type == "blank_key":
            recs.append(Recommendation(
                priority=priority,
                severity=pf.severity,
                category="Data Integrity",
                title="Populate missing key field values",
                detail=pf.description,
                action=(
                    "Review and populate blank key fields. If these represent valid records "
                    "without a policy number, assign a placeholder (e.g. 'UNASSIGNED-001') "
                    "to preserve data integrity during tie-out."
                ),
            ))
            priority += 1
        elif pf.finding_type == "duplicate_policy":
            recs.append(Recommendation(
                priority=priority,
                severity=pf.severity,
                category="Data Integrity",
                title="Review duplicate policy identifiers",
                detail=pf.description,
                action=(
                    "Determine whether duplicates are intentional (e.g. mid-term endorsements, "
                    "installment premiums) or data entry errors. Add a transaction-type column "
                    "to distinguish multiple entries for the same policy."
                ),
            ))
            priority += 1

    # Tie-out anomalies
    if tieout:
        for anomaly in tieout.anomalies:
            recs.append(Recommendation(
                priority=priority,
                severity=anomaly.risk_level,
                category="Tie-Out",
                title=_anomaly_title(anomaly.anomaly_type),
                detail=anomaly.description,
                action=_anomaly_action(anomaly.anomaly_type),
            ))
            priority += 1

    # General best-practice if no critical issues
    if not blank_findings and not (sort_sim and sort_sim.corruption_pct > 0):
        recs.append(Recommendation(
            priority=priority,
            severity="LOW",
            category="Best Practice",
            title="Add policy-value integrity validation to your BDX workflow",
            detail="No critical structural issues were found in this file.",
            action=(
                "Schedule regular BDX integrity checks before approval. "
                "Consider adding a row-signature column to the workbook that "
                "can be compared after each data transformation."
            ),
        ))

    return sorted(recs, key=lambda r: (
        {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}.get(r.severity, 4),
        r.priority,
    ))


def _anomaly_title(atype: str) -> str:
    return {
        "conflicting_amounts": "Resolve conflicting amounts for duplicate policies",
        "blank_key_with_value": "Assign keys to records with financial amounts",
        "key_with_blank_values": "Review records with populated keys but blank amounts",
        "value_inconsistency": "Investigate inconsistent financial values",
    }.get(atype, "Review tie-out anomaly")


def _anomaly_action(atype: str) -> str:
    return {
        "conflicting_amounts": (
            "Review each duplicate policy key and determine the correct amount. "
            "Consider adding an endorsement-type flag to distinguish transaction rows."
        ),
        "blank_key_with_value": (
            "Assign a policy key to these records, or move them to a separate "
            "'Unallocated' section with clear labelling."
        ),
        "key_with_blank_values": (
            "Confirm whether zero-value records are intentional (e.g. cancelled policies). "
            "If so, populate the financial field with 0 rather than leaving it blank."
        ),
        "value_inconsistency": (
            "Review records with the same key but different financial combinations "
            "and determine which is the authoritative value."
        ),
    }.get(atype, "Review and correct the identified anomaly.")
