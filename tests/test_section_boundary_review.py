"""Synthetic tests: the section-boundary review never publishes source excerpts."""
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from prepare_section_boundary_review import (
    STRATA, candidate_context, choose_rows, prepare, safe_csv_value, stratum_of
)
from audit_thesis_structure import analyze_text


def text_by_group(category):
    body = ("Se estudió una investigación técnica en el sistema.\n" * 50)
    if category == "late_reference_with_appendix":
        return (body + "REFERENCIAS BIBLIOGRÁFICAS\n" + "Libro citado.\n" * 12
                + "ANEXOS\n" + "Mediciones de laboratorio.\n" * 15)
    if category == "late_reference_without_appendix":
        return body + "REFERENCIAS\n" + ("Libro de referencia.\n" * 35)
    if category == "early_reference_only":
        return "REFERENCIAS\n" + body
    return body


class StructureReviewTests(unittest.TestCase):
    def test_four_groups(self):
        for category in STRATA:
            text = text_by_group(category)
            result = analyze_text(text)
            self.assertEqual(stratum_of(result), category)
            snippet = candidate_context(text, .55)
            self.assertTrue(snippet["context_after"])
            if category == "no_reference_heading":
                self.assertEqual(snippet["heading_line"], "")
            else:
                self.assertIn("REFERENCIAS", snippet["heading_line"])

    def test_quotas_reproducible_disjoint(self):
        pools = {label: list(range(i * 30, (i + 1) * 30))
                 for i, label in enumerate(STRATA)}
        a = choose_rows(pools, 5, seed=987)
        b = choose_rows(pools, 5, seed=987)
        self.assertEqual(a, b)
        ids = [i for group in a.values() for i in group]
        self.assertEqual(len(ids), 20)
        self.assertEqual(len(set(ids)), 20)

    def test_csv_formula_safe(self):
        self.assertEqual(safe_csv_value("=EXCEL_FORMULA"), "'=EXCEL_FORMULA")
        self.assertEqual(safe_csv_value("-123"), "'-123")
        self.assertEqual(safe_csv_value("Notes"), "Notes")

    def test_restricted_sheet_excludes_existing_validation_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "revision"
            original = Path(tmp) / "original"
            src = original / "data/processed/04_clean_corpus.parquet"
            src.parent.mkdir(parents=True)
            records = []
            for category in STRATA:
                for i in range(7):
                    records.append({
                        "handle_id": f"PRIVATE-{category}-{i}",
                        "full_text": text_by_group(category),
                    })
            pd.DataFrame(records).to_parquet(src, index=False)
            master = workspace / "data/revision_private/validation/sample_master_private.csv"
            master.parent.mkdir(parents=True)
            pd.DataFrame({"handle_id": ["PRIVATE-late_reference_with_appendix-0"]}).to_csv(master, index=False)
            private = workspace / "data/revision_private/section_boundary_review_v1"
            report = workspace / "docs/audits/section_boundary_review_design.json"
            result = prepare(original, workspace, 2, 42, .55, private, report)
            self.assertEqual(result["private_review_records_total"], 8)
            self.assertEqual(result["excluded_previously_selected_450_validation_rows"], 1)
            self.assertEqual(sum(result["strata_population_counts"].values()), 28)
            with (private / "section_boundary_review_private.csv").open(encoding="utf-8") as f:
                private_rows = list(csv.DictReader(f))
            self.assertEqual(len(private_rows), 8)
            self.assertNotIn("PRIVATE-late_reference_with_appendix-0",
                             [r["private_source_handle"] for r in private_rows])
            self.assertNotIn("PRIVATE-", report.read_text(encoding="utf-8"))
            self.assertNotIn("Se estudió", report.read_text(encoding="utf-8"))
            self.assertTrue(all(
                r["human_heading_is_real_references_start"] == ""
                for r in private_rows
            ))
            with self.assertRaises(FileExistsError):
                prepare(original, workspace, 2, 42, .55, private, report)


if __name__ == "__main__":
    unittest.main()
