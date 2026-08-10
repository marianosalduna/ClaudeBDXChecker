"""
Unit tests for the sort corruption simulator (Feature 9).
"""
import unittest
import pandas as pd
import numpy as np

from modules.sort_simulator import simulate_sort_corruption
from modules.blank_column_detector import DataRegionReport


def _make_region_report(has_split=True):
    if has_split:
        return DataRegionReport(
            sheet_name="Sheet1",
            total_columns=6,
            populated_columns=["A", "B", "C", "D", "E", "F"],
            blank_columns=["C"],
            split_points=["C"],
            regions=[
                {"start": "A", "end": "B", "start_idx": 0, "end_idx": 1,
                 "cols": ["A", "B"], "count": 2},
                {"start": "D", "end": "F", "start_idx": 3, "end_idx": 5,
                 "cols": ["D", "E", "F"], "count": 3},
            ],
            affected_region={"start": "D", "end": "F", "cols": ["D", "E", "F"], "count": 3},
            internal_blank_count=1,
            risk_level="CRITICAL",
        )
    else:
        return DataRegionReport(
            sheet_name="Sheet1",
            total_columns=4,
            populated_columns=["A", "B", "C", "D"],
            blank_columns=[],
            split_points=[],
            regions=[{"start": "A", "end": "D", "start_idx": 0, "end_idx": 3,
                      "cols": ["A", "B", "C", "D"], "count": 4}],
            affected_region=None,
            internal_blank_count=0,
            risk_level="LOW",
        )


class TestSimulateSortCorruption(unittest.TestCase):
    def _make_df(self, n=50):
        np.random.seed(1)
        return pd.DataFrame({
            "A": [f"POL{i:03d}" for i in range(n)],
            "B": np.random.randint(1000, 9999, n).astype(str),
            "D": np.random.uniform(100, 10000, n).round(2).astype(str),
            "E": np.random.uniform(10, 1000, n).round(2).astype(str),
            "F": np.random.uniform(5, 500, n).round(2).astype(str),
        })

    def test_returns_none_when_no_split(self):
        df = self._make_df()
        report = _make_region_report(has_split=False)
        result = simulate_sort_corruption(df, report, ["A"], ["D", "E"])
        self.assertIsNone(result)

    def test_returns_result_when_split_exists(self):
        df = self._make_df()
        report = _make_region_report(has_split=True)
        result = simulate_sort_corruption(df, report, ["A"], ["D"])
        self.assertIsNotNone(result)

    def test_corruption_count_within_bounds(self):
        df = self._make_df(100)
        report = _make_region_report(has_split=True)
        result = simulate_sort_corruption(df, report, ["A"], ["D"])
        self.assertGreaterEqual(result.corrupted_rows, 0)
        self.assertLessEqual(result.corrupted_rows, len(df))

    def test_corruption_pct_within_bounds(self):
        df = self._make_df(100)
        report = _make_region_report(has_split=True)
        result = simulate_sort_corruption(df, report, ["A"], ["D"])
        self.assertGreaterEqual(result.corruption_pct, 0.0)
        self.assertLessEqual(result.corruption_pct, 100.0)

    def test_before_sample_has_rows(self):
        df = self._make_df(20)
        report = _make_region_report(has_split=True)
        result = simulate_sort_corruption(df, report, ["A"], ["D"])
        self.assertFalse(result.before_sample.empty)

    def test_after_sample_has_rows(self):
        df = self._make_df(20)
        report = _make_region_report(has_split=True)
        result = simulate_sort_corruption(df, report, ["A"], ["D"])
        self.assertFalse(result.after_sample.empty)

    def test_sort_column_in_result(self):
        df = self._make_df(20)
        report = _make_region_report(has_split=True)
        result = simulate_sort_corruption(df, report, ["A"], ["D"])
        self.assertEqual(result.sort_column, "A")

    def test_risk_level_set(self):
        df = self._make_df(100)
        report = _make_region_report(has_split=True)
        result = simulate_sort_corruption(df, report, ["A"], ["D"])
        self.assertIn(result.risk_level, ["CRITICAL", "HIGH", "MEDIUM", "LOW"])


if __name__ == "__main__":
    unittest.main()
