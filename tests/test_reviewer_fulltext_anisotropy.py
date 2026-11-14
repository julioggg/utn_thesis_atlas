"""Synthetic CPU tests: anisotropy, exact pairwise mean identity, and privacy."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from reviewer_fulltext_anisotropy import (
    center_and_normalize, diagnose_pair,
    exact_off_diagonal_mean_cosine, same_anchor_knn_overlap
)


class AnisotropyTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(17)
        n, d = 44, 64
        base = rng.normal(size=(n, d)).astype(np.float32)
        base /= np.linalg.norm(base, axis=1, keepdims=True)
        shared = np.zeros((n, d), dtype=np.float32)
        shared[:, 0] = 4.
        self.original = (base + shared)
        self.original /= np.linalg.norm(self.original, axis=1, keepdims=True)
        altered = base + shared + rng.normal(size=(n, d)).astype(np.float32)*.015
        self.fulltext = altered/np.linalg.norm(altered, axis=1, keepdims=True)

    def test_centering_reduces_common_direction(self):
        centered, residual, mean_norm = center_and_normalize(self.original)
        self.assertEqual(centered.shape, self.original.shape)
        self.assertEqual(residual["n"], len(self.original))
        self.assertGreater(mean_norm, .9)
        np.testing.assert_allclose(np.linalg.norm(centered, axis=1), 1, atol=1e-5)
        self.assertLess(
            exact_off_diagonal_mean_cosine(centered),
            exact_off_diagonal_mean_cosine(self.original),
        )

    def test_exact_mean_identity_matches_pairwise_matrix(self):
        x = self.original.astype(np.float64)
        gram = x @ x.T
        direct = gram[np.triu_indices(len(x), k=1)].mean()
        self.assertAlmostEqual(
            direct, exact_off_diagonal_mean_cosine(x), places=5
        )

    def test_diagnostic_follows_aggregate_privacy(self):
        result = diagnose_pair(
            self.original, self.fulltext,
            pair_count=400, anchors=12, k=5, seed=13
        )
        self.assertEqual(result["n_documents"], 44)
        self.assertIn("fulltext_mean_centered", result["pairwise_cosine_distributions"])
        self.assertIn(
            "original_vs_fulltext_centered", result["topk_neighbor_set_overlap"]
        )
        self.assertNotIn("record_ids", str(result))
        self.assertTrue(
            0 <= result["topk_neighbor_set_overlap"]["fulltext_raw_vs_centered"]["mean"] <= 1
        )

    def test_reject_degenerate_centering(self):
        duplicated = np.ones((4, 16), dtype=np.float32)
        duplicated /= np.linalg.norm(duplicated, axis=1, keepdims=True)
        with self.assertRaises(ValueError):
            center_and_normalize(duplicated)


if __name__ == "__main__":
    unittest.main()
