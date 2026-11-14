"""Synthetic tests for legacy descriptor replay without loading any AI model."""
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from reviewer_shared import sha256_file
from reviewer_legacy_alignment_replay import (
    freeze_original_dicts, prepare_sentences,
    source_matches_archived_labels, compare_replay
)


def source_inventory(path, dicts):
    return {
        "status":"unverified_ast_descriptor_candidates",
        "candidate_source_inventory":[{
            "relative_path":path.name,
            "sha256":sha256_file(path),
        }],
        "literal_candidates":[{
            "relative_source_path":path.name,
            "variable_name":variable,
            "number_of_entries":len(values),
            "candidate_literal":values,
        } for variable,values in dicts.items()],
    }


class SourceAlignmentReplayTests(unittest.TestCase):
    def setUp(self):
        self.dicts = {
            "PDOT":{f"PDOT {i}":f"territorial area {i}" for i in range(6)},
            "ODS":{f"ODS {i} label":f"description {i}" for i in range(1,18)},
            "NEEDS":{f"Need {i}":f"priority {i}" for i in range(10)},
        }

    def test_exact_source_and_dictionary_order(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            src=root/"utn_atlas_pipeline.py"
            src.write_text("PDOT={}\nODS={}\nNEEDS={}\n")
            inv=source_inventory(src,self.dicts)
            mapped, sha=freeze_original_dicts(inv,root)
            self.assertEqual(mapped["pdot"],self.dicts["PDOT"])
            self.assertEqual(mapped["ods"],self.dicts["ODS"])
            names, texts=prepare_sentences(mapped["ods"])
            self.assertEqual(names[3],"ODS 4 label")
            self.assertEqual(texts[3],
                             "passage: ODS 4 label. description 4")
            self.assertEqual(sha,sha256_file(src))
            src.write_text("changed")
            with self.assertRaisesRegex(ValueError,"differs"):
                freeze_original_dicts(inv,root)

    def test_scores_and_three_historical_ranks_match(self):
        cats=["PDOT A","PDOT B","PDOT C","PDOT D","PDOT E","PDOT F"]
        scores=np.array([
            [.9,.3,.1,.4,.2,.05],
            [.1,.5,.6,.4,.01,.3],
            [.2,.1,.4,.5,.9,.6],
        ],dtype=np.float32)
        rank=np.argsort(-scores,axis=1)[:,:3]
        frame={}
        for r in range(3):
            frame[f"pdot_top{r+1}"]=np.asarray(cats)[rank[:,r]]
            frame[f"pdot_top{r+1}_score"]=scores[np.arange(3),rank[:,r]]
        archive=pd.DataFrame(frame)
        source_matches_archived_labels(
            archive,{"pdot":dict.fromkeys(cats,"descriptor")}
        )
        record=compare_replay(scores,cats,archive,"pdot")
        self.assertTrue(record["all_three_ranks_identical"])
        self.assertEqual(record["ranking"]["1"]["exact_label_agreement"],1.)
        self.assertTrue(record["score_reconstruction_candidate_tolerance_1e_minus_3"])
        self.assertEqual(record["unordered_top3_set_agreement"],1.)
        bad=archive.copy()
        bad["pdot_top1"]=bad["pdot_top2"]
        record=compare_replay(scores,cats,bad,"pdot")
        self.assertEqual(record["ranking"]["1"]["mismatch_count"],3)
        self.assertFalse(record["all_top1_labels_identical"])

    def test_unexpected_category_rejected(self):
        frame=pd.DataFrame({
            f"ods_top{r}":["ODS 99 error"]
            for r in range(1,4)
        })
        for r in range(1,4):
            frame[f"ods_top{r}_score"]=[.7]
        with self.assertRaisesRegex(ValueError,"not in source"):
            source_matches_archived_labels(
                frame,{"ods":{"ODS 1":"descriptor","ODS 2":"descriptor"}}
            )


if __name__=="__main__":
    unittest.main()
