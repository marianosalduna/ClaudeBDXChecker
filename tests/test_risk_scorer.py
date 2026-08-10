"""
Unit tests for the risk scoring engine (Feature 12).
"""
import unittest
from unittest.mock import MagicMock

from modules.risk_scorer import score_sheet, score_workbook, risk_color, score_badge, RiskScore
from modules.blank_column_detector import BlankColumnFinding, DataRegionReport
from modules.policy_validator import PolicyFinding


def _make_blank_finding(risk_level="CRITICAL"):
    return BlankColumnFinding(
        sheet_name="Sheet1",
        col_index=8,
        col_letter="I",
        col_header=None,
        position="internal",
        risk_level=risk_level,
        description="Test blank column",
    )


def _make_policy_finding(severity="HIGH", finding_type="blank_key"):
    return PolicyFinding(
        finding_type=finding_type,
        severity=severity,
        count=5,
        affected_rows=[1, 2, 3, 4, 5],
        description="Test policy finding",
    )


def _make_region_report(blank_count=0):
    return DataRegionReport(
        sheet_name="Sheet1",
        total_columns=20,
        populated_columns=list("ABCDEFGHIJKLMN"),
        blank_columns=[],
        split_points=[],
        regions=[],
        affected_region=None,
        internal_blank_count=blank_count,
        risk_level="LOW" if blank_count == 0 else "CRITICAL",
    )


class TestScoreSheet(unittest.TestCase):
    def test_perfect_score_no_findings(self):
        result = score_sheet("Sheet1", [], _make_region_report(), None, [], None, None)
        self.assertEqual(result.overall_score, 100)
        self.assertEqual(result.risk_level, "LOW")

    def test_critical_finding_reduces_score(self):
        findings = [_make_blank_finding("CRITICAL")]
        result = score_sheet("Sheet1", findings, _make_region_report(), None, [], None, None)
        self.assertLess(result.overall_score, 100)
        self.assertEqual(result.risk_level, "CRITICAL")
        self.assertEqual(result.critical_count, 1)

    def test_high_finding(self):
        policy_findings = [_make_policy_finding("HIGH")]
        result = score_sheet("Sheet1", [], _make_region_report(), None, policy_findings, None, None)
        self.assertLess(result.overall_score, 100)
        self.assertEqual(result.risk_level, "HIGH")

    def test_multiple_blank_columns_extra_penalty(self):
        findings = [_make_blank_finding("CRITICAL"), _make_blank_finding("CRITICAL")]
        region = _make_region_report(blank_count=2)
        result = score_sheet("Sheet1", findings, region, None, [], None, None)
        # Should have extra penalty for multiple blanks
        self.assertLess(result.overall_score, 40)

    def test_score_clamped_to_zero(self):
        findings = [_make_blank_finding("CRITICAL")] * 10
        result = score_sheet("Sheet1", findings, _make_region_report(), None,
                             [_make_policy_finding("CRITICAL")] * 5, None, None)
        self.assertGreaterEqual(result.overall_score, 0)


class TestScoreWorkbook(unittest.TestCase):
    def test_empty_workbook(self):
        result = score_workbook("test.xlsx", {})
        self.assertEqual(result.workbook_score, 100)
        self.assertEqual(result.workbook_risk, "LOW")

    def test_single_sheet(self):
        rs = RiskScore("Sheet1", 60, "HIGH", 0, 2, 0, 0, [])
        result = score_workbook("test.xlsx", {"Sheet1": rs})
        self.assertEqual(result.workbook_score, 60)
        self.assertEqual(result.workbook_risk, "HIGH")

    def test_multiple_sheets_worst_risk_wins(self):
        rs1 = RiskScore("Sheet1", 90, "LOW", 0, 0, 0, 1, [])
        rs2 = RiskScore("Sheet2", 20, "CRITICAL", 2, 0, 0, 0, [])
        result = score_workbook("test.xlsx", {"Sheet1": rs1, "Sheet2": rs2})
        self.assertEqual(result.workbook_risk, "CRITICAL")
        self.assertEqual(result.workbook_score, 55)  # average of 90 and 20


class TestRiskColor(unittest.TestCase):
    def test_known_levels(self):
        self.assertEqual(risk_color("CRITICAL"), "#d32f2f")
        self.assertEqual(risk_color("HIGH"), "#f57c00")
        self.assertEqual(risk_color("MEDIUM"), "#fbc02d")
        self.assertEqual(risk_color("LOW"), "#388e3c")

    def test_unknown_level(self):
        self.assertEqual(risk_color("UNKNOWN"), "#757575")


class TestScoreBadge(unittest.TestCase):
    def test_score_labels(self):
        self.assertEqual(score_badge(95), "Excellent")
        self.assertEqual(score_badge(80), "Good")
        self.assertEqual(score_badge(60), "Fair")
        self.assertEqual(score_badge(30), "Poor")
        self.assertEqual(score_badge(10), "Critical")


if __name__ == "__main__":
    unittest.main()
