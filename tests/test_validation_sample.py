"""Synthetic-only tests of blinded validation sample design."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from prepare_blinded_validation_sample import (
    allocate_quotas, select_samples, make_private_and_aggregate
)


def fake_corpus(n=360):
    return pd.DataFrame({
        "handle_id": [f"FAKE-ROW-{i:04d}" for i in range(n)],
        "faculty": ["F1", "F2", "F3", "", "F4", "F5"] * (n // 6),
        "year": [2021 + i % 6 for i in range(n)],
        "ods_top1": ["ODS 4"] * (n // 2) + ["ODS 3"] * (n // 3) + ["ODS 14"] * (n // 6),
        "pdot_top1": ["PDOT A" if i % 3 else "PDOT B" for i in range(n)],
        "ods_top1_score": [.8] * n,
        "ods_top2_score": [.795 if i % 4 else .77 for i in range(n)],
        "pdot_top1_score": [.8] * n,
        "pdot_top2_score": [.79 if i % 3 else .75 for i in range(n)],
    })


class DesignTests(unittest.TestCase):
    def test_quotas_sum_to_requested_size(self):
        quotas = allocate_quotas({"B": 15, "A": 60, "C": 1}, total=30,
                                 min_per_label=4)
        self.assertEqual(sum(quotas.values()), 30)
        self.assertEqual(quotas["C"], 1)
        self.assertTrue(all(quotas[x] <= n for x, n in {"B": 15, "A": 60, "C": 1}.items()))

    def test_disjoint_sampling_and_blind_private_templates(self):
        df = fake_corpus()
        selected, quotas = select_samples(df, n_total=90, n_random=30,
                                          seed=42, min_per_label=8)
        self.assertEqual(len(selected), 90)
        self.assertEqual(selected["handle_id"].nunique(), 90)
        self.assertEqual(selected["selection_stratum"].value_counts()["population_random"], 30)
        selected_again, _ = select_samples(df, n_total=90, n_random=30,
                                           seed=42, min_per_label=8)
        self.assertEqual(selected["handle_id"].tolist(),
                         selected_again["handle_id"].tolist())
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "private"
            output = Path(tmp) / "public.json"
            aggregate = make_private_and_aggregate(
                selected, quotas, len(df), 30, 42, destination, output
            )
            self.assertEqual(aggregate["selected_theses"], 90)
            self.assertEqual(aggregate["status"], "prepared_unannotated")
            for name in ("coder_A_private.csv", "coder_B_private.csv"):
                coder = pd.read_csv(destination / name)
                self.assertEqual(len(coder), 90)
                self.assertIn("private_source_handle", coder)
                self.assertNotIn("ods_top1", coder)
                self.assertNotIn("pdot_top1", coder)
                self.assertNotIn("faculty", coder)
                self.assertNotIn("selection_stratum", coder)
            master = pd.read_csv(destination / "sample_master_private.csv")
            self.assertIn("ods_top1", master)
            public = json.dumps(json.loads(output.read_text()))
            self.assertNotIn("FAKE-ROW-", public)

    def test_invalid_duplicate_handle_rejected(self):
        df = fake_corpus(360)
        df.loc[10, "handle_id"] = df.loc[0, "handle_id"]
        with self.assertRaises(ValueError):
            select_samples(df, n_total=90, n_random=30, seed=42, min_per_label=8)


if __name__ == "__main__":
    unittest.main()
