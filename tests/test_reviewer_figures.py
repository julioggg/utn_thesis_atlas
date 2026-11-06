"""Synthetic source-of-truth table/figure reconciliation tests, no Matplotlib required."""
import sys
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from reviewer_rebuild_figures import canonical_tables

class CanonicalReconciliationTests(unittest.TestCase):
    def test_single_source_counts_and_advisor_definitions(self):
        n=7830
        df=pd.DataFrame({
            "handle_id":[f"SYNTH-{i:05d}" for i in range(n)],
            "ods_top1":["ODS 4 Educación de calidad"]*2649+
                       ["ODS 9 Industria"]*(n-2649),
            "pdot_top1":["Sistema Socio Cultural"]*n,
            "need_top1":["A" if i%3 else "B" for i in range(n)],
            "need_top1_score":[.8]*n,
            "advisor":["A"]*12+["B"]*13+[""]*(n-25),
        })
        sdg,pdot,needs,has_advisor,unique_advisors=canonical_tables(df)
        self.assertEqual(sdg["ODS 4"],2649)
        self.assertEqual(sdg.sum(),n)
        self.assertEqual(pdot.sum(),n)
        self.assertEqual(needs["n"].sum(),n)
        self.assertEqual(has_advisor,25)
        self.assertEqual(unique_advisors,2)
        self.assertAlmostEqual(float(needs["share"].sum()),1,places=6)

    def test_bad_population_rejected(self):
        df=pd.DataFrame({
            "handle_id":["1"], "ods_top1":["ODS 4"],"pdot_top1":["A"],
            "need_top1":["B"],"need_top1_score":[.9],"advisor":["A"]
        })
        with self.assertRaises(ValueError):
            canonical_tables(df)

if __name__ == "__main__":
    unittest.main()
