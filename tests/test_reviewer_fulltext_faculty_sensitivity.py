"""Synthetic checks for faculty strict-vs-imputed sensitivity, original/fulltext."""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from reviewer_shared import FIVE_FACULTIES
from reviewer_fulltext_faculty_sensitivity import (
    strict_faculty_mask, study_views, VIEWS
)
from reviewer_fulltext_anisotropy import center_and_normalize


class FulltextFacultySensitivityTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(2026)
        rows = []
        for index, faculty in enumerate(FIVE_FACULTIES):
            for i in range(40):
                rows.append({"faculty": faculty, "career": f"Career {index}"})
            for i in range(3):
                rows.append({"faculty": None, "career": f"Career {index}"})
        rows.extend([
            {"faculty": "Facultades", "career": "Unmapped"},
            {"faculty": "", "career": ""},
        ])
        self.frame = pd.DataFrame(rows)
        x = rng.normal(size=(len(rows), 1024)).astype(np.float32)
        x[:, 0] += 6
        x /= np.linalg.norm(x, axis=1, keepdims=True)
        y = x + rng.normal(size=x.shape).astype(np.float32) * .015
        y /= np.linalg.norm(y, axis=1, keepdims=True)
        cx, _, _ = center_and_normalize(x)
        cy, _, _ = center_and_normalize(y)
        self.embeddings = dict(zip(VIEWS, (x, cx, y, cy)))

    def test_verified_counts_not_misc_faculty(self):
        flags = strict_faculty_mask(self.frame)
        self.assertEqual(int(flags.sum()), 200)
        self.assertFalse(flags[-1])
        self.assertFalse(flags[-2])

    def test_four_variants_and_strict_vs_imputed(self):
        result = study_views(self.frame, self.embeddings, sample_n=35)
        self.assertEqual(result["strict_original_rows"], 200)
        self.assertEqual(result["added_heuristic_imputed_rows"], 15)
        self.assertEqual(result["conservative_including_imputed_rows"], 215)
        self.assertEqual(result["original_missing_or_other_rows_excluded"], 17)
        self.assertEqual(set(result["sensitivity"]), {
            "strict_original_faculty_only", "conservative_career_imputation"
        })
        for definition in result["sensitivity"].values():
            self.assertEqual(set(definition), set(VIEWS))
            for candidate in definition.values():
                self.assertEqual(candidate["balanced_knn"]["balanced_n"], 175)
                self.assertTrue(
                    0 <= candidate["balanced_knn"]["k_statistics"]["15"]
                    ["fraction_neighbors_other_faculty"] <= 1
                )

    def test_bad_embeddings_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "four aligned"):
            study_views(self.frame, {"legacy_raw": self.embeddings["legacy_raw"]})
        bad = dict(self.embeddings)
        bad["fulltext_raw"] = bad["fulltext_raw"][:-1]
        with self.assertRaisesRegex(ValueError, "Incorrect/misaligned"):
            study_views(self.frame, bad)


if __name__ == "__main__":
    unittest.main()
