"""Pure synthetic paired-bootstrap/matched-pair significance regression tests."""
import sys
import unittest
from pathlib import Path
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from reviewer_four_e5_paired_random_uncertainty import paired_stats


class PairedUncertaintyTests(unittest.TestCase):
    def test_exact_matched_case_gains_and_losses(self):
        a=np.array([True,True,False,False,True,False,True,False])
        b=np.array([True,False,True,True,False,True,True,False])
        r=paired_stats(a,b,n_boot=2000,seed=42)
        self.assertEqual(r["n"],8)
        self.assertEqual(r["baseline_correct_n"],4)
        self.assertEqual(r["candidate_correct_n"],5)
        self.assertEqual(r["candidate_correct_baseline_wrong_n"],3)
        self.assertEqual(r["baseline_correct_candidate_wrong_n"],2)
        self.assertEqual(r["accuracy_delta_points"],12.5)
        self.assertEqual(r["mcnemar_exact_two_sided_p_unadjusted"],1.0)
        lo,hi=r["delta_bootstrap95_points"]
        self.assertLessEqual(lo,r["accuracy_delta_points"])
        self.assertGreaterEqual(hi,r["accuracy_delta_points"])

    def test_exact_mcnemar_all_gains(self):
        a=np.zeros(120,dtype=bool)
        b=np.zeros(120,dtype=bool)
        b[:12]=True
        r=paired_stats(a,b,seed=42,n_boot=1500)
        self.assertEqual(r["accuracy_delta_points"],10.0)
        self.assertEqual(r["candidate_correct_baseline_wrong_n"],12)
        self.assertEqual(r["baseline_correct_candidate_wrong_n"],0)
        self.assertEqual(r["mcnemar_exact_two_sided_p_unadjusted"],round(2/4096,7))

    def test_no_improvement_and_repeatable_bootstrap(self):
        same=np.array([True,False]*60)
        x=paired_stats(same,same,n_boot=1200)
        y=paired_stats(same,same,n_boot=1200)
        self.assertEqual(x,y)
        self.assertEqual(x["accuracy_delta_points"],0)
        self.assertEqual(x["delta_bootstrap95_points"],[0.0,0.0])
        self.assertEqual(x["mcnemar_exact_two_sided_p_unadjusted"],1.0)

    def test_refuse_mismatched_case_pairs(self):
        with self.assertRaisesRegex(ValueError,"same nonempty"):
            paired_stats([True,False],[True])
        with self.assertRaisesRegex(ValueError,"same nonempty"):
            paired_stats([],[])

if __name__=="__main__":
    unittest.main()
