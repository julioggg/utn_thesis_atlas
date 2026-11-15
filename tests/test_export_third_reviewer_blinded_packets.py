"""Synthetic checks: third reviewer packets stay blind and keep original cases."""
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from export_blinded_validation_workbooks import build_xlsx
from export_third_reviewer_blinded_packets import (
    thematic_sheets,structural_sheets,zip_packet,C_FIELDS,S_FIELDS
)


class ThirdReviewPacketsTests(unittest.TestCase):
    def setUp(self):
        self.dir=tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root=Path(self.dir.name)
        self.h="http://private-institution.edu/example"
        self.text=self.root/"source.txt"
        self.text.write_text("Synthetic original thesis text",encoding="utf-8")
        self.t={
            self.h:{
                "file":self.text,"title":"Source thesis",
                "preview":"Research abstract","tail":"Appendix findings",
                "characters":len("Synthetic original thesis text")
            }
        }

    def test_thematic_omits_a_b_e5_and_disagreement_reason(self):
        src=[{
            "study_id":"TH-0022","private_source_handle":self.h,
            "reasons_for_review":"ods_disagreement",
            "coder_A_sdg_primary":"ODS 4",
            "coder_B_sdg_primary":"ODS 12",
            "coder_A_evidence":"Private A notes",
            "coder_B_evidence":"Private B notes",
        }]
        sheets=thematic_sheets(src,self.t)
        self.assertEqual(len(sheets[1][1]),6)
        self.assertEqual(tuple(sheets[1][1][4]),C_FIELDS)
        path=self.root/"C.xlsx"
        build_xlsx(path,sheets)
        with ZipFile(path) as archive:
            xml=archive.read("xl/worksheets/sheet2.xml").decode("utf-8")
            self.assertIn("TH-0022",xml)
            self.assertNotIn("Private A notes",xml)
            self.assertNotIn("Private B notes",xml)
            self.assertNotIn("ods_disagreement",xml)
            self.assertNotIn("coder_A_sdg_primary",xml)
            self.assertNotIn("ODS 12",xml)
            self.assertIn("dataValidations",xml)

    def test_structural_omits_prior_human_decisions_and_keeps_candidate(self):
        src=[{
            "review_id":"SB-0039","private_source_handle":self.h,
            "candidate_position_fraction":"0.989266",
            "heading_line":"Referencias",
            "context_before":"Research",
            "context_after":"Appendix",
            "trailing_excerpt":"Literature",
            "human_heading_is_real_references_start":"no",
            "human_corrected_boundary_fraction":"0.534785",
            "human_notes":"Prior evaluator found a nested citation block."
        }]
        sheets=structural_sheets(src,self.t)
        self.assertEqual(tuple(sheets[1][1][4]),S_FIELDS)
        file=self.root/"boundary.xlsx"
        build_xlsx(file,sheets)
        with ZipFile(file) as z:
            xml=z.read("xl/worksheets/sheet2.xml").decode("utf-8")
            self.assertIn("SB-0039",xml)
            self.assertIn("0.989266",xml)
            self.assertNotIn("0.534785",xml)
            self.assertNotIn("nested citation",xml)
        package=self.root/"private.zip"
        zip_packet(package,"Review.xlsx",sheets,src,self.t,"review_id")
        with ZipFile(package) as z:
            self.assertEqual(set(z.namelist()),{
                "Review.xlsx","Evidencias/SB-0039.txt","LEEME_PRIVACIDAD.txt"
            })
            self.assertEqual(
                z.read("Evidencias/SB-0039.txt").decode("utf-8"),
                "Synthetic original thesis text"
            )

if __name__=="__main__":
    unittest.main()
