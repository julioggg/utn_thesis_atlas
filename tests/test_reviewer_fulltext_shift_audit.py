"""Synthetic-only checks of safe label-shift and frozen validation coverage."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from reviewer_fulltext_shift_audit import compare_cohort, report_domain, N, VARIANTS


class ShiftAuditTests(unittest.TestCase):
    def setUp(self):
        self.baseline = np.tile(np.asarray(["ODS A","ODS B","ODS C"],dtype=str),N//3)
        self.versions = {key: self.baseline.copy() for key in VARIANTS}
        self.versions["fulltext_raw"][:31] = "ODS B"
        self.versions["fulltext_centered"][:17] = "ODS C"
        self.cohorts = {
            "population_random": np.arange(120),
            "targeted_enrichment": np.arange(120,450),
        }

    def test_aggregate_changes_and_counts(self):
        result = report_domain(self.baseline, self.versions,self.cohorts)
        self.assertEqual(result["all_theses"]["historical_vs_fulltext_raw_changed_n"],21)
        self.assertEqual(result["all_theses"]["fulltext_raw_vs_centered_changed_n"],27)
        self.assertEqual(result["frozen_sample_strata"]["population_random"]["n_theses"],120)
        self.assertEqual(result["frozen_sample_strata"]["targeted_enrichment"]["n_theses"],330)
        for key in ("historical_count","fulltext_raw_count","fulltext_centered_count"):
            self.assertEqual(sum(x[key] for x in result["changed_class_prevalence"]),N)
        self.assertNotIn("handle_id",str(result))
        self.assertNotIn("row_index",str(result))

    def test_refuse_duplicate_indices(self):
        with self.assertRaisesRegex(ValueError,"unique"):
            compare_cohort(self.baseline,self.versions,np.asarray([0,0]))

    def test_bad_variant_array_size_fails(self):
        bad=dict(self.versions)
        bad["fulltext_raw"]=bad["fulltext_raw"][:-1]
        with self.assertRaisesRegex(ValueError,"row count"):
            report_domain(self.baseline,bad,self.cohorts)


if __name__=="__main__":
    unittest.main()
