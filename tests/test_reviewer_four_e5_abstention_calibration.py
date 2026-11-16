"""Synthetic threshold/margin abstention tests: 330 calibration only."""
import sys
import unittest
from pathlib import Path
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from reviewer_four_e5_abstention_calibration import (
    predict_abstaining, tune_on_330, MIN_TRAIN_COVERAGE
)

class AbstentionCalibrationTests(unittest.TestCase):
    def test_top1_is_forced_when_thresholds_disabled(self):
        names=["ODS 1","ODS 2","ODS 3"]
        scores=np.array([
            [0.5,0.3,0.2],
            [0.2,0.4,0.41],
            [0.1,0.1,0.1],
        ])
        labels=predict_abstaining(scores,names,-1,-1)
        self.assertEqual(labels.tolist(),["ODS 1","ODS 3","ODS 1"])
        labels=predict_abstaining(scores,names,0.0,0.03)
        self.assertEqual(labels.tolist(),["ODS 1","NONE","NONE"])

    def test_330_enriched_calibration_with_abstention_and_fixed_coverage(self):
        names=["ODS 1","ODS 2","ODS 3"]
        score=np.zeros((330,3),dtype=np.float32)
        truth=[]
        for i in range(330):
            if i<130:
                score[i]=[0.93,0.1,0.09]
                truth.append("ODS 1")
            elif i<260:
                score[i]=[0.1,0.93,0.09]
                truth.append("ODS 2")
            else:
                score[i]=[0.35,0.34,0.32]
                truth.append("NONE")
        (t,m),result,tried=tune_on_330(score,np.asarray(truth),names)
        self.assertGreater(tried,0)
        self.assertGreaterEqual(1-result["no_match_predicted_n"]/330,
                                MIN_TRAIN_COVERAGE)
        self.assertGreaterEqual(result["macro_f1_present_or_predicted_classes"],0.8)
        predicted=predict_abstaining(score,names,t,m)
        self.assertEqual(len(predicted),330)
        self.assertEqual((predicted=="NONE").sum(),70)
        self.assertEqual((predicted[:260]=="NONE").sum(),0)

    def test_prevent_wrong_train_size_and_score_shape(self):
        labels=["PDOT 1","PDOT 2"]
        with self.assertRaisesRegex(ValueError,"330"):
            tune_on_330(np.zeros((120,2)),["NONE"]*120,labels)
        with self.assertRaisesRegex(ValueError,"score grid"):
            predict_abstaining(np.zeros((10,2)),["PDOT 1"],0.1,0.1)

    def test_refuse_nonfinite_scores(self):
        score=np.zeros((330,2))
        score[9,1]=np.nan
        with self.assertRaisesRegex(ValueError,"Nonfinite"):
            tune_on_330(score,["NONE"]*330,["PDOT 1","PDOT 2"])

if __name__=="__main__":
    unittest.main()
