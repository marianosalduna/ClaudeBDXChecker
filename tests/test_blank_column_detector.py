"""
Unit tests for blank column detection (Feature 3 & 4).
"""
import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np

from modules.blank_column_detector import (
    detect_blank_columns,
    _df_column_liveness,
    _build_regions,
    BlankColumnFinding,
    DataRegionReport,
)
from modules.file_handler import get_column_letter


class TestColumnLetter(unittest.TestCase):
    def test_single_letters(self):
        self.assertEqual(get_column_letter(0), "A")
        self.assertEqual(get_column_letter(25), "Z")

    def test_double_letters(self):
        self.assertEqual(get_column_letter(26), "AA")
        self.assertEqual(get_column_letter(51), "AZ")
        self.assertEqual(get_column_letter(52), "BA")


class TestDfColumnLiveness(unittest.TestCase):
    def test_all_populated(self):
        df = pd.DataFrame({"A": [1, 2], "B": ["x", "y"]})
        result = _df_column_liveness(df)
        self.assertEqual(result, [True, True])

    def test_all_blank(self):
        df = pd.DataFrame({"A": [None, None], "B": [np.nan, np.nan]})
        result = _df_column_liveness(df)
        self.assertEqual(result, [False, False])

    def test_mixed(self):
        df = pd.DataFrame({"A": [1, 2], "B": [None, None], "C": ["x", "y"]})
        result = _df_column_liveness(df)
        self.assertEqual(result, [True, False, True])

    def test_whitespace_only(self):
        df = pd.DataFrame({"A": ["  ", "  "]})
        result = _df_column_liveness(df)
        self.assertEqual(result, [False])


class TestBuildRegions(unittest.TestCase):
    def test_no_split(self):
        liveness = [True, True, True, True]
        regions = _build_regions(liveness, 0, 3)
        self.assertEqual(len(regions), 1)
        self.assertEqual(regions[0]["start"], "A")
        self.assertEqual(regions[0]["end"], "D")

    def test_single_split(self):
        # A=pop, B=blank, C=pop
        liveness = [True, False, True]
        regions = _build_regions(liveness, 0, 2)
        self.assertEqual(len(regions), 2)
        self.assertEqual(regions[0]["start"], "A")
        self.assertEqual(regions[1]["start"], "C")

    def test_double_split(self):
        # A=pop, B=blank, C=pop, D=blank, E=pop
        liveness = [True, False, True, False, True]
        regions = _build_regions(liveness, 0, 4)
        self.assertEqual(len(regions), 3)

    def test_no_populated(self):
        liveness = [False, False]
        regions = _build_regions(liveness, None, None)
        self.assertEqual(regions, [])


class TestDetectBlankColumns(unittest.TestCase):
    def _make_mock_wb(self, max_row, max_col, cell_values):
        """Build a minimal openpyxl-like mock."""
        ws = MagicMock()
        ws.max_row = max_row
        ws.max_column = max_col
        ws.sheet_state = "visible"
        ws.tables = {}

        def cell(row, column):
            c = MagicMock()
            c.value = cell_values.get((row, column))
            return c

        ws.cell.side_effect = cell

        wb = MagicMock()
        wb.__getitem__ = MagicMock(return_value=ws)
        return wb

    def test_no_blank_columns(self):
        cell_values = {
            (1, 1): "PolicyNo", (1, 2): "Premium",
            (2, 1): "POL001",   (2, 2): 1000.0,
        }
        wb = self._make_mock_wb(2, 2, cell_values)
        df = pd.DataFrame({"PolicyNo": ["POL001"], "Premium": [1000.0]})

        findings, report = detect_blank_columns(wb, "Sheet1", df)
        self.assertEqual(len(findings), 0)
        self.assertEqual(report.internal_blank_count, 0)

    def test_internal_blank_column(self):
        # Column B is blank, A and C are populated
        cell_values = {
            (1, 1): "PolicyNo", (1, 2): None, (1, 3): "Premium",
            (2, 1): "POL001",   (2, 2): None, (2, 3): 1000.0,
        }
        wb = self._make_mock_wb(2, 3, cell_values)
        df = pd.DataFrame({"PolicyNo": ["POL001"], "": [None], "Premium": [1000.0]})

        findings, report = detect_blank_columns(wb, "Sheet1", df)
        self.assertGreaterEqual(report.internal_blank_count, 1)

    def test_risk_level_critical(self):
        cell_values = {
            (1, 1): "A", (1, 2): None, (1, 3): "C",
            (2, 1): "x", (2, 2): None, (2, 3): "z",
        }
        wb = self._make_mock_wb(2, 3, cell_values)
        df = pd.DataFrame({"A": ["x"], "": [None], "C": ["z"]})
        findings, report = detect_blank_columns(wb, "Sheet1", df)
        for f in findings:
            self.assertEqual(f.risk_level, "CRITICAL")


if __name__ == "__main__":
    unittest.main()
