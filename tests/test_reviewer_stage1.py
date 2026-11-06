"""Synthetic tests for reviewer stage-1 statistical reconstruction."""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from reviewer_stage1_stats import (
    clean_faculties, contingency_and_tests, kw_rank_dispersion,
    rarefy_entropy, score_thresholds, coverage_need
)
from reviewer_shared import FIVE_FACULTIES, normalize_codes, bh_adjust


class ReviewerStatisticsTests(unittest.TestCase):
    def test_mappings_are_conservative(self):
        rows = []
        for i, fac in enumerate(FIVE_FACULTIES):
            rows.extend([{"faculty": fac, "career": f"career-{i}"} for _ in range(15)])
            rows.append({"faculty": None, "career": f"career-{i}"})
        rows.append({"faculty": "Facultades", "career": "unknown"})
        x, report = clean_faculties(pd.DataFrame(rows))
        self.assertEqual(report["career_imputed_rows"], 5)
        self.assertEqual(report["unresolved_rows"], 1)
        self.assertEqual(set(x["faculty5"].dropna()), set(FIVE_FACULTIES))

    def test_contingency_and_rarefaction(self):
        g = np.repeat(FIVE_FACULTIES, 45)
        labels = np.array([f"ODS {1 + (i * 3 + j * 5) % 17}"
                           for i in range(5) for j in range(45)])
        obs, expected, result = contingency_and_tests(g, labels, seed=123, permutations=29)
        self.assertEqual(obs.sum(), len(g))
        self.assertEqual(expected.shape, (5, 17))
        self.assertEqual(result["df_nominal"], 64)
        self.assertTrue(0 <= result["permutation_p_value"] <= 1)
        rare = rarefy_entropy(g, labels, draws=12, sample_size=25)
        self.assertEqual(rare["rarefaction_n"], 25)
        self.assertEqual(len(rare["faculties"]), 5)

    def test_dispersion_has_effect_size_and_posthoc(self):
        groups = np.repeat(FIVE_FACULTIES, 25)
        x = np.concatenate([np.arange(25)*.0001 + k*.03 for k in range(5)])
        r = kw_rank_dispersion(x, groups, permutations=21)
        self.assertEqual(len(r["posthoc_rank_biserial_bh"]), 10)
        self.assertGreaterEqual(r["epsilon_squared_clamped"], 0)
        self.assertEqual(r["df"], 4)

    def test_abstention_thresholds_no_claim_of_accuracy(self):
        df = pd.DataFrame({
            "ods_top1_score": [.78,.81,.85], "ods_top2_score": [.77,.808,.83],
            "pdot_top1_score": [.78,.81,.85], "pdot_top2_score": [.77,.808,.83],
            "need_top1_score": [.78,.81,.85], "need_top2_score": [.77,.808,.83],
            "need_top1": ["Need A","Need B","Need A"],
        })
        data = score_thresholds(df)
        self.assertEqual(data["ods"]["top1_score_cutoffs"]["0.800"]["abstain_n"], 1)
        self.assertEqual(data["ods"]["margin_cutoffs"]["0.010"]["ambiguous_n"], 1)
        coverage = coverage_need(df)
        self.assertFalse(coverage["is_original_manuscript_formula_verified"])
        self.assertEqual(sum(x["n"] for x in coverage["needs"]), 3)

    def test_sdg_name_normalization_and_bh(self):
        self.assertEqual(normalize_codes(["ODS 4 Educación", "SDG 14 marine", "unexpected"]),
                         ["ODS 4", "ODS 14", "[invalid]"])
        x = bh_adjust([.001,.1,.03])
        self.assertLessEqual(x[0], x[1])
        self.assertTrue(all(0 <= v <= 1 for v in x))


if __name__ == "__main__":
    unittest.main()
