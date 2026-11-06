"""Unit tests for pooling variants: synthetic arrays only, no GPU or real theses."""
import sys
import unittest
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from study_pooling_sensitivity import pool_strategies, comparisons


class PoolingTests(unittest.TestCase):
    def test_outputs_are_normalized(self):
        rng = np.random.default_rng(19)
        vectors = rng.normal(size=(30, 1024)).astype("float32")
        vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
        weights = np.full(30, 384)
        pooled = pool_strategies(vectors, weights)
        self.assertEqual(set(pooled), {"all_weighted", "middle_80pct",
                                      "first_25pct", "equal_three_regions"})
        self.assertTrue(all(v.shape == (1024,) for v in pooled.values()))
        self.assertTrue(all(abs(np.linalg.norm(v) - 1) < 1e-5
                            for v in pooled.values()))

    def test_front_and_trim_proxies_are_distinct(self):
        vectors = np.zeros((20, 1024), dtype=np.float32)
        vectors[:5, 0] = 1
        vectors[5:, 1] = 1
        pooled = pool_strategies(vectors, np.ones(20))
        self.assertGreater(pooled["first_25pct"][0], 0.99)
        self.assertGreater(pooled["all_weighted"][1], 0.9)
        self.assertGreater(pooled["middle_80pct"][1], 0.9)

    def test_single_chunk_remains_supported(self):
        arr = np.zeros((1, 1024), dtype=np.float32)
        arr[0, 2] = 1.
        pooled = pool_strategies(arr, [20])
        self.assertTrue(all(np.isclose(v[2], 1) for v in pooled.values()))

    def test_invalid_weights_rejected(self):
        arr = np.ones((2, 1024), dtype=np.float32)
        with self.assertRaises(ValueError):
            pool_strategies(arr, [1, -3])

    def test_aggregate_output_omits_row_data(self):
        original = np.eye(3, 1024, dtype=np.float32)
        variants = {"all_weighted": original.copy()}
        result = comparisons(original, variants)
        self.assertEqual(result["all_weighted"]["same_thesis_cosine_vs_legacy"]["n"], 3)
        self.assertEqual(result["all_weighted"]["cross_thesis_pairwise_cosine"]["n"], 3)
        self.assertNotIn("row_indices", str(result))


if __name__ == "__main__":
    unittest.main()
