"""Regression: published model metrics must feed Figure S01 without domain-key drift.

Entire fixture is synthetic; no thesis text, handles, private judgements or
model outputs are stored in this repository.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from reviewer_build_manuscript_assets import model_validation
from reviewer_render_manuscript_figures import models


class SupplementaryFigureIntegrationTests(unittest.TestCase):
    def test_builder_output_renders_sdg_and_pdot_comparisons(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            audits = workspace / "docs/audits"
            audits.mkdir(parents=True)
            class_dir = workspace / "data/revision_private/four_e5_variant_coder_metrics_v2"
            class_dir.mkdir(parents=True)

            v2 = {
                "status": "four_frozen_E5_representations_vs_two_independent_coders_not_adjudicated",
                "comparisons": {},
            }
            lexical = {
                "status": "historical_source_lexical_TFIDF_ODS_PDOT_AB_validation_exploratory",
                "comparisons": {},
            }
            paired = {
                "status": "exploratory_paired_TFIDF_vs_frozen_E5_on_120_random",
                "comparisons": {},
            }
            variants = ("legacy_raw", "legacy_centered", "fulltext_raw", "fulltext_centered")
            for domain, classes in (("ods", 17), ("pdot", 6)):
                v2["comparisons"][domain] = {}
                lexical["comparisons"][domain] = {"human_coders": {}}
                paired["comparisons"][domain] = {}
                for variant in variants:
                    v2["comparisons"][domain][variant] = {}
                    for coder in ("A", "B"):
                        v2["comparisons"][domain][variant][coder] = {
                            "random_120": {
                                "n": 120,
                                "accuracy": 0.54,
                                "macro_f1_present_or_predicted_classes": 0.41,
                            }
                        }
                for coder in ("A", "B"):
                    lexical["comparisons"][domain]["human_coders"][coder] = {
                        "random_120": {
                            "n": 120,
                            "accuracy": 0.50,
                            "macro_f1_present_or_predicted_classes": 0.39,
                        }
                    }
                    paired["comparisons"][domain][coder] = {}
                    for variant in ("legacy_raw", "fulltext_centered"):
                        paired["comparisons"][domain][coder][variant] = {
                            "paired_candidate_minus_lexical": {
                                "n": 120,
                                "accuracy_delta_points": 4.0,
                                "delta_bootstrap95_points": [-3.0, 11.0],
                                "candidate_correct_baseline_wrong_n": 20,
                                "baseline_correct_candidate_wrong_n": 15,
                                "mcnemar_exact_two_sided_p_unadjusted": 0.5,
                            }
                        }
                    rows = []
                    for idx in range(classes + 1):
                        rows.append({
                            "class": ("NONE" if idx == classes else f"{domain}_{idx + 1}"),
                            "reference_n": 120 if idx == 0 else 0,
                            "predicted_n": 120 if idx == 0 else 0,
                            "precision": 0.5,
                            "recall": 0.5,
                            "f1": 0.5,
                        })
                    pd.DataFrame(rows).to_csv(
                        class_dir / f"{domain}_fulltext_centered_vs_{coder}_random_120_perclass_PRIVATE.csv",
                        index=False,
                    )

            for name, obj in (
                ("reviewer_four_e5_variant_dual_coder_metrics_v2.json", v2),
                ("reviewer_historical_tfidf_human_metrics_v1.json", lexical),
                ("reviewer_tfidf_vs_e5_paired_random_v1.json", paired),
            ):
                (audits / name).write_text(json.dumps(obj), encoding="utf-8")

            tables = workspace / "tables"
            model, _ = model_validation(workspace, tables)
            self.assertEqual(set(model["domain"]), {"SDG", "PDOT"})
            self.assertEqual(len(model), 40)

            table = pd.read_csv(tables / "Table_06_Classifier_Accuracy_and_MacroF1.csv")
            self.assertEqual(set(table["Domain"]), {"SDG", "PDOT"})

            figures = workspace / "figures"
            figures.mkdir()
            output = models(model, figures)
            self.assertTrue((figures / output["png"]).is_file())
            self.assertTrue((figures / output["svg"]).is_file())


if __name__ == "__main__":
    unittest.main()
