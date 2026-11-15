"""Synthetic-only private structural review adjudication roster checks."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from prepare_section_boundary_adjudication import make_adjudication_rows

class BoundaryAdjudicationTests(unittest.TestCase):
    def test_substantive_correction_not_invalid_and_no_premature_decision(self):
        rows=[]
        for i in range(1,81):
            row={
                "review_id":f"SB-{i:04d}",
                "private_source_handle":f"private-source-{i}",
                "sampling_stratum":"early_reference_only",
                "candidate_position_fraction":"0.90",
                "human_corrected_boundary_fraction":"",
                "human_heading_is_real_references_start":"yes",
                "human_tail_contains_scientific_contribution":"no",
                "human_trim_from_boundary_safe":"yes",
                "heading_line":"Referencias",
                "context_before":"End of results",
                "context_after":"Bibliography",
                "trailing_excerpt":"References",
                "human_notes":"Checked thesis",
            }
            if i in (22,39):
                row.update({
                    "human_heading_is_real_references_start":"no",
                    "human_corrected_boundary_fraction":"0.63",
                    "human_tail_contains_scientific_contribution":"yes",
                    "human_trim_from_boundary_safe":"no",
                    "human_notes":"A later bibliography is not the first; verify whole source.",
                })
            rows.append(row)
        result,counts=make_adjudication_rows(rows)
        self.assertEqual(len(result),2)
        self.assertEqual([x["review_id"] for x in result],["SB-0022","SB-0039"])
        self.assertEqual(counts["needs_adjudication"],2)
        self.assertEqual(counts["invalid"],0)
        self.assertEqual(counts["reviewed"],78)
        self.assertTrue(all(
            x["adjudicator_reasoning_and_text_evidence"]=="" for x in result
        ))
        self.assertTrue(all(
            x["audit_reason_codes"]=="corrected_candidate_requires_adjudication"
            for x in result
        ))
        self.assertEqual(rows[21]["human_corrected_boundary_fraction"],"0.63")

    def test_duplicate_ids_refused(self):
        with self.assertRaisesRegex(ValueError,"80 unique"):
            make_adjudication_rows([{"review_id":"SB-1"}]*80)

if __name__=="__main__":
    unittest.main()
