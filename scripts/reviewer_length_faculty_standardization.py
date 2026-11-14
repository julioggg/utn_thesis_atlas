#!/usr/bin/env python3
"""Faculty-standardized length sensitivity for legacy/fulltext ODS and PDOT labels.

Read-only, CPU-only, aggregate-only. Tests whether apparent fulltext PDOT
dominance and ODS/needs top1 drift across document-length quartiles persist
after standardizing to the fixed distribution of original verified faculties
plus an explicit unknown/misc group.

All results remain ASSOCIATIONS; do not claim causal bias, higher accuracy,
impact or statistical independence. No model, PDFs or original labels modified.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from audit_embedding_comparison import check_row_alignment
from reviewer_fulltext_drift_diagnostic import (
    N, DOMAINS, length_quartiles, load_verified_length_census,
)
from reviewer_fulltext_reclassification import cosine_scores
from reviewer_legacy_alignment_replay import freeze_original_dicts
from reviewer_shared import FIVE_FACULTIES, sha256_file, write_public

GROUP_UNKNOWN = "Sin facultad verificada (incluye miscelánea)"
PRIMARY = {
    "ods": "ODS 4 Educación de calidad",
    "pdot": "Asentamientos Humanos Movilidad Energía Conectividad",
    "need": "Salud nutrición grupos prioritarios",
}
MIN_CELL = 30


def strict_group_labels(faculties):
    """Original verified faculties ONLY; no reassigning data by career."""
    value = pd.Series(faculties, dtype="string").str.strip()
    return value.where(value.isin(FIVE_FACULTIES), GROUP_UNKNOWN).astype(str).to_numpy()


def contrast_by_quartiles(faculty, token_lengths, original, revised,
                         target_label, min_cell=MIN_CELL):
    """Calculate crude and direct faculty-standardized rates for each Q.

    Weighting uses the *same* global faculty distribution in all quartiles;
    if any cell smaller than the privacy threshold, omit a standardized rate.
    """
    faculty = np.asarray(faculty, dtype=str)
    token_lengths = np.asarray(token_lengths, dtype=np.int64)
    original = np.asarray(original, dtype=str)
    revised = np.asarray(revised, dtype=str)
    if any(x.shape != (N,) for x in (faculty, token_lengths, original, revised)):
        raise ValueError("All inputs must be aligned to 7830 thesis rows")
    if not target_label or np.any(token_lengths <= 0):
        raise ValueError("Invalid target category or document lengths")
    quartiles = length_quartiles(token_lengths)
    groups = [*FIVE_FACULTIES, GROUP_UNKNOWN]
    if set(faculty) != set(groups):
        raise ValueError("Expected five original faculty names plus unresolved group")
    weights = {f: float(np.mean(faculty == f)) for f in groups}
    if not np.isclose(sum(weights.values()), 1):
        raise ValueError("Original faculty weights do not sum to one")

    by_quartile = []
    by_group = {f: {} for f in groups}
    for q, indices in quartiles.items():
        head = {
            "quartile": q,
            "n": len(indices),
            "median_content_tokens": int(np.median(token_lengths[indices])),
            "crude": {
                "original_target_label_share":
                    round(float(np.mean(original[indices] == target_label)), 6),
                "fulltext_target_label_share":
                    round(float(np.mean(revised[indices] == target_label)), 6),
                "original_to_fulltext_changed_share":
                    round(float(np.mean(original[indices] != revised[indices])), 6),
            },
            "standardized_on_original_faculty_mix": None,
            "suppressed_faculty_quartile_cells": 0,
        }
        local_rates = {}
        for group in groups:
            subset = indices[faculty[indices] == group]
            if len(subset) < min_cell:
                head["suppressed_faculty_quartile_cells"] += 1
                by_group[group][q] = None
                continue
            measures = {
                "n": len(subset),
                "original_target_label_share":
                    round(float(np.mean(original[subset] == target_label)), 6),
                "fulltext_target_label_share":
                    round(float(np.mean(revised[subset] == target_label)), 6),
                "original_to_fulltext_changed_share":
                    round(float(np.mean(original[subset] != revised[subset])), 6),
            }
            by_group[group][q] = measures
            local_rates[group] = measures
        if len(local_rates) == len(groups):
            head["standardized_on_original_faculty_mix"] = {
                label: round(
                    float(sum(weights[group] * local_rates[group][label]
                              for group in groups)), 6)
                for label in (
                    "original_target_label_share",
                    "fulltext_target_label_share",
                    "original_to_fulltext_changed_share",
                )
            }
        by_quartile.append(head)

    def endpoint_rates(field, layer):
        first, last = by_quartile[0], by_quartile[-1]
        if layer == "crude":
            return first[layer][field], last[layer][field]
        if first[layer] is None or last[layer] is None:
            return None, None
        return first[layer][field], last[layer][field]

    diffs = {}
    for layer in ("crude", "standardized_on_original_faculty_mix"):
        stats = {}
        for field in (
            "original_target_label_share",
            "fulltext_target_label_share",
            "original_to_fulltext_changed_share",
        ):
            q1, q4 = endpoint_rates(field, layer)
            stats[field + "_q4_minus_q1_percentage_points"] = (
                round(100 * (q4 - q1), 3)
                if q1 is not None and q4 is not None else None
            )
        diffs[layer] = stats
    rows = []
    for group in groups:
        q1 = by_group[group]["Q1"]
        q4 = by_group[group]["Q4"]
        rows.append({
            "faculty_group": group,
            "population_group_n": int(np.count_nonzero(faculty == group)),
            "q1_n": q1["n"] if q1 is not None else None,
            "q4_n": q4["n"] if q4 is not None else None,
            "q1_fulltext_target_label_share":
                q1["fulltext_target_label_share"] if q1 else None,
            "q4_fulltext_target_label_share":
                q4["fulltext_target_label_share"] if q4 else None,
            "q4_minus_q1_target_share_percentage_points":
                round(100 * (q4["fulltext_target_label_share"] -
                             q1["fulltext_target_label_share"]), 3)
                if q1 and q4 else None,
            "q1_original_to_fulltext_changed_share":
                q1["original_to_fulltext_changed_share"] if q1 else None,
            "q4_original_to_fulltext_changed_share":
                q4["original_to_fulltext_changed_share"] if q4 else None,
        })

    return {
        "target_label": target_label,
        "faculty_groups": len(groups),
        "faculty_group_weights_full_corpus": {
            f: round(weights[f], 6) for f in groups
        },
        "privacy_suppress_cells_with_n_below": min_cell,
        "quartile_summaries": by_quartile,
        "endpoint_q4_minus_q1": diffs,
        "by_original_verified_faculty_or_unknown": rows,
        "interpretation": [
            "Crude trends can reflect differences in faculty composition across length quartiles.",
            "Direct standardization holds original verified-faculty composition constant across quartiles.",
            "This adjustment does NOT account for within-faculty programs, publication year, thesis subject or text extraction quality.",
            "The unresolved faculty group is preserved, not imputed; small cells are suppressed.",
            "Longer fulltext is associated with different labels, but that does NOT identify a causal mechanism.",
            "These are UNSUPERVISED category assignments, never human accuracy or policy impact.",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root", type=Path, required=True)
    p.add_argument("--private-run", type=Path, default=Path(
        "data/revision_private/fulltext_e5_large_v1"
    ))
    p.add_argument("--private-scores", type=Path, default=Path(
        "data/revision_private/reviewer_fulltext_reclassification/"
        "reclassification_all_7830_PRIVATE.npz"
    ))
    p.add_argument("--source-inventory", type=Path, default=Path(
        "data/revision_private/descriptor_inventory/"
        "descriptor_source_candidates_PRIVATE.json"
    ))
    p.add_argument("--reclassification-report", type=Path, default=Path(
        "docs/audits/reviewer_fulltext_reclassification_v1.json"
    ))
    p.add_argument("--output", type=Path, default=Path(
        "docs/audits/reviewer_fulltext_length_faculty_standardization.json"
    ))
    args = p.parse_args()
    workspace = Path(__file__).resolve().parent.parent
    data_root = (workspace / "data").resolve()
    for item in (args.private_run, args.private_scores, args.source_inventory):
        if not item.expanduser().resolve().is_relative_to(data_root):
            raise ValueError("Source matrices and inventory must remain in private data")
    if args.output.expanduser().resolve().exists():
        raise FileExistsError("Output exists: do not overwrite an existing audit")

    root = args.project_root.expanduser().resolve()
    census, alignment = check_row_alignment(root)
    if census != N or not all(alignment.values()):
        raise ValueError("Original original 04/05/06/07 row ordering not verified")

    manifest = json.loads(args.source_inventory.read_text(encoding="utf-8"))
    dictionaries, sha = freeze_original_dicts(manifest, root)
    previous = json.loads(args.reclassification_report.read_text(encoding="utf-8"))
    if (
        previous.get("n_theses") != N or
        previous.get("status") != "fulltext_and_centered_ods_pdot_needs_reclassification_exploratory_not_human_validated" or
        previous.get("descriptor_source_sha256") != sha
    ):
        raise ValueError("Reclassification provenance does not match original descriptors")

    token_lengths, _, checkpoint_blocks, manifest_fingerprint = load_verified_length_census(
        args.private_run, root
    )
    source = pd.read_parquet(
        root / "data/processed/07_alignment_pdot_ods_needs.parquet",
        columns=["handle_id", "faculty", "year",
                 "ods_top1", "pdot_top1", "need_top1"],
    )
    if (
        len(source) != N or source["handle_id"].isna().any() or
        source["handle_id"].duplicated().any()
    ):
        raise ValueError("Original source IDs invalid")
    faculty = strict_group_labels(source["faculty"])
    report = {}
    with np.load(args.private_scores, allow_pickle=False) as saved:
        for domain in DOMAINS:
            descriptor_names = list(dictionaries[domain])
            key = f"{domain}_fulltext_raw_top3_indices"
            if key not in saved:
                raise ValueError(f"Private reclassification lacks {key}")
            categories = np.asarray(saved[key])[:, 0]
            if categories.shape != (N,) or np.any(categories < 0) or np.any(categories >= len(descriptor_names)):
                raise ValueError("Invalid private fulltext ranks")
            labels = np.asarray(descriptor_names)[categories]
            original = source[f"{domain}_top1"].astype(str).to_numpy()
            if not set(original).issubset(set(descriptor_names)):
                raise ValueError("Original labels do not belong to source descriptor taxonomy")
            item = contrast_by_quartiles(
                faculty, token_lengths, original, labels, PRIMARY[domain]
            )
            known_flips = previous["domains"][domain]["representations"]["fulltext_raw"]["top1_changed_against_original_n"]
            if int(np.sum(original != labels)) != known_flips:
                raise ValueError("Fulltext label flip count does not match earlier audit")
            report[domain] = item
    output = {
        "schema_version": 1,
        "status": "descriptive_length_faculty_standardization_unvalidated",
        "n_population": N,
        "source_alignment": alignment,
        "source_descriptor_sha256": sha,
        "fulltext_checkpoint_manifest_fingerprint": manifest_fingerprint,
        "checkpoint_blocks_validated": checkpoint_blocks,
        "reclassification_report_sha256": sha256_file(args.reclassification_report),
        "taxonomies": report,
        "human_ground_truth_evaluated": False,
        "study_conclusion_is_causal": False,
        "note": (
            "Fixed-faculty direct standardization is descriptive only, not proof "
            "that fulltext embeddings or class descriptions are more accurate. "
            "Individual records and source texts remain private in CEDIA."
        ),
    }
    target = write_public(output, args.output, workspace)
    print("Faculty-adjusted length sensitivity:", target)
    for domain, entry in report.items():
        diff = entry["endpoint_q4_minus_q1"]
        print(domain, "Q4-Q1 dominant label (crude pp):",
              diff["crude"]["fulltext_target_label_share_q4_minus_q1_percentage_points"],
              "standardized pp:",
              diff["standardized_on_original_faculty_mix"][
                  "fulltext_target_label_share_q4_minus_q1_percentage_points"
              ])
    print("CPU-only, aggregate-only; no original corpus files or blinded sheets modified.")


if __name__ == "__main__":
    main()
