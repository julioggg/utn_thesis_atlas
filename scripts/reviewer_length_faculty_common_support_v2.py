#!/usr/bin/env python3
"""Common-support faculty standardization for fulltext class-shift trends.

A follow-up to reviewer_length_faculty_standardization.py. The first report
correctly returned null for whole-population direct standardization because
at least one faculty × length-quartile cell had <30 theses. This analysis
*does not fill in the missing group*, reduce the threshold or extrapolate.
It explicitly restricts the estimand to six original faculty/missingness
strata represented by >=30 documents in BOTH Q1 and Q4.

Weights are a fixed full-corpus faculty distribution, renormalized over
eligible groups. Both the crude and common-support estimates are reported;
their populations and denominators are different. Bootstrap intervals
describe resampling variability WITHIN the observed cells and do not
establish accuracy or causation. CPU only; row-level inputs remain private.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from audit_embedding_comparison import check_row_alignment
from reviewer_fulltext_drift_diagnostic import (
    N, DOMAINS, length_quartiles, load_verified_length_census
)
from reviewer_length_faculty_standardization import (
    GROUP_UNKNOWN, PRIMARY, strict_group_labels
)
from reviewer_legacy_alignment_replay import freeze_original_dicts
from reviewer_shared import FIVE_FACULTIES, sha256_file, write_public

GROUPS = [*FIVE_FACULTIES, GROUP_UNKNOWN]
OUTCOMES = (
    "original_target_share",
    "fulltext_target_share",
    "original_vs_fulltext_flip_share",
)


def calculate_group_outcomes(original, revised, target):
    return {
        "original_target_share": (original == target).astype(np.uint8),
        "fulltext_target_share": (revised == target).astype(np.uint8),
        "original_vs_fulltext_flip_share": (original != revised).astype(np.uint8),
    }


def standardize_common_support(faculty, lengths, original, revised, target,
                               min_n=30, boots=1000, seed=42):
    """Direct Q1/Q4 standardization on groups with common support.

    No imputation. Stratum weights use only full-corpus counts of the
    eligible original faculty groups, not Q1/Q4 exposure composition.
    Group names/numbers with <min_n cases never disclose their cell counts.
    """
    faculty = np.asarray(faculty, dtype=str)
    lengths = np.asarray(lengths, dtype=np.int64)
    original = np.asarray(original, dtype=str)
    revised = np.asarray(revised, dtype=str)
    if any(x.shape != (N,) for x in (faculty, lengths, original, revised)):
        raise ValueError("All original/fulltext arrays must have 7830 rows")
    if set(faculty) != set(GROUPS):
        raise ValueError("Must contain five verified faculties plus unresolved group")
    if np.any(lengths <= 0) or not isinstance(target, str) or not target.strip():
        raise ValueError("Invalid content lengths or target category")
    if min_n < 30 or boots < 100:
        raise ValueError("Keep minimum privacy cell at least 30 and bootstrap >=100")

    all_outcomes = calculate_group_outcomes(original, revised, target)
    quartiles = length_quartiles(lengths)
    end = {"Q1": quartiles["Q1"], "Q4": quartiles["Q4"]}
    included = []
    excluded = []
    cells = {}
    for group in GROUPS:
        cells[group] = {
            q: indices[faculty[indices] == group]
            for q, indices in end.items()
        }
        if all(len(cells[group][q]) >= min_n for q in end):
            included.append(group)
        else:
            excluded.append(group)
    if not included:
        raise ValueError("No faculties with adequate common support at both endpoints")

    eligible = np.isin(faculty, included)
    eligible_population_n = int(np.count_nonzero(eligible))
    eligible_population_share = eligible_population_n / N
    global_weights = {
        g: float(np.mean(faculty == g)) for g in GROUPS
    }
    weights = {
        g: float(np.sum(faculty == g) / eligible_population_n)
        for g in included
    }
    if not np.isclose(sum(weights.values()), 1):
        raise ValueError("Common-support population weights do not sum to 1")

    within = {}
    rng = np.random.default_rng(seed)
    # Keep bootstrap replicates private within this process; output only
    # aggregate 95% percentile intervals.
    sims = {
        k: {"Q1": np.zeros(boots), "Q4": np.zeros(boots)}
        for k in OUTCOMES
    }
    for group in included:
        within[group] = {}
        for quartile, indices in cells[group].items():
            entry = {"n": len(indices)}
            for key, values in all_outcomes.items():
                successes = int(values[indices].sum())
                rate = successes / len(indices)
                entry[key] = round(float(rate), 6)
                sims[key][quartile] += weights[group] * (
                    rng.binomial(len(indices), rate, size=boots) / len(indices)
                )
            within[group][quartile] = entry

    original_eligible = {
        q: indices[eligible[indices]] for q, indices in end.items()
    }
    standardized = {}
    for name in OUTCOMES:
        q1 = sum(weights[group] * within[group]["Q1"][name] for group in included)
        q4 = sum(weights[group] * within[group]["Q4"][name] for group in included)
        difference = sims[name]["Q4"] - sims[name]["Q1"]
        standardized[name] = {
            "q1_rate": round(float(q1), 6),
            "q4_rate": round(float(q4), 6),
            "q4_minus_q1_percentage_points": round(100 * (q4 - q1), 3),
            "within_cell_bootstrap_95pct_ci_pp": [
                round(100 * float(x), 3)
                for x in np.quantile(difference, [.025, .975])
            ],
        }

    crude_all = {}
    crude_eligible = {}
    for name, values in all_outcomes.items():
        for destination, indices_for_q in (
            (crude_all, end),
            (crude_eligible, original_eligible),
        ):
            q1 = float(np.mean(values[indices_for_q["Q1"]]))
            q4 = float(np.mean(values[indices_for_q["Q4"]]))
            destination[name] = {
                "q1_rate": round(q1, 6),
                "q4_rate": round(q4, 6),
                "q4_minus_q1_percentage_points": round(100 * (q4 - q1), 3),
            }

    return {
        "target_label": target,
        "common_support_requirement_min_n_per_group_in_each_endpoint": min_n,
        "groups_included": included,
        "groups_excluded_due_to_insufficient_q1_or_q4_support": excluded,
        "full_corpus_n": N,
        "eligible_full_corpus_n": eligible_population_n,
        "eligible_full_corpus_share": round(eligible_population_share, 6),
        "q1_n_full": len(end["Q1"]),
        "q4_n_full": len(end["Q4"]),
        "q1_n_eligible": len(original_eligible["Q1"]),
        "q4_n_eligible": len(original_eligible["Q4"]),
        "eligible_groups_original_full_corpus_weights": {
            k: round(v, 6) for k, v in weights.items()
        },
        "crude_all_faculties": crude_all,
        "crude_eligible_faculties_only": crude_eligible,
        "direct_standardization_on_common_support": standardized,
        "within_eligible_group_rates": within,
        "bootstrap_settings": {
            "replicates": boots, "seed": seed,
            "resampling": "independent binary nonparametric-equivalent cell bootstrap",
        },
        "warnings": [
            "Common-support estimate EXCLUDES all insufficiently represented groups (potentially Health); it is NOT a six-faculty population estimate.",
            "The original full-population standardized estimate remains undefined; no missing cells were imputed.",
            "All CI bounds quantify only within-cell resampling uncertainty, conditional on the observed corpus and faculty strata.",
            "The adjusted contrast is descriptive, not causal and not human model validity.",
            "Do not compare Q4 minus Q1 estimates across groups as if faculty and curriculum were randomized.",
            "Original faculty and missing metadata are retained; no category imputations.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--min-cell", type=int, default=30)
    parser.add_argument("--bootstrap", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--private-run", type=Path, default=Path(
        "data/revision_private/fulltext_e5_large_v1"
    ))
    parser.add_argument("--private-scores", type=Path, default=Path(
        "data/revision_private/reviewer_fulltext_reclassification/"
        "reclassification_all_7830_PRIVATE.npz"
    ))
    parser.add_argument("--source-inventory", type=Path, default=Path(
        "data/revision_private/descriptor_inventory/"
        "descriptor_source_candidates_PRIVATE.json"
    ))
    parser.add_argument("--reclassification-report", type=Path, default=Path(
        "docs/audits/reviewer_fulltext_reclassification_v1.json"
    ))
    parser.add_argument("--output", type=Path, default=Path(
        "docs/audits/reviewer_length_faculty_common_support_v2.json"
    ))
    a = parser.parse_args()
    if a.min_cell < 30 or a.bootstrap < 100:
        parser.error("min-cell must be at least 30 and bootstrap at least 100")
    workspace = Path(__file__).resolve().parent.parent
    root = a.project_root.expanduser().resolve()
    private_root = (workspace / "data").resolve()
    for p in (a.private_run, a.private_scores, a.source_inventory):
        if not p.expanduser().resolve().is_relative_to(private_root):
            raise ValueError("Private inputs must stay under ignored revision/data/")
    if a.output.expanduser().resolve().exists():
        raise FileExistsError("The common-support public report already exists; do not overwrite")

    rows, alignment = check_row_alignment(root)
    if rows != N or not all(alignment.values()):
        raise ValueError("Original row index not verified")
    manifest = json.loads(a.source_inventory.read_text(encoding="utf-8"))
    taxonomy, source_hash = freeze_original_dicts(manifest, root)
    preceding = json.loads(
        a.reclassification_report.read_text(encoding="utf-8")
    )
    if (
        preceding.get("status") !=
        "fulltext_and_centered_ods_pdot_needs_reclassification_exploratory_not_human_validated"
        or preceding.get("n_theses") != N
        or preceding.get("descriptor_source_sha256") != source_hash
    ):
        raise ValueError("Missing or mismatched fulltext source audit")

    lengths, _, blocks, fingerprint = load_verified_length_census(
        a.private_run.expanduser().resolve(), root
    )
    source = pd.read_parquet(
        root / "data/processed/07_alignment_pdot_ods_needs.parquet",
        columns=["handle_id", "faculty", "ods_top1", "pdot_top1", "need_top1"],
    )
    if (
        len(source) != N or source.handle_id.isna().any()
        or source.handle_id.duplicated().any()
    ):
        raise ValueError("Invalid source parquet row identities")
    groups = strict_group_labels(source["faculty"])
    domains = {}
    with np.load(a.private_scores, allow_pickle=False) as saved:
        for domain in DOMAINS:
            names = list(taxonomy[domain])
            label_key = f"{domain}_fulltext_raw_top3_indices"
            if label_key not in saved:
                raise ValueError(f"Private reclassification is missing {label_key}")
            ids = np.asarray(saved[label_key])
            if ids.shape != (N,3) or np.any(ids < 0) or np.any(ids >= len(names)):
                raise ValueError("Private predicted label indices invalid")
            old = source[f"{domain}_top1"].astype(str).to_numpy()
            if not set(old).issubset(set(names)):
                raise ValueError("Original labels not found in frozen source taxonomy")
            full = np.asarray(names)[ids[:,0]]
            if int(np.count_nonzero(old != full)) != (
                preceding["domains"][domain]["representations"]["fulltext_raw"][
                    "top1_changed_against_original_n"
                ]
            ):
                raise ValueError("Label flip count inconsistent with earlier audit")
            domains[domain] = standardize_common_support(
                groups, lengths, old, full, PRIMARY[domain],
                min_n=a.min_cell, boots=a.bootstrap, seed=a.seed + DOMAINS.index(domain)
            )
    report = {
        "schema_version": 2,
        "status": "length_faculty_common_support_standardization_unvalidated",
        "population_rows": N,
        "source_taxonomy_sha256": source_hash,
        "reclassification_report_sha256": sha256_file(a.reclassification_report),
        "private_prediction_matrix_sha256": sha256_file(a.private_scores),
        "fulltext_checkpoint_blocks": blocks,
        "fulltext_checkpoint_fingerprint": fingerprint,
        "original_row_alignment_verified": alignment,
        "taxonomies": domains,
        "expert_ground_truth_measured": False,
        "not_an_all_faculties_adjusted_estimate": True,
        "note": (
            "Fixed faculty weights are renormalized among groups having >=30 "
            "observations in BOTH endpoint quartiles; full-population standardization "
            "remains undefined; no extrapolation or imputation."
        ),
    }
    dest = write_public(report, a.output, workspace)
    print("Common-support standardization:", dest)
    for domain, item in domains.items():
        print(domain, "| eligible groups:",len(item["groups_included"]),
              "| covered population:", item["eligible_full_corpus_n"],
              "| excluded:", item["groups_excluded_due_to_insufficient_q1_or_q4_support"])
        for key in ("fulltext_target_share", "original_vs_fulltext_flip_share"):
            obj = item["direct_standardization_on_common_support"][key]
            print(" ", key, "Q4-Q1, pp:", obj["q4_minus_q1_percentage_points"],
                  "95% within-cell bootstrap:", obj["within_cell_bootstrap_95pct_ci_pp"])
    print("Original 6-group full population adjusted estimate remains undefined.")


if __name__ == "__main__":
    main()
