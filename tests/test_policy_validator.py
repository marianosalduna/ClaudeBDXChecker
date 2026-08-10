"""
Unit tests for policy validation (Feature 8).
"""
import unittest
import pandas as pd
import numpy as np

from modules.policy_validator import validate_policies, build_policy_summary


class TestValidatePolicies(unittest.TestCase):
    def _make_df(self, data):
        return pd.DataFrame(data)

    def test_no_issues(self):
        df = self._make_df({
            "Policy Number": ["POL001", "POL002", "POL003"],
            "Net Premium": [1000.0, 2000.0, 3000.0],
        })
        findings, _ = validate_policies(df, ["Policy Number"], ["Net Premium"])
        types = [f.finding_type for f in findings]
        self.assertNotIn("blank_key", types)
        self.assertNotIn("duplicate_policy", types)

    def test_blank_key_detected(self):
        df = self._make_df({
            "Policy Number": ["POL001", None, "POL003"],
            "Net Premium": [1000.0, 2000.0, 3000.0],
        })
        findings, _ = validate_policies(df, ["Policy Number"], ["Net Premium"])
        types = [f.finding_type for f in findings]
        self.assertIn("blank_key", types)
        blank_finding = next(f for f in findings if f.finding_type == "blank_key")
        self.assertEqual(blank_finding.count, 1)

    def test_duplicate_policy_detected(self):
        df = self._make_df({
            "Policy Number": ["POL001", "POL001", "POL002"],
            "Net Premium": [1000.0, 1500.0, 2000.0],
        })
        findings, _ = validate_policies(df, ["Policy Number"], ["Net Premium"])
        types = [f.finding_type for f in findings]
        self.assertIn("duplicate_policy", types)
        dup = next(f for f in findings if f.finding_type == "duplicate_policy")
        self.assertEqual(dup.count, 2)

    def test_blank_financial_detected(self):
        df = self._make_df({
            "Policy Number": ["POL001", "POL002"],
            "Net Premium": [1000.0, None],
        })
        findings, _ = validate_policies(df, ["Policy Number"], ["Net Premium"])
        types = [f.finding_type for f in findings]
        self.assertIn("blank_financial", types)

    def test_unexpected_null_detected(self):
        df = self._make_df({
            "Policy Number": ["POL001", "POL002"],
            "Net Premium": [None, None],
        })
        findings, _ = validate_policies(df, ["Policy Number"], ["Net Premium"])
        types = [f.finding_type for f in findings]
        self.assertIn("unexpected_null", types)

    def test_missing_key_column(self):
        df = self._make_df({"Net Premium": [1000.0]})
        findings, _ = validate_policies(df, ["Policy Number"], ["Net Premium"])
        types = [f.finding_type for f in findings]
        self.assertIn("missing_key", types)

    def test_severity_levels(self):
        df = self._make_df({
            "Policy Number": [None, "POL001"],
            "Net Premium": [1000.0, None],
        })
        findings, _ = validate_policies(df, ["Policy Number"], ["Net Premium"])
        severities = {f.severity for f in findings}
        self.assertTrue(severities.issubset({"CRITICAL", "HIGH", "MEDIUM", "LOW"}))


class TestBuildPolicySummary(unittest.TestCase):
    def test_summary_aggregation(self):
        df = pd.DataFrame({
            "Policy Number": ["POL001", "POL001", "POL002"],
            "Net Premium": [1000.0, 500.0, 2000.0],
            "__row_num__": [1, 2, 3],
        })
        summary = build_policy_summary(df, ["Policy Number"], ["Net Premium"])
        self.assertFalse(summary.empty)
        self.assertIn("Policy Number", summary.columns)

    def test_empty_key_fields(self):
        df = pd.DataFrame({"Net Premium": [1000.0]})
        summary = build_policy_summary(df, [], ["Net Premium"])
        self.assertTrue(summary.empty)


if __name__ == "__main__":
    unittest.main()
