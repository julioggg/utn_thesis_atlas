"""Tests for original-space neighborhood mixing, diversity and partial-year exclusion."""
import sys
import unittest
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from reviewer_shared import FIVE_FACULTIES
from reviewer_stage2_geometry import (
    centroid_geometry, balanced_knn_mixing,
    topic_bridge_candidates, conservative_growth
)


class GeometryTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(321)
        self.labels = np.repeat(FIVE_FACULTIES, 42)
        centers = np.eye(5,1024, dtype="float32")
        x = np.asarray([
            centers[i//42] + .12*rng.normal(size=1024)
            for i in range(210)
        ], dtype=np.float32)
        self.vectors = x/np.linalg.norm(x, axis=1, keepdims=True)

    def test_centroids_and_knn_balanced(self):
        d, centers = centroid_geometry(self.vectors, self.labels)
        self.assertEqual(d.shape, (5,5))
        self.assertTrue(np.allclose(d, d.T, atol=1e-5))
        self.assertTrue(np.all(np.diag(d)==0))
        r = balanced_knn_mixing(self.vectors,self.labels,per_faculty=37,
                                ks=(5,15,30),seed=11)
        self.assertEqual(r["balanced_n"], 185)
        self.assertTrue(0 <= r["k_statistics"]["15"]["fraction_neighbors_other_faculty"] <= 1)
        self.assertGreater(r["random_group_mix_expectation_exact"], .75)

    def test_topic_bridges_have_strict_minimum(self):
        d, _ = centroid_geometry(self.vectors, self.labels)
        topics = np.array(["Topic A" if i<82 else "Topic B" for i in range(210)])
        r = topic_bridge_candidates(topics,self.labels,d,minimum_n=20,minimum_per_second_faculty=10)
        self.assertGreaterEqual(r["qualifying_topic_ids"],1)
        self.assertTrue(all(x["n_five_faculty"] >= 20 for x in r["top_candidates"]))

    def test_partial_2026_is_never_used(self):
        topics = np.array(["Topic A","Topic A","Topic B","Topic A"]*30)
        years = np.array([2021,2024,2025,2026]*30)
        trend = conservative_growth(topics,years,min_recent=10)
        self.assertTrue(trend["2026_excluded_due_to_incomplete_year"])
        self.assertEqual(trend["annual_counts"]["2026"],30)
        self.assertEqual(trend["top_growth_candidate_topic_ids"][0]["2024_25_n"],30)


if __name__ == "__main__":
    unittest.main()
