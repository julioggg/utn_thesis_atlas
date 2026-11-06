"""Synthetic tests of blind-sheet integrity and progress checks."""
import tempfile
import unittest
from pathlib import Path
import sys
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_annotation_progress import inspect_files, evaluate_domain


class PrivateProgressTests(unittest.TestCase):
    def make_files(self, folder):
        pd.DataFrame({
            "study_id": ["TH-0001", "TH-0002"],
            "handle_id": ["https://example.edu/item1", "https://example.edu/item2"],
        }).to_csv(folder / "sample_master_private.csv", index=False)
        for letter in ("A", "B"):
            pd.DataFrame({
                "study_id": ["TH-0001", "TH-0002"],
                "private_source_handle": ["https://example.edu/item1", "https://example.edu/item2"],
                "sdg_primary": ["ODS 4", ""],
                "sdg_secondary": ["", ""],
                "sdg_no_match": ["no", ""],
                "pdot_primary": ["PDOT 2", ""],
                "pdot_secondary": ["", ""],
                "pdot_no_match": ["no", ""],
                "uncertain": ["no", ""],
                "brief_evidence": ["Objectives section", ""],
                "coder_notes": ["", ""],
            }).to_csv(folder / f"coder_{letter}_private.csv", index=False)

    def test_progress_without_identifier_leaks(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            self.make_files(folder)
            report = inspect_files(folder)
            self.assertEqual(report["both_coders_complete"], 1)
            self.assertEqual(report["coder_progress"]["A"]["not_started"], 1)
            self.assertTrue(report["coder_sheet_integrity"] == "passed")
            self.assertNotIn("example.edu", str(report))
            self.assertNotIn("TH-0001", str(report))
            self.assertFalse(report["all_annotations_finished"])

    def test_mismatched_handle_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            self.make_files(folder)
            file = folder / "coder_B_private.csv"
            frame = pd.read_csv(file, dtype=str, keep_default_na=False)
            frame.loc[0, "private_source_handle"] = "UNRELATED"
            frame.to_csv(file, index=False)
            with self.assertRaises(ValueError):
                inspect_files(folder)

    def test_codes_and_no_match_conflict(self):
        ok = {
            "sdg_primary": "ODS 12", "sdg_secondary": "ODS 7", "sdg_no_match": "no",
            "pdot_primary": "", "pdot_secondary": "", "pdot_no_match": "yes",
        }
        self.assertEqual(evaluate_domain(ok, "sdg", {f"ODS {i}" for i in range(1,18)})[0], "complete")
        self.assertEqual(evaluate_domain(ok, "pdot", {f"PDOT {i}" for i in range(1,7)})[0], "complete")
        ok["sdg_no_match"] = "yes"
        self.assertEqual(evaluate_domain(ok, "sdg", {f"ODS {i}" for i in range(1,18)})[0], "invalid")


if __name__ == "__main__":
    unittest.main()
