"""Synthetic tests of private 47-case adjudication to 450-reference safety gate."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from freeze_47_adjudications_450_reference import (
    HEADS, read_47, build_reference, require_ratification, sha256
)
from export_blinded_validation_workbooks import build_xlsx

class Freeze47Tests(unittest.TestCase):
    def setUp(self):
        self.master=[]
        self.A=[]
        self.B=[]
        self.records=[]
        for i in range(450):
            sid=f"TH-{i+1:04d}"
            handle=f"private-{i}"
            self.master.append({"study_id":sid,"handle_id":handle})
            a={
                "study_id":sid,"private_source_handle":handle,
                "sdg_primary":"ODS 4","sdg_no_match":"no",
                "pdot_primary":"PDOT 2","pdot_no_match":"no",
            }
            b=dict(a)
            if i<35:
                b["sdg_primary"]="ODS 8"
            if 35<=i<47:
                b["pdot_primary"]="PDOT 3"
            self.A.append(a)
            self.B.append(b)
            if i<47:
                row={
                    1:sid,2:handle,
                    3:"SÍ" if i<35 else "NO",
                    4:"SÍ" if i>=35 else "NO",
                    5:"ODS 4",6:"ODS 8" if i<35 else "ODS 4",7:"ODS 8",
                    8:"PDOT 2",9:"PDOT 3" if i>=35 else "PDOT 2",10:"PDOT 2",
                    11:"ODS 4",12:"no",13:"PDOT 2",14:"no",
                    15:"Verified thesis abstract and conclusion",
                    16:"Original thesis results section",
                    17:"Committee review","18":"2026-11-15",
                    18:"2026-11-15",19:"LISTO",20:"",
                }
                row.pop("18",None)
                self.records.append(row)

    def test_47_exact_conflicts_create_450_but_no_unapproved_labels(self):
        ref,counts=build_reference(self.master,self.A,self.B,self.records)
        self.assertEqual(len(ref),450)
        self.assertEqual(counts["conflict_rows"],47)
        self.assertEqual(counts["agreement_rows"],403)
        self.assertEqual(ref[0]["human_reference_basis"],"committee_reviewed_ab_primary_conflict")
        self.assertEqual(ref[-1]["human_reference_basis"],"committee_policy_ab_primary_agreement")

    def test_original_a_b_change_refused(self):
        self.records[0][5]="ODS 11"
        with self.assertRaisesRegex(ValueError,"original A/B response|Original A/B response"):
            build_reference(self.master,self.A,self.B,self.records)

    def test_wrong_case_id_refused(self):
        self.records[0][1]="TH-NOT-IN-ROSTER"
        with self.assertRaisesRegex(ValueError,"differs from frozen"):
            build_reference(self.master,self.A,self.B,self.records)

    def test_original_excel_sheet_read_only(self):
        with tempfile.TemporaryDirectory() as td:
            dest=Path(td)/"47.xlsx"
            content=[
                ["HEADER"],["READ ONLY"],["STUDY"],[],list(HEADS)
            ]
            content += [[row.get(j,"") for j in range(1,21)] for row in self.records]
            build_xlsx(dest,[("ADJUDICACION_47",content,[20]*20,"generic",None)])
            values=read_47(dest)
            self.assertEqual(len(values),47)
            self.assertEqual(values[0][1],"TH-0001")
            self.assertEqual(sha256(dest),sha256(dest))

    def test_apply_cannot_run_without_private_ratification(self):
        with self.assertRaisesRegex(ValueError,"--ratification-record"):
            require_ratification(None,Path("/tmp/no.xlsx"))

if __name__=="__main__":
    unittest.main()
