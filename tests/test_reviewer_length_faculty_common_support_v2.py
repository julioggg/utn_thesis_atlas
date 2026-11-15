"""Synthetic tests: never fabricate missing Health Q4 faculty cells."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from reviewer_length_faculty_common_support_v2 import (
    N, GROUPS, standardize_common_support
)
from reviewer_length_faculty_standardization import GROUP_UNKNOWN
from reviewer_shared import FIVE_FACULTIES


class CommonSupportV2Tests(unittest.TestCase):
    def setUp(self):
        # Consecutive increasing lengths assign predictable Q1..Q4.
        counts = (
            (300, 300, 300, 300, 300, 458),
            (300, 300, 300, 300, 300, 458),
            (300, 300, 300, 300, 300, 457),
            (420, 400, 400, 20, 400, 317),
        )
        self.assertEqual([sum(c) for c in counts],
                         [1958, 1958, 1957, 1957])
        self.lengths = np.arange(1, N + 1, dtype=np.int64)
        self.groups = []
        self.original = []
        # Deliberately no *within-faculty* length trend.
        probabilities = (.1, .2, .3, .4, .5, .6)
        for row in counts:
            for index, count in enumerate(row):
                self.groups.extend([GROUPS[index]] * count)
                successes = round(count * probabilities[index])
                self.original.extend(["TGT"] * successes)
                self.original.extend(["OTHER"] * (count - successes))
        self.groups = np.asarray(self.groups, dtype=str)
        self.original = np.asarray(self.original, dtype=str)
        self.revised = self.original.copy()

    def test_health_sparse_q4_excluded_without_lowering_threshold(self):
        report = standardize_common_support(
            self.groups, self.lengths, self.original, self.revised,
            "TGT", min_n=30, boots=300, seed=41
        )
        self.assertNotIn(FIVE_FACULTIES[3], report["groups_included"])
        self.assertEqual(
            report["groups_excluded_due_to_insufficient_q1_or_q4_support"],
            [FIVE_FACULTIES[3]],
        )
        self.assertEqual(len(report["groups_included"]), 5)
        self.assertEqual(sum(report["eligible_groups_original_full_corpus_weights"].values()),
                         1.0)
        self.assertLess(report["eligible_full_corpus_n"], N)
        self.assertIn(
            "fulltext_target_share",
            report["direct_standardization_on_common_support"]
        )
        ci = report["direct_standardization_on_common_support"]["fulltext_target_share"][
            "within_cell_bootstrap_95pct_ci_pp"
        ]
        self.assertLessEqual(ci[0], ci[1])
        self.assertIsInstance(report["eligible_full_corpus_n"], int)

    def test_mixture_effect_is_reduced_for_no_within_group_trend(self):
        result = standardize_common_support(
            self.groups, self.lengths, self.original, self.revised,
            "TGT", boots=300
        )
        crude = result["crude_all_faculties"]["fulltext_target_share"][
            "q4_minus_q1_percentage_points"
        ]
        adjusted = result["direct_standardization_on_common_support"][
            "fulltext_target_share"
        ]["q4_minus_q1_percentage_points"]
        self.assertGreater(abs(crude), 2)
        self.assertLess(abs(adjusted), .5)
        self.assertEqual(
            result["direct_standardization_on_common_support"][
                "original_vs_fulltext_flip_share"
            ]["q4_minus_q1_percentage_points"],
            0.
        )

    def test_refuses_threshold_relaxation_and_unknown_group(self):
        with self.assertRaisesRegex(ValueError, "minimum privacy"):
            standardize_common_support(
                self.groups, self.lengths, self.original,
                self.revised, "TGT", min_n=3
            )
        modified = self.groups.copy()
        modified[0] = "invalid faculty"
        with self.assertRaisesRegex(ValueError, "five verified"):
            standardize_common_support(
                modified, self.lengths, self.original, self.revised, "TGT"
            )

    def test_no_common_support_must_fail(self):
        with self.assertRaisesRegex(ValueError, "No faculties"):
            standardize_common_support(
                self.groups, self.lengths, self.original, self.revised,
                "TGT", min_n=1000
            )


if __name__ == "__main__":
    unittest.main()
