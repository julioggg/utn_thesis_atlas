"""Synthetic validation of population split, C selection and no automatic consensus."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from reviewer_three_coder_comparison import comparison

class ThreeCoderComparisonTests(unittest.TestCase):
    def build(self):
        master=[]
        A=[]
        B=[]
        C=[]
        queue=[]
        for i in range(450):
            sid=f"TH-{i+1:04d}"
            h=f"private-source-{i+1}"
            master.append({
                "study_id":sid,"handle_id":h,
                "selection_stratum":"population_random" if i<120 else "targeted_enrichment"
            })
            row={
                "study_id":sid,"private_source_handle":h,
                "sdg_primary":"ODS 4","sdg_secondary":"","sdg_no_match":"no",
                "pdot_primary":"PDOT 2","pdot_secondary":"","pdot_no_match":"no",
                "uncertain":"no","brief_evidence":"Source-based reason","coder_notes":""
            }
            A.append(dict(row))
            B.append(dict(row))
            if i<201:
                C.append(dict(row))
                queue.append({"study_id":sid,"private_source_handle":h})
        B[0]["sdg_primary"]="ODS 12"
        C[0]["sdg_primary"]="ODS 12"
        B[1]["pdot_primary"]="PDOT 4"
        C[2]["pdot_primary"]="PDOT 4"
        return master,A,B,C,queue

    def test_separate_120_random_and_330_enrichment(self):
        m,a,b,c,q=self.build()
        result,rows=comparison(m,a,b,c,q)
        self.assertEqual(result["n_c_selected"],201)
        self.assertEqual(len(rows),201)
        self.assertEqual(result["a_b_primary_inter_rater"]["ods"][
            "population_random_120"]["disagreement_n"],1)
        self.assertEqual(result["a_b_primary_inter_rater"]["pdot"][
            "population_random_120"]["disagreement_n"],1)
        self.assertEqual(result["c_selected_201_patterns"]["ods"][
            "b_c_same_a_differs"],1)
        self.assertEqual(result["c_selected_201_patterns"]["pdot"][
            "a_c_same_b_differs"],1)
        self.assertEqual(result["c_selected_201_patterns"]["pdot"][
            "a_b_same_c_differs"],1)
        self.assertTrue(all(
            row["expert_consensus_ods_primary"]==""
            and row["expert_consensus_pdot_primary"]=="" for row in rows
        ))

    def test_frozen_source_mismatch_rejected(self):
        m,a,b,c,q=self.build()
        c[10]["private_source_handle"]="mismatched"
        with self.assertRaisesRegex(ValueError,"source handle"):
            comparison(m,a,b,c,q)

    def test_nonrandom_third_roster_mismatch_rejected(self):
        m,a,b,c,q=self.build()
        c.pop()
        with self.assertRaisesRegex(ValueError,"rosters"):
            comparison(m,a,b,c,q)

if __name__=="__main__":
    unittest.main()
