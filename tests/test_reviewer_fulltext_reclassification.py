"""Synthetic-only unit tests for safe fulltext SDG/PDOT reclassification."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from reviewer_fulltext_reclassification import (
    N, DOMAINS, replay_gate, cosine_scores, top3,
    domain_summary, _normalize_residuals
)


class FulltextReclassificationTests(unittest.TestCase):
    def make_replay(self):
        return {
            "status":"historical_original_alignment_replayed_candidate",
            "n_corpus_rows": N,
            "n_original_descriptor_sentences": 33,
            "model":"intfloat/multilingual-e5-large",
            "descriptor_encoding":{"prefix":"passage: "},
            "domains":{
                d: {
                    "n":N, "unordered_top3_set_agreement":1.,
                    "ranking":{
                        str(i):{
                            "mismatch_count":(
                                (1,2,1)[i-1] if d=="need" else 0
                            ),
                            "absolute_score_error_q99":2.4e-7,
                        } for i in range(1,4)
                    }
                } for d in DOMAINS
            }
        }

    def test_historical_replay_requires_strict_fidelity(self):
        report = self.make_replay()
        accepted = replay_gate(report)
        self.assertEqual(accepted["pdot"]["replay_rank_1_to_3_mismatches"],[0,0,0])
        self.assertEqual(accepted["need"]["replay_rank_1_to_3_mismatches"],[1,2,1])
        report["domains"]["need"]["ranking"]["1"]["mismatch_count"]=2
        with self.assertRaisesRegex(ValueError, "ranking"):
            replay_gate(report)

    def test_exact_top_three_and_no_source_scores_leaked(self):
        labels = ["SDG A", "SDG B", "SDG C"]
        scores = np.tile(np.asarray([[.9,.7,.1]], dtype=np.float32), (N,1))
        archived = np.tile(np.asarray(labels, dtype=str), (N,1))
        first = np.asarray(["SDG A"] * N)
        order, ordered_scores=top3(scores)
        self.assertEqual(order.shape, (N,3))
        self.assertAlmostEqual(float(ordered_scores[0,0]),.9,places=6)
        audit=domain_summary(scores, labels, first, archived)
        self.assertEqual(audit["top1_changed_against_original_n"],0)
        self.assertEqual(audit["identical_top3_set_against_original_n"],N)
        self.assertEqual(audit["uncalibrated_margin_le_counts"]["0.010"],0)
        self.assertEqual(audit["top1_category_counts_candidate_unvalidated"]["SDG A"],N)
        self.assertNotIn("handle_id",str(audit))

    def test_unit_normalized_centered_descriptors_and_cosine(self):
        docs = np.asarray([[1,0,0],[0,1,0]],dtype=np.float32)
        descriptor = np.asarray([[1,0,0],[0,1,0]],dtype=np.float32)
        np.testing.assert_allclose(cosine_scores(docs, descriptor), np.eye(2), atol=1e-6)
        mean = np.asarray([.2,.2,.1],dtype=np.float32)
        centered=_normalize_residuals(descriptor,mean)
        np.testing.assert_allclose(np.linalg.norm(centered,axis=1),1,atol=1e-6)
        with self.assertRaises(ValueError):
            _normalize_residuals(descriptor,descriptor[0])

    def test_top3_rejects_too_few_categories(self):
        with self.assertRaisesRegex(ValueError,"at least 3"):
            top3(np.ones((2,2),dtype=np.float32))


if __name__=="__main__":
    unittest.main()
