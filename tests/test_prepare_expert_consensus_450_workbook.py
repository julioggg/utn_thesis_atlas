"""Synthetic test: 450-case consensus worklist never invents expert reference."""
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from prepare_expert_consensus_450_workbook import (
    generate,create_workbook,EDITABLE,FIELDS
)


class ExpertConsensusWorkbookTests(unittest.TestCase):
    def inputs(self):
        master=[]
        A=[]
        B=[]
        C=[]
        queue=[]
        for i in range(450):
            sid=f"TH-{i+1:04d}"
            h=f"private-doc-{i}"
            master.append({
                "study_id":sid,"handle_id":h,
                "selection_stratum":"population_random" if i<120 else "targeted_enrichment",
            })
            row={
                "study_id":sid,"private_source_handle":h,
                "sdg_primary":"ODS 4","sdg_secondary":"","sdg_no_match":"no",
                "pdot_primary":"PDOT 2","pdot_secondary":"","pdot_no_match":"no",
                "uncertain":"no","brief_evidence":"Original thesis finding",
                "coder_notes":"",
            }
            A.append(dict(row))
            B.append(dict(row))
            if i<201:
                C.append(dict(row))
                queue.append({
                    "study_id":sid,"private_source_handle":h,
                    "reasons_for_review":"human_uncertainty",
                })
        # Main label disagreement -> highest priority.
        B[0]["sdg_primary"]="ODS 12"
        # C challenges A/B agreement, not automated majority.
        C[1]["pdot_primary"]="PDOT 4"
        return master,A,B,C,queue

    def test_original_450_case_worklist_and_blank_expert_fields(self):
        rows=generate(*self.inputs())
        self.assertEqual(len(rows),450)
        by_id={r["study_id"]:r for r in rows}
        self.assertEqual(len(by_id),450)
        self.assertEqual(by_id["TH-0001"]["review_priority"],"P0_AB_PRIMARY_CONFLICT")
        self.assertEqual(by_id["TH-0001"]["A_B_ODS_unapproved_candidate"],"")
        self.assertEqual(by_id["TH-0002"]["review_priority"],"P1_C_CHALLENGES_AB")
        self.assertEqual(by_id["TH-0002"]["A_B_PDOT_unapproved_candidate"],"PDOT 2")
        self.assertEqual(by_id["TH-0003"]["review_priority"],"P2_SECONDARY_OR_UNCERTAINTY")
        self.assertEqual(by_id["TH-0450"]["review_priority"],"P3_AB_UNCONTESTED")
        for row in rows:
            self.assertTrue(all(row[field]=="" for field in EDITABLE))

    def test_native_xlsx_expert_only_fields_are_yellow(self):
        rows=generate(*self.inputs())
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"private.xlsx"
            counts=create_workbook(rows,path)
            self.assertEqual(sum(counts.values()),450)
            with ZipFile(path) as z:
                self.assertIsNone(z.testzip())
                xml=z.read("xl/worksheets/sheet2.xml").decode()
                self.assertIn("final_sdg_primary",xml)
                self.assertIn("dataValidations",xml)
                self.assertIn('r="S6" s="3"',xml)
                self.assertIn('r="C6" s="2"',xml)
                self.assertNotIn("<f>",xml)
                self.assertNotIn("selection_stratum",xml)

    def test_invalid_roster_never_exported(self):
        m,a,b,c,q=self.inputs()
        c[0]["private_source_handle"]="invalid"
        with self.assertRaisesRegex(ValueError,"source handle"):
            generate(m,a,b,c,q)


if __name__=="__main__":
    unittest.main()
