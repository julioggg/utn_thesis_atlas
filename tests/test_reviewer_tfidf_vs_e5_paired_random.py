"""Synthetic regression tests for lexical versus E5 matched-pair metrics."""
import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from reviewer_tfidf_vs_e5_paired_random import key_labels,paired_summary
from reviewer_human_validation_metrics import PDOT_ID

class LexicalE5PairedTests(unittest.TestCase):
    def test_taxonomy_preserves_original_descriptor_order(self):
        ods=[f"ODS {i} Goal" for i in range(17,0,-1)]
        self.assertEqual(key_labels(ods,"ods"),[f"ODS {i}" for i in range(17,0,-1)])
        pdot=list(PDOT_ID)
        canonical=list(PDOT_ID.values())
        # E5 source report: historical full category names.
        self.assertEqual(key_labels(pdot,"pdot"),canonical)
        # TF-IDF frozen .npz: already normalized PDOT 1..6.
        self.assertEqual(key_labels(canonical,"pdot"),canonical)
        # Reversed order must be preserved, never sorted or reindexed.
        self.assertEqual(key_labels(canonical[::-1],"pdot"),canonical[::-1])
        with self.assertRaisesRegex(ValueError,"human codebook"):
            key_labels(["ODS 4"],"ods")
        with self.assertRaisesRegex(ValueError,"human codebook"):
            key_labels(canonical[:-1]+[pdot[-1]],"pdot")

    def test_paired_difference_and_macrof1_fully_recomputed(self):
        truth=np.array(["ODS 4"]*60+["ODS 3"]*60)
        lexical=np.array(["ODS 4"]*55+["ODS 3"]*5+["ODS 3"]*45+["ODS 4"]*15)
        e5=np.array(["ODS 4"]*60+["ODS 3"]*40+["ODS 4"]*20)
        x=paired_summary(truth,lexical,e5,"ods",1500,42)
        self.assertEqual(x["lexical_accuracy"],round(100/120,6))
        self.assertEqual(x["candidate_accuracy"],round(100/120,6))
        self.assertEqual(x["paired_candidate_minus_lexical"]["accuracy_delta_points"],0)
        self.assertEqual(x["reference_no_match"],0)
        self.assertEqual(x["lexical_no_match_predicted"],0)
        self.assertEqual(x["candidate_no_match_predicted"],0)

    def test_refuse_unpaired_sample(self):
        with self.assertRaisesRegex(ValueError,"120 identical"):
            paired_summary(["PDOT 2"]*119,["PDOT 2"]*119,["PDOT 2"]*119,
                           "pdot",1500,42)

    def test_pdot_compatible_with_none_truth(self):
        truth=["NONE"]+["PDOT 2"]*119
        lexical=["PDOT 2"]*120
        candidate=["PDOT 2"]*120
        x=paired_summary(truth,lexical,candidate,"pdot",1000,42)
        self.assertEqual(x["reference_no_match"],1)
        self.assertEqual(x["lexical_accuracy"],round(119/120,6))
        self.assertEqual(x["paired_candidate_minus_lexical"]["mcnemar_exact_two_sided_p_unadjusted"],1)

if __name__=="__main__":
    unittest.main()

