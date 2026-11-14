"""Synthetic-only tests for full-corpus versus legacy E5 diagnostics."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from reviewer_compare_fulltext_legacy import (
    sample_distinct_pairs, paired_cosines, sample_neighbors,
    geometry_diagnostics, check_fulltext_report,
)


class FulltextLegacyComparisonTests(unittest.TestCase):
    def setUp(self):
        gen = np.random.default_rng(77)
        x = gen.normal(size=(48, 16)).astype(np.float32)
        x /= np.linalg.norm(x, axis=1, keepdims=True)
        self.old = x
        # Slight geometric perturbation, deliberately NOT identical.
        y = x + .025 * gen.normal(size=x.shape).astype(np.float32)
        self.new = y / np.linalg.norm(y, axis=1, keepdims=True)

    def test_pair_sampling_never_returns_same_row(self):
        gen = np.random.default_rng(4)
        i, j = sample_distinct_pairs(48, 5000, gen)
        self.assertEqual(len(i), 5000)
        self.assertTrue(np.all(i != j))
        self.assertTrue(np.all((j >= 0) & (j < 48)))

    def test_cosines_and_neighbor_exclusion(self):
        i = np.array([0, 2, 9])
        j = np.array([1, 3, 8])
        result = paired_cosines(self.old, i, j, batch_size=2)
        expected = np.sum(self.old[i] * self.old[j], axis=1)
        np.testing.assert_allclose(result, expected, atol=1e-6)
        near = sample_neighbors(self.old, np.array([0, 4, 8]), k=5)
        for row, indices in zip([0, 4, 8], near):
            self.assertEqual(len(indices), 5)
            self.assertNotIn(row, indices)

    def test_geometry_comparison_is_aggregate_only(self):
        report = geometry_diagnostics(
            self.old, self.new, pair_count=1500, anchors=12, k=5, seed=29
        )
        self.assertEqual(report["sampled_distinct_pairs_with_replacement"], 1500)
        self.assertEqual(report["sampled_anchor_documents_without_replacement"], 12)
        self.assertEqual(report["same_thesis_original_vs_fulltext_cosine"]["n"], 48)
        self.assertEqual(report["old_cross_thesis_cosine"]["n"], 1500)
        self.assertTrue(0 <= report["same_thesis_topk_neighbor_set_overlap"]["mean"] <= 1)
        self.assertGreater(report["same_thesis_original_vs_fulltext_cosine"]["median"], .9)
        self.assertNotIn("individual_scores", str(report))

    def test_requires_verified_full_corpus_report(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "report.json"
            stub = {
                "status": "complete_full_corpus_fulltext_E5_aggregated_candidate",
                "population": 7830,
                "model": "intfloat/multilingual-e5-large",
                "full_corpus_counts": {
                    "documents": 7830, "private_matrix_rows": 7830,
                    "private_vector_dimension": 1024,
                    "content_tokens": 286050084, "windows": 854145
                },
            }
            path.write_text(json.dumps(stub), encoding="utf-8")
            self.assertEqual(check_fulltext_report(path)["model"], stub["model"])
            stub["full_corpus_counts"]["windows"] = 854144
            path.write_text(json.dumps(stub), encoding="utf-8")
            with self.assertRaises(ValueError):
                check_fulltext_report(path)


if __name__ == "__main__":
    unittest.main()
