"""Synthetic-only tests for blinded human validation statistics."""
import sys
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from reviewer_human_validation_metrics import (
    agreement,metrics,labels_from_coder,thresholds_from_calibration,NONE
)


class HumanValidationTests(unittest.TestCase):
    def test_independent_coder_kappa(self):
        a=["ODS 1","ODS 2",NONE,"ODS 1","ODS 2"]
        b=["ODS 1","ODS 2",NONE,"ODS 1","ODS 2"]
        r=agreement(a,b)
        self.assertEqual(r["n"],5)
        self.assertAlmostEqual(r["cohen_kappa"],1,places=6)
        changed=agreement(a,[NONE,"ODS 2",NONE,"ODS 2","ODS 2"])
        self.assertLess(changed["cohen_kappa"],1)

    def test_refusal_of_incomplete_human_codes(self):
        x=pd.DataFrame([{"sdg_primary":"","sdg_no_match":"no"},
                        {"sdg_primary":"ODS 1","sdg_no_match":"no"}])
        with self.assertRaises(ValueError):
            labels_from_coder(x,"ods")
        x.loc[0,"sdg_no_match"]="yes"
        self.assertEqual(labels_from_coder(x,"ods").tolist(),[NONE,"ODS 1"])

    def test_metrics_have_support_and_no_match(self):
        a=np.array(["ODS 1","ODS 2",NONE,"ODS 2"])
        b=np.array(["ODS 1","ODS 1","ODS 2","ODS 2"])
        r=metrics(a,b,["ODS 1","ODS 2",NONE])
        self.assertEqual(r["no_match_reference_n"],1)
        self.assertEqual(r["no_match_predicted_n"],0)
        self.assertEqual(len(r["per_class_private"]),3)
        self.assertAlmostEqual(r["accuracy"],.5)

    def test_calibration_runs_only_on_passed_human_arrays(self):
        s=np.array([[.84,.6],[.83,.82],[.6,.89],[.7,.71],[.8,.65]],
                   dtype=np.float32)
        truth=np.array(["ODS 1",NONE,"ODS 2",NONE,"ODS 1"])
        threshold,f1=thresholds_from_calibration(s,truth,["ODS 1","ODS 2"])
        self.assertEqual(len(threshold),2)
        self.assertTrue(0<=f1<=1)


if __name__=="__main__":
    unittest.main()
