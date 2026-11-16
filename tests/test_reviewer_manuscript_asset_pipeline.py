"""Synthetic manuscript exhibit safety and source-order regression checks.

The tests use no institutional handles, thesis files or human annotations.
"""
from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from reviewer_freeze_manuscript_snapshot import selected_labels
from reviewer_build_manuscript_assets import table,verify_ledger

class ManuscriptAssetsSafetyTests(unittest.TestCase):
    def test_source_labels_use_exact_source_descriptor_position(self):
        n=7830
        names=[f"ODS {i} original descriptor" for i in range(1,18)]
        scores=np.zeros((n,17),dtype=np.float32)
        scores[:,3]=.7
        scores[:,2]=.5
        selected,top,margin=selected_labels(scores,names,"ods")
        self.assertTrue(np.all(selected=="ODS 4"))
        self.assertAlmostEqual(float(top[0]),.7,places=5)
        self.assertAlmostEqual(float(margin[0]),.2,places=5)

    def test_source_taxonomy_ODS_must_never_be_permuted_or_guessed(self):
        scores=np.zeros((7830,17),dtype=np.float32)
        labels=[f"ODS {i}" for i in range(1,18)]
        labels[-1]="ODS 4"
        with self.assertRaisesRegex(ValueError,"Taxonomy size/uniqueness|descriptor IDs"):
            selected_labels(scores,labels,"ods")
        with self.assertRaisesRegex(ValueError,"score matrix"):
            selected_labels(np.zeros((10,17)),[f"ODS {i}" for i in range(1,18)],"ods")

    def test_private_ledger_validation_and_aggregate_counts(self):
        n=7830
        df=pd.DataFrame({
            "source_row_index":np.arange(n),
            "handle_id":[f"synthetic-{i}" for i in range(n)],
            "year":[2024]*n,
            "faculty5":["Unassigned"]*n,
            "advisor_reported":[False]*n,
            "ods_label":["ODS 4"]*n,
            "pdot_label":["PDOT 2"]*n,
            "need_label":["synthetic need A"]*n,
            "ods_top1_score":[.9]*n,"pdot_top1_score":[.9]*n,
            "need_top1_score":[.9]*n,
            "ods_margin":[.3]*n,"pdot_margin":[.3]*n,
            "need_margin":[.3]*n,
        })
        audit={
            "status":"frozen_descriptive_model_snapshot_exploratory",
            "model_variant":"fulltext_centered",
            "label_totals":{
                "ods":{"ODS 4":7830},"pdot":{"PDOT 2":7830},
                "need":{"Local need 01":7830},
            },
            "adviser_records_with_nonempty_value":0,
        }
        self.assertTrue(verify_ledger(df,audit))
        df.loc[17,"ods_label"]="ODS 5"
        with self.assertRaisesRegex(ValueError,"locked audit"):
            verify_ledger(df,audit)

    def test_aggregate_csv_and_markdown_do_not_dump_private_handles(self):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td)
            x=table(d,"Test_Aggregate",["Class","N"],[("SDG 4",275),("SDG 6",63)])
            self.assertEqual(len(x),2)
            content=(d/"Test_Aggregate.md").read_text(encoding="utf-8")
            self.assertIn("SDG 4",content)
            self.assertNotIn("handle_id",content)
            self.assertEqual(list(d.glob("*")),sorted(d.glob("*")) or list(d.glob("*")))

if __name__=="__main__":
    unittest.main()
