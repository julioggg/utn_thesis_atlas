"""Synthetic, dependency-light tests for cluster/UMAP stability preprocessing."""
import sys
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from reviewer_stage3_stability import deterministic_sample, neighbor_indices


class StabilitySamplingTests(unittest.TestCase):
    def test_stratified_sample_deterministic_and_unique(self):
        df = pd.DataFrame({
            "faculty5": ["A"]*150 + ["B"]*50 + [None]*30
        })
        a, groups = deterministic_sample(df, 100, seed=12)
        b, _ = deterministic_sample(df, 100, seed=12)
        self.assertEqual(len(a),100)
        self.assertEqual(len(set(a.tolist())),100)
        self.assertEqual(a.tolist(),b.tolist())
        self.assertEqual(sum(groups.values()),100)
        self.assertIn("[unassigned]",groups)

    def test_knn_disallows_self_and_selects_closest(self):
        xy = np.array([[0,0],[0,1],[3,0],[3,1]],dtype=np.float32)
        ix = neighbor_indices(xy,k=1)
        self.assertEqual(ix.shape,(4,1))
        self.assertNotEqual(ix[0,0],0)
        self.assertEqual(ix[0,0],1)

    def test_invalid_sample_size(self):
        df = pd.DataFrame({"faculty5": ["A"]*100})
        with self.assertRaises(ValueError):
            deterministic_sample(df, 150, seed=10)


if __name__ == "__main__":
    unittest.main()
