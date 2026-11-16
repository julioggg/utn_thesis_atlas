"""Synthetic checks of frozen four-E5-variant, separate-coder evaluation."""
import sys
import unittest
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from reviewer_four_e5_variant_dual_coder_metrics import (
    validate_fulltext_source,evaluate_scores_for_coder
)


class FrozenFourE5VariantsTests(unittest.TestCase):
    def test_reclassification_source_gate(self):
        report={
            "status":"fulltext_and_centered_ods_pdot_needs_reclassification_exploratory_not_human_validated",
            "n_theses":7830,
            "variants":["legacy_raw","legacy_centered","fulltext_raw","fulltext_centered"],
            "source_alignment_verified":{"04_vs_05":True},
            "descriptor_source_sha256":"abc"
        }
        self.assertTrue(validate_fulltext_source(report))
        report["n_theses"]=45
        with self.assertRaisesRegex(ValueError,"roster"):
            validate_fulltext_source(report)

    def test_120_random_and_330_enriched_score_against_coder(self):
        indices=np.arange(450,dtype=int)
        strata=np.array(["population_random"]*120+["targeted_enrichment"]*330)
        scores=np.zeros((7830,17),dtype=np.float32)
        scores[:,3]=0.8
        truth=pd.DataFrame([{
            "sdg_primary":"ODS 4","sdg_no_match":"no",
            "pdot_primary":"PDOT 2","pdot_no_match":"no",
        } for _ in range(450)])
        truth.loc[0,"sdg_primary"]="ODS 3"
        values=evaluate_scores_for_coder(
            scores,[f"ODS {i}" for i in range(1,18)],truth,indices,strata
        )
        self.assertEqual(values["random_120"]["n"],120)
        self.assertEqual(values["enriched_330"]["n"],330)
        self.assertEqual(values["random_120"]["accuracy"],round(119/120,6))
        self.assertEqual(values["enriched_330"]["accuracy"],1.0)
        self.assertEqual(values["random_120"]["no_match_predicted_n"],0)
        self.assertTrue(any(
            x["reference_n"]==0 for x in
            values["random_120"]["per_class_private"]
        ))

    def test_pdot_no_match_competes_with_forced_top1(self):
        indices=np.arange(450,dtype=int)
        strata=np.array(["population_random"]*120+["targeted_enrichment"]*330)
        scores=np.zeros((7830,6),dtype=np.float32)
        scores[:,1]=0.7
        truth=pd.DataFrame([{
            "pdot_primary":"PDOT 2","pdot_no_match":"no"
        } for _ in range(450)])
        truth.loc[0,"pdot_primary"]=""
        truth.loc[0,"pdot_no_match"]="yes"
        values=evaluate_scores_for_coder(
            scores,[f"PDOT {i}" for i in range(1,7)],truth,indices,strata
        )
        self.assertEqual(values["random_120"]["no_match_reference_n"],1)
        self.assertEqual(values["random_120"]["no_match_predicted_n"],0)
        self.assertEqual(values["random_120"]["accuracy"],round(119/120,6))

if __name__=="__main__":
    unittest.main()
