"""Synthetic tests for strict read-only expert final-cell audit."""
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from audit_expert_consensus_450_workbook import (
    audit, evaluate_final, source_unchanged, workbook_rows
)
from prepare_expert_consensus_450_workbook import (
    FIELDS, EDITABLE, create_workbook
)


class ConsensusAuditTests(unittest.TestCase):
    def setUp(self):
        self.expected=[]
        for i in range(450):
            case=dict.fromkeys(FIELDS,"")
            case.update({
                "study_id":f"TH-{i+1:04d}",
                "private_source_handle":f"source-{i}",
                "review_priority":"P3_AB_UNCONTESTED",
                "A_ODS_primary":"ODS 4",
                "B_ODS_primary":"ODS 4",
                "A_PDOT_primary":"PDOT 2",
                "B_PDOT_primary":"PDOT 2",
                "A_B_ODS_unapproved_candidate":"ODS 4",
                "A_B_PDOT_unapproved_candidate":"PDOT 2",
                "A_evidence":"Thesis methods and findings",
            })
            self.expected.append(case)

    def test_no_auto_acceptance_of_ab_agreement(self):
        states=audit(self.expected,self.expected)
        self.assertEqual(states["by_status"],{"not_started":450})
        self.assertFalse(states[
            "ready_for_separate_provenance_and_source_adjudication_gate"
        ])

    def test_expert_partial_and_final_and_conflict(self):
        row=deepcopy(self.expected[0])
        row["final_sdg_primary"]="ODS 4"
        self.assertEqual(evaluate_final(row)[0],"in_progress")
        row["final_sdg_no_match"]="no"
        row["final_pdot_primary"]="PDOT 2"
        row["final_pdot_no_match"]="no"
        row["final_expert_rationale"]="Section 5 shows educational outcomes"
        row["final_expert_name_and_date"]="Review committee, 2026-11-15"
        self.assertEqual(evaluate_final(row)[0],"complete")
        row["final_pdot_no_match"]="yes"
        self.assertEqual(evaluate_final(row)[0],"invalid")

    def test_immutable_evidence_is_not_alterable(self):
        changed=deepcopy(self.expected)
        changed[0]["A_evidence"]="Unsupported modified rationale"
        with self.assertRaisesRegex(ValueError,"immutable"):
            source_unchanged(changed,self.expected)
        changed=deepcopy(self.expected)
        changed[10]["private_source_handle"]="wrong"
        with self.assertRaisesRegex(ValueError,"immutable"):
            source_unchanged(changed,self.expected)

    def test_created_workbook_headers_read_back_and_sources_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            original=Path(temp)/"consensus.xlsx"
            create_workbook(self.expected,original)
            rows=workbook_rows(original)
            self.assertEqual(len(rows),450)
            self.assertTrue(all(k in rows[0] for k in EDITABLE))
            self.assertTrue(all(rows[0][k]=="" for k in EDITABLE))
            source_unchanged(rows,self.expected)
            self.assertEqual(audit(rows,self.expected)["by_status"],
                             {"not_started":450})


if __name__=="__main__":
    unittest.main()
