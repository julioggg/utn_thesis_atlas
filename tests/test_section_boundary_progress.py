"""Synthetic-only testing of private section-boundary audit and exclusion rules."""
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_section_boundary_review import assess_row, summarize
from prepare_section_boundary_review import STRATA


class BoundaryAuditTests(unittest.TestCase):
    def test_row_consistency(self):
        row = {
            "candidate_position_fraction": ".9",
            "human_heading_is_real_references_start": "yes",
            "human_corrected_boundary_fraction": "",
            "human_tail_contains_scientific_contribution": "no",
            "human_trim_from_boundary_safe": "yes",
            "human_notes": "Confirmed by a private reviewer",
        }
        self.assertEqual(assess_row(row)[0], "reviewed")
        row["human_tail_contains_scientific_contribution"] = "yes"
        self.assertEqual(assess_row(row)[0], "invalid")
        row["human_tail_contains_scientific_contribution"] = "uncertain"
        row["human_trim_from_boundary_safe"] = "no"
        self.assertEqual(assess_row(row)[0], "needs_adjudication")

    def test_rejected_heading_with_better_boundary_requires_adjudication(self):
        row = {
            "candidate_position_fraction": "0.905213",
            "human_heading_is_real_references_start": "no",
            "human_corrected_boundary_fraction": "0.625923",
            "human_tail_contains_scientific_contribution": "yes",
            "human_trim_from_boundary_safe": "no",
            "human_notes": "Two reference sections separated by scientific content.",
        }
        state, reasons = assess_row(row)
        self.assertEqual(state, "needs_adjudication")
        self.assertEqual(reasons, ["corrected_candidate_requires_adjudication"])
        # A logically unsafe assertion remains a hard invalidity, even if
        # there is ALSO a legitimate correction that needs adjudication.
        row["human_trim_from_boundary_safe"] = "yes"
        state, reasons = assess_row(row)
        self.assertEqual(state, "invalid")
        self.assertIn("unsafe_trim_approval_conflict", reasons)

    def test_unedited_and_partial(self):
        row = {
            "candidate_position_fraction": "",
            "human_heading_is_real_references_start": "",
            "human_corrected_boundary_fraction": "",
            "human_tail_contains_scientific_contribution": "",
            "human_trim_from_boundary_safe": "",
        }
        self.assertEqual(assess_row(row)[0], "not_started")
        row["human_heading_is_real_references_start"] = "no"
        self.assertEqual(assess_row(row)[0], "in_progress")
        row["human_heading_is_real_references_start"] = "yes"
        self.assertEqual(assess_row(row)[0], "invalid")

    def build(self, root):
        csv_path = root / "section_boundary_review_private.csv"
        master = root / "sample_master_private.csv"
        with master.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["handle_id"])
            writer.writeheader()
            writer.writerow({"handle_id": "KEEP-OUT-450"})
        keys = [
            "review_id", "private_source_handle", "sampling_stratum",
            "candidate_position_fraction", "human_heading_is_real_references_start",
            "human_corrected_boundary_fraction",
            "human_tail_contains_scientific_contribution",
            "human_trim_from_boundary_safe", "human_notes",
        ]
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            i = 0
            for group in STRATA:
                for j in range(20):
                    i += 1
                    candidate = ".83" if group.startswith("late_reference") else ""
                    row = {
                        "review_id": f"SB-{i:04d}",
                        "private_source_handle": f"PRIVATE-SOURCE-HANDLE-{i}",
                        "sampling_stratum": group,
                        "candidate_position_fraction": candidate,
                        "human_heading_is_real_references_start": "",
                        "human_corrected_boundary_fraction": "",
                        "human_tail_contains_scientific_contribution": "",
                        "human_trim_from_boundary_safe": "",
                        "human_notes": "",
                    }
                    if i == 1:
                        row["human_heading_is_real_references_start"] = "yes"
                        row["human_tail_contains_scientific_contribution"] = "no"
                        row["human_trim_from_boundary_safe"] = "yes"
                    writer.writerow(row)
        return csv_path, master

    def test_80_rows_and_no_identifier_leaks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            private, master = self.build(path)
            report = summarize(private, master)
            self.assertEqual(report["sample_rows"], 80)
            self.assertEqual(report["total_reviewed"], 1)
            self.assertEqual(report["total_not_started"], 79)
            self.assertEqual(report["reviewed_answer_counts"]
                             ["human_trim_from_boundary_safe"]["yes"], 1)
            self.assertTrue(report["excluded_450_thematic_validation_overlap"])
            public = json.dumps(report)
            self.assertNotIn("PRIVATE-SOURCE-HANDLE", public)
            self.assertNotIn("KEEP-OUT-450", public)

    def test_sample_overlap_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            private, master = self.build(path)
            lines = private.read_text(encoding="utf-8").splitlines()
            lines[1] = lines[1].replace("PRIVATE-SOURCE-HANDLE-1", "KEEP-OUT-450")
            private.write_text("\n".join(lines) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                summarize(private, master)


if __name__ == "__main__":
    unittest.main()
