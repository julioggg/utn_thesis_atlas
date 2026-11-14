"""Synthetic CPU tests for fulltext class concentration and length drift audit."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from reviewer_fulltext_drift_diagnostic import (
    N, concentrations, js_divergence, transitions, length_quartiles, diagnose,
)


class FulltextDriftDiagnosticTests(unittest.TestCase):
    def test_entropy_concentration_and_js(self):
        names = ["A", "B", "C"]
        original = np.asarray(["A"] * 6 + ["B"] * 6)
        concentrated = np.asarray(["A"] * 11 + ["B"])
        raw = concentrations(original, names)
        changed = concentrations(concentrated, names)
        self.assertLess(changed["normalized_shannon_entropy"],
                        raw["normalized_shannon_entropy"])
        self.assertGreater(changed["herfindahl_concentration"],
                           raw["herfindahl_concentration"])
        self.assertEqual(js_divergence([1, 1], [1, 1]), 0.)
        self.assertAlmostEqual(js_divergence([1, 0], [0, 1]), 1., places=6)

    def test_transitions_suppress_small_transition_cells(self):
        original = np.asarray(["ODS A"] * 50 + ["ODS B"] * 5)
        revised = np.asarray(["ODS B"] * 30 + ["ODS A"] * 20 + ["ODS A"] * 5)
        report = transitions(original, revised, min_flow=25, cap=10)
        self.assertEqual(report["total_changed_top1"], 35)
        self.assertEqual(report["top_changed_label_flows"][0]["n"], 30)
        self.assertEqual(report["other_changed_label_flows_combined_n"], 5)

    def test_length_quartiles_cover_every_row_once(self):
        x = np.arange(1,N+1,dtype=np.int64)
        quartiles = length_quartiles(x)
        self.assertEqual(sum(len(x) for x in quartiles.values()),N)
        self.assertEqual(set(np.concatenate(list(quartiles.values())).tolist()),
                         set(range(N)))
        self.assertLessEqual(
            max(len(y) for y in quartiles.values()) -
            min(len(y) for y in quartiles.values()), 1
        )

    def test_domain_report_privacy(self):
        ncat = 6
        labels = [f"PDOT {i}" for i in range(ncat)]
        original = np.asarray(labels)[np.arange(N) % ncat]
        raw = np.zeros((N,ncat),dtype=np.float32)
        raw[:,0] = 0.9
        raw[np.arange(N),np.arange(N)%ncat] = .95
        altered = np.zeros_like(raw)
        altered[:,0] = .96
        score = {
            "legacy_raw": raw,
            "legacy_centered": altered,
            "fulltext_raw": altered,
            "fulltext_centered": raw,
        }
        content = np.arange(1,N+1,dtype=np.int64)
        groups = length_quartiles(content)
        report = diagnose(
            "pdot",labels,original,score,content,np.ones(N,dtype=np.int64),groups
        )
        self.assertEqual(report["n"],N)
        self.assertEqual(
            report["representations"]["fulltext_raw"]["concentration"]["largest_category_n"],
            N
        )
        self.assertEqual(len(report["by_original_document_token_quartile"]),4)
        self.assertNotIn("handle_id",str(report))
        self.assertNotIn("source_row_index",str(report))

    def test_bad_category_distribution_rejected(self):
        with self.assertRaisesRegex(ValueError,"class/category mismatch"):
            concentrations(["A","B","C"],["A","B"])


if __name__=="__main__":
    unittest.main()
