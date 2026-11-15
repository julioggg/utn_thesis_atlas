"""Synthetic tests for read-only third C intake and AI proposal hard gate."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from audit_uploaded_third_review_proposals import (
    validate_thematic,validate_structural,
    compare_roster,read_workbook_rows
)
from export_third_reviewer_blinded_packets import C_FIELDS,S_FIELDS
from export_blinded_validation_workbooks import build_xlsx


class CProposalIntakeTests(unittest.TestCase):
    def test_ai_disclosed_thematic_is_only_proposal(self):
        row=dict.fromkeys(C_FIELDS,"")
        row.update({
            "study_id":"TH-0002",
            "private_source_handle":"13222",
            "documento_local":"Evidencias/TH-0002.txt",
            "sdg_primary":"ODS 2",
            "sdg_no_match":"no",
            "pdot_primary":"PDOT 3",
            "pdot_no_match":"no",
            "uncertain":"no",
            "brief_evidence":"Resumen: objetivos agrícolas",
            "coder_notes":"Codificación asistida por IA, NO tercera evaluación humana independiente.",
            "reviewer_identity_date":"Asistencia IA · 2026-11-15"
        })
        result=validate_thematic([row])
        self.assertEqual(result["n_cases"],1)
        self.assertEqual(result["self_declared_automated_assistance"],1)
        self.assertEqual(result["explicit_nonhuman_proposal_claim"],1)
        self.assertEqual(result["evidence_based_on_abstract_excerpt"],1)

    def test_structural_candidate_yes_with_corrected_early_boundary_is_warned(self):
        row=dict.fromkeys(S_FIELDS,"")
        row.update({
            "review_id":"SB-0022",
            "private_source_handle":"11291",
            "documento_local":"Evidencias/SB-0022.txt",
            "candidate_position_fraction":"0.905213",
            "heading_line":"BIBLIOGRAFÍA:",
            "independent_heading_is_real_references_start":"yes",
            "independent_corrected_boundary_fraction":"0.625910",
            "independent_tail_contains_scientific_contribution":"yes",
            "independent_trim_from_boundary_safe":"no",
            "independent_notes_and_evidence":"El candidato corresponde a una bibliografía local dentro del anexo.",
            "reviewer_identity_date":"Asistencia IA · 2026-11-15",
        })
        frozen=[{
            "review_id":"SB-0022","private_source_handle":"11291",
            "candidate_position_fraction":"0.9052130"
        }]
        status,warnings=validate_structural([row],frozen)
        self.assertEqual(status["self_declared_automated_assistance"],1)
        self.assertEqual(status["post_heading_scientific_content_yes"],1)
        self.assertEqual(status["trim_safe_yes"],0)
        self.assertIn(
            "heading_yes_but_large_boundary_correction",
            [x["issue"] for x in warnings]
        )
        self.assertIn(
            "heading_yes_but_notes_question_candidate",
            [x["issue"] for x in warnings]
        )
        row["independent_trim_from_boundary_safe"]="yes"
        with self.assertRaisesRegex(ValueError,"unsafe_trim_approval_conflict"):
            validate_structural([row],frozen)

    def test_original_handles_are_immutable(self):
        r={"study_id":"TH-0002","private_source_handle":"13222",
           "documento_local":"Evidencias/TH-0002.txt"}
        frozen=[{"study_id":"TH-0002","private_source_handle":"13222"}]
        compare_roster([r],frozen,"study_id","thematic")
        r["private_source_handle"]="wrong"
        with self.assertRaisesRegex(ValueError,"handles"):
            compare_roster([r],frozen,"study_id","thematic")

    def test_external_workbook_labels_read_without_reformatting(self):
        with tempfile.TemporaryDirectory() as td:
            dst=Path(td)/"C.xlsx"
            rows=[
                ["EVALUADOR C"]+[""]*12,
                ["PROPOSAL"]+[""]*12,
                ["DATA"]+[""]*12,
                ["DATA"]+[""]*12,
                list(C_FIELDS),
                ["TH-0002","13222","Evidencias/TH-0002.txt"]+[""]*10,
            ]
            build_xlsx(dst,[("Evaluación C",rows,[22]*13,"generic",None)])
            records=read_workbook_rows(dst,C_FIELDS)
            self.assertEqual(len(records),1)
            self.assertEqual(records[0]["study_id"],"TH-0002")


if __name__=="__main__":
    unittest.main()
