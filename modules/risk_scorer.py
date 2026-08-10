"""
Feature 12: Risk Scoring Engine
Aggregates findings into severity-levelled scores at finding/sheet/workbook level.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from modules.blank_column_detector import BlankColumnFinding, DataRegionReport
from modules.excel_table_validator import TableValidationResult
from modules.policy_validator import PolicyFinding
from modules.sort_simulator import SortSimulationResult
from modules.tieout_engine import TieOutReport


SEVERITY_WEIGHT = {
    "CRITICAL": 30,
    "HIGH": 15,
    "MEDIUM": 7,
    "LOW": 2,
}


@dataclass
class RiskScore:
    sheet_name: str
    overall_score: int          # 0 (worst) to 100 (best)
    risk_level: str             # CRITICAL / HIGH / MEDIUM / LOW
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    findings_summary: List[Dict]


@dataclass
class WorkbookRiskReport:
    filename: str
    workbook_score: int
    workbook_risk: str
    sheet_scores: Dict[str, RiskScore]
    top_findings: List[Dict]


def score_sheet(
    sheet_name: str,
    blank_findings: List[BlankColumnFinding],
    region_report: Optional[DataRegionReport],
    table_result: Optional[TableValidationResult],
    policy_findings: List[PolicyFinding],
    sort_sim: Optional[SortSimulationResult],
    tieout: Optional[TieOutReport],
) -> RiskScore:
    """Compute a 0-100 integrity score for a single sheet."""
    penalties: List[Dict] = []

    # Blank column findings
    for f in blank_findings:
        w = SEVERITY_WEIGHT.get(f.risk_level, 2)
        penalties.append({
            "severity": f.risk_level,
            "weight": w,
            "description": f"Blank column {f.col_letter} splits dataset",
            "category": "structure",
        })

    # Multiple internal blanks = extra penalty
    if region_report and region_report.internal_blank_count >= 2:
        penalties.append({
            "severity": "CRITICAL",
            "weight": SEVERITY_WEIGHT["CRITICAL"],
            "description": f"Multiple ({region_report.internal_blank_count}) internal blank columns",
            "category": "structure",
        })

    # Sort simulation
    if sort_sim and sort_sim.corruption_pct > 0:
        sev = sort_sim.risk_level
        penalties.append({
            "severity": sev,
            "weight": SEVERITY_WEIGHT.get(sev, 7),
            "description": f"Sort simulation: {sort_sim.corruption_pct}% rows potentially corrupted",
            "category": "sort_corruption",
        })

    # Table validation
    if table_result and not table_result.has_table:
        penalties.append({
            "severity": "MEDIUM",
            "weight": SEVERITY_WEIGHT["MEDIUM"],
            "description": "Data not stored as Excel Table",
            "category": "structure",
        })

    # Policy findings
    for pf in policy_findings:
        w = SEVERITY_WEIGHT.get(pf.severity, 2)
        penalties.append({
            "severity": pf.severity,
            "weight": w,
            "description": pf.description[:120],
            "category": "data_integrity",
        })

    # Tieout anomalies
    if tieout:
        for anomaly in tieout.anomalies:
            w = SEVERITY_WEIGHT.get(anomaly.risk_level, 2)
            penalties.append({
                "severity": anomaly.risk_level,
                "weight": w,
                "description": anomaly.description[:120],
                "category": "tieout",
            })

    # Calculate score
    total_penalty = sum(p["weight"] for p in penalties)
    score = max(0, 100 - total_penalty)

    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for p in penalties:
        sev = p["severity"]
        if sev in counts:
            counts[sev] += 1

    risk_level = (
        "CRITICAL" if counts["CRITICAL"] > 0 else
        "HIGH" if counts["HIGH"] > 0 else
        "MEDIUM" if counts["MEDIUM"] > 0 else
        "LOW"
    )

    return RiskScore(
        sheet_name=sheet_name,
        overall_score=score,
        risk_level=risk_level,
        critical_count=counts["CRITICAL"],
        high_count=counts["HIGH"],
        medium_count=counts["MEDIUM"],
        low_count=counts["LOW"],
        findings_summary=penalties,
    )


def score_workbook(
    filename: str,
    sheet_scores: Dict[str, RiskScore],
) -> WorkbookRiskReport:
    """Aggregate sheet scores into a workbook-level report."""
    if not sheet_scores:
        return WorkbookRiskReport(filename, 100, "LOW", {}, [])

    avg_score = int(sum(s.overall_score for s in sheet_scores.values()) / len(sheet_scores))

    workbook_risk = (
        "CRITICAL" if any(s.risk_level == "CRITICAL" for s in sheet_scores.values()) else
        "HIGH" if any(s.risk_level == "HIGH" for s in sheet_scores.values()) else
        "MEDIUM" if any(s.risk_level == "MEDIUM" for s in sheet_scores.values()) else
        "LOW"
    )

    # Collect top findings across all sheets
    all_findings = []
    for sheet_name, rs in sheet_scores.items():
        for f in rs.findings_summary:
            all_findings.append({**f, "sheet": sheet_name})

    # Sort by severity weight desc
    top_findings = sorted(all_findings, key=lambda x: x["weight"], reverse=True)[:20]

    return WorkbookRiskReport(
        filename=filename,
        workbook_score=avg_score,
        workbook_risk=workbook_risk,
        sheet_scores=sheet_scores,
        top_findings=top_findings,
    )


def risk_color(level: str) -> str:
    """Return a hex color for a risk level (for display)."""
    return {
        "CRITICAL": "#d32f2f",
        "HIGH": "#f57c00",
        "MEDIUM": "#fbc02d",
        "LOW": "#388e3c",
    }.get(level, "#757575")


def score_badge(score: int) -> str:
    if score >= 90:
        return "Excellent"
    elif score >= 75:
        return "Good"
    elif score >= 50:
        return "Fair"
    elif score >= 25:
        return "Poor"
    return "Critical"
