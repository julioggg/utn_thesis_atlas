"""Synthetic-only tests: direct faculty standardization separates mix from length."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from reviewer_length_faculty_standardization import (
    N, GROUP_UNKNOWN, contrast_by_quartiles, strict_group_labels
)
from reviewer_shared import FIVE_FACULTIES


class FacultyLengthTests(unittest.TestCase):
    def setUp(self):
        self.groups = list(FIVE_FACULTIES) + [GROUP_UNKNOWN]
        q_sizes = [1958, 1958, 1957, 1957]
        q_distributions = [
            [600,450,300,220,200,188],
            [328,327,326,326,326,325],
            [327,326,326,326,326,326],
            [188,200,220,300,450,599],
        ]
        assert all(sum(dist)==s for dist,s in zip(q_distributions,q_sizes))
        self.length = np.arange(1,N+1,dtype=np.int64)
        self.faculty = []
        self.labels = []
        rates = [.1,.2,.3,.4,.5,.6]
        for counts in q_distributions:
            for j, n in enumerate(counts):
                self.faculty.extend([self.groups[j]]*n)
                self.labels.extend(["TGT"]*round(n*rates[j]))
                self.labels.extend(["OTHER"]*(n-round(n*rates[j])))
        self.faculty=np.asarray(self.faculty)
        self.labels=np.asarray(self.labels)

    def test_faculty_standardization_reduces_artificial_length_gradient(self):
        result = contrast_by_quartiles(
            self.faculty,self.length,self.labels,self.labels,"TGT"
        )
        crude = result["endpoint_q4_minus_q1"]["crude"][
            "fulltext_target_label_share_q4_minus_q1_percentage_points"
        ]
        adjusted = result["endpoint_q4_minus_q1"][
            "standardized_on_original_faculty_mix"
        ]["fulltext_target_label_share_q4_minus_q1_percentage_points"]
        self.assertGreater(crude, 5)
        self.assertLess(abs(adjusted), 0.5)
        self.assertEqual(sum(g["population_group_n"] for g in
                             result["by_original_verified_faculty_or_unknown"]),N)

    def test_verified_only_not_heuristic_mapping(self):
        known = list(FIVE_FACULTIES) + ["Facultades","",None]
        groups = strict_group_labels(known)
        self.assertEqual(groups[0],FIVE_FACULTIES[0])
        self.assertTrue(all(x==GROUP_UNKNOWN for x in groups[-3:]))

    def test_strict_input_and_suppression(self):
        invalid = self.faculty.copy()
        invalid[0] = "Another Faculty"
        with self.assertRaisesRegex(ValueError,"five original"):
            contrast_by_quartiles(invalid,self.length,self.labels,self.labels,"TGT")
        report = contrast_by_quartiles(
            self.faculty,self.length,self.labels,self.labels,"TGT",
            min_cell=1000
        )
        self.assertIsNone(
            report["quartile_summaries"][0]["standardized_on_original_faculty_mix"]
        )
        self.assertTrue(all(
            row["q1_n"] is None for row in
            report["by_original_verified_faculty_or_unknown"]
        ))


if __name__=="__main__":
    unittest.main()
