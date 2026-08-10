"""
Unit tests for the row signature engine (Feature 7).
"""
import unittest
import hashlib
import pandas as pd
import numpy as np

from modules.signature_engine import (
    build_row_signature,
    add_signatures,
    find_duplicate_signatures,
    signature_change_count,
)


class TestBuildRowSignature(unittest.TestCase):
    def test_consistent_hash(self):
        df = pd.DataFrame({"PolicyNo": ["POL001"], "Premium": ["1000.0"]})
        sig1 = build_row_signature(df, ["PolicyNo"], ["Premium"])
        sig2 = build_row_signature(df, ["PolicyNo"], ["Premium"])
        self.assertEqual(sig1.iloc[0], sig2.iloc[0])

    def test_sha256_format(self):
        df = pd.DataFrame({"PolicyNo": ["POL001"], "Premium": ["1000.0"]})
        sig = build_row_signature(df, ["PolicyNo"], ["Premium"])
        # SHA-256 hex digest is 64 characters
        self.assertEqual(len(sig.iloc[0]), 64)

    def test_different_values_different_hash(self):
        df = pd.DataFrame({
            "PolicyNo": ["POL001", "POL002"],
            "Premium": ["1000.0", "2000.0"],
        })
        sigs = build_row_signature(df, ["PolicyNo"], ["Premium"])
        self.assertNotEqual(sigs.iloc[0], sigs.iloc[1])

    def test_null_normalisation(self):
        df = pd.DataFrame({"PolicyNo": [None], "Premium": ["1000.0"]})
        sig = build_row_signature(df, ["PolicyNo"], ["Premium"])
        # Should produce a hash, not fail
        self.assertEqual(len(sig.iloc[0]), 64)

        # Null values should hash consistently
        sig2 = build_row_signature(df, ["PolicyNo"], ["Premium"])
        self.assertEqual(sig.iloc[0], sig2.iloc[0])

    def test_empty_field_list(self):
        df = pd.DataFrame({"PolicyNo": ["POL001"]})
        sig = build_row_signature(df, [], [])
        self.assertEqual(sig.iloc[0], "")

    def test_manual_hash_verification(self):
        """Verify the hash matches a manually computed SHA-256."""
        df = pd.DataFrame({"PolicyNo": ["POL001"], "Premium": ["1000"]})
        raw = "POL001|1000".encode("utf-8")
        expected = hashlib.sha256(raw).hexdigest()
        sig = build_row_signature(df, ["PolicyNo"], ["Premium"])
        self.assertEqual(sig.iloc[0], expected)


class TestAddSignatures(unittest.TestCase):
    def test_adds_signature_column(self):
        df = pd.DataFrame({"PolicyNo": ["POL001"], "Premium": ["1000"]})
        result = add_signatures(df, ["PolicyNo"], ["Premium"])
        self.assertIn("__row_signature__", result.columns)

    def test_does_not_mutate_original(self):
        df = pd.DataFrame({"PolicyNo": ["POL001"]})
        _ = add_signatures(df, ["PolicyNo"], [])
        self.assertNotIn("__row_signature__", df.columns)


class TestFindDuplicateSignatures(unittest.TestCase):
    def test_finds_duplicates(self):
        df = pd.DataFrame({
            "PolicyNo": ["POL001", "POL001", "POL002"],
            "Premium": ["1000", "1000", "2000"],
        })
        df_sig = add_signatures(df, ["PolicyNo"], ["Premium"])
        dups = find_duplicate_signatures(df_sig)
        self.assertEqual(len(dups), 2)

    def test_no_duplicates(self):
        df = pd.DataFrame({
            "PolicyNo": ["POL001", "POL002"],
            "Premium": ["1000", "2000"],
        })
        df_sig = add_signatures(df, ["PolicyNo"], ["Premium"])
        dups = find_duplicate_signatures(df_sig)
        self.assertTrue(dups.empty)


class TestSignatureChangeCount(unittest.TestCase):
    def test_no_change(self):
        sigs = pd.Series(["abc", "def", "ghi"])
        self.assertEqual(signature_change_count(sigs, sigs), 0)

    def test_all_changed(self):
        orig = pd.Series(["abc", "def", "ghi"])
        after = pd.Series(["xyz", "xyz", "xyz"])
        self.assertEqual(signature_change_count(orig, after), 3)

    def test_partial_change(self):
        orig = pd.Series(["abc", "def", "ghi"])
        after = pd.Series(["abc", "xyz", "ghi"])
        self.assertEqual(signature_change_count(orig, after), 1)


if __name__ == "__main__":
    unittest.main()
