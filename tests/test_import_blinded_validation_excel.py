"""Prove Excel submission import validates frozen blind ID and coder identity."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from export_blinded_validation_workbooks import build_xlsx, annotation_sheets
from import_blinded_validation_excel import (
    extract_annotations, compare_input
)


class BlindedExcelImportTests(unittest.TestCase):
    def create_book(self,root,letter="A"):
        cases=[]
        texts={}
        for i in range(1,451):
            study=f"TH-{i:04d}"
            handle=f"https://institutional.example/record/{i}"
            cases.append({
                "study_id":study,"private_source_handle":handle,
                "sdg_primary":"","sdg_secondary":"","sdg_no_match":"",
                "pdot_primary":"","pdot_secondary":"","pdot_no_match":"",
                "uncertain":"","brief_evidence":"","coder_notes":"",
            })
            texts[handle]={
                "title":"Synthetic example","abstract":"",
                "preview":"A sample synthetic corpus","tail":"End of example",
                "characters":44,
            }
        file=root/f"Coder_{letter}.xlsx"
        build_xlsx(file,annotation_sheets(cases,texts,letter))
        return file,cases

    def test_450_unannotated_rows_and_identity(self):
        with tempfile.TemporaryDirectory() as d:
            f,cases=self.create_book(Path(d),"A")
            parsed=extract_annotations(f,"A")
            self.assertEqual(len(parsed),450)
            self.assertEqual(parsed[449]["study_id"],"TH-0450")
            self.assertEqual(parsed[449]["sdg_primary"],"")
            modifications,answered,_,_=compare_input(cases,parsed)
            self.assertEqual(modifications,0)
            self.assertEqual(answered,0)
            with self.assertRaisesRegex(ValueError,"identify"):
                extract_annotations(f,"B")

    def test_cannot_import_changed_source_handle(self):
        with tempfile.TemporaryDirectory() as d:
            f,cases=self.create_book(Path(d))
            parsed=extract_annotations(f,"A")
            parsed[10]["private_source_handle"]="tampered"
            with self.assertRaisesRegex(ValueError,"handles changed"):
                compare_input(cases,parsed)

    def test_cannot_override_existing_answers(self):
        with tempfile.TemporaryDirectory() as d:
            f,cases=self.create_book(Path(d))
            cases[0]["sdg_primary"]="ODS 4"
            parsed=extract_annotations(f,"A")
            with self.assertRaisesRegex(ValueError,"already recorded"):
                compare_input(cases,parsed)


if __name__=="__main__":
    unittest.main()
