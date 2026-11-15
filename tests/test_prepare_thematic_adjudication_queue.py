"""Synthetic-only thematic disagreement roster tests, preserving A and B."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from prepare_thematic_adjudication_queue import (
    ADJUDICATION_FIELDS, select_cases
)


class ThematicAdjudicationQueueTests(unittest.TestCase):
    def setUp(self):
        self.master=[]
        self.a=[]
        for i in range(1,451):
            sid=f"TH-{i:04d}"
            handle=f"opaque-institutional-handle-{i}"
            self.master.append({"study_id":sid,"handle_id":handle})
            self.a.append({
                "study_id":sid,
                "private_source_handle":handle,
                "sdg_primary":"ODS 4","sdg_secondary":"",
                "sdg_no_match":"no",
                "pdot_primary":"PDOT 2","pdot_secondary":"",
                "pdot_no_match":"no","uncertain":"no",
                "brief_evidence":"Documented learning outcomes",
                "coder_notes":"",
            })
        self.b=copy.deepcopy(self.a)

    def test_disagreement_and_uncertainty_queued_without_fabricating_truth(self):
        self.b[21]["sdg_primary"]="ODS 3"
        self.b[38]["pdot_primary"]="PDOT 4"
        self.a[48]["uncertain"]="yes"
        old_a=copy.deepcopy(self.a)
        old_b=copy.deepcopy(self.b)
        pending,reasons=select_cases(self.master,self.a,self.b)
        self.assertEqual(len(pending),3)
        self.assertEqual([x["study_id"] for x in pending],
                         ["TH-0022","TH-0039","TH-0049"])
        self.assertEqual(dict(reasons),{
            "ods_disagreement":1,
            "pdot_disagreement":1,
            "human_uncertainty":1,
        })
        self.assertEqual(pending[0]["coder_B_sdg_primary"],"ODS 3")
        for row in pending:
            self.assertTrue(all(row[key]=="" for key in ADJUDICATION_FIELDS))
        self.assertEqual(self.a,old_a)
        self.assertEqual(self.b,old_b)

    def test_frozen_handle_mismatch_refused(self):
        self.b[0]["private_source_handle"]="wrong-handle"
        with self.assertRaisesRegex(ValueError,"Wrong B source handle"):
            select_cases(self.master,self.a,self.b)

    def test_no_disagreements_is_not_ground_truth(self):
        result,reasons=select_cases(self.master,self.a,self.b)
        self.assertEqual(result,[])
        self.assertEqual(dict(reasons),{})


if __name__=="__main__":
    unittest.main()
