#!/usr/bin/env python3
"""CPU-only full-corpus ODS/PDOT/NEEDS reclassification sensitivity.

Requires completed 7830-thesis E5 fulltext and near-exact replay of historical
descriptor scores. Reuses the 33 original-source E5 descriptor vectors, no
model inference or repeated PDF processing. Compares original-vs-fulltext and
raw-vs-mean-centered labels, top-3 category sets and score ambiguities.

IMPORTANT: All outputs are UNVALIDATED semantic affinities, not expertise
labels, direct SDG achievement or policy impact. Row-level scores and
predictions remain under ignored CEDIA revision/data.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from audit_embedding_comparison import check_row_alignment
from reviewer_compare_fulltext_legacy import check_fulltext_report, normalize_checked
from reviewer_fulltext_anisotropy import center_and_normalize
from reviewer_legacy_alignment_replay import freeze_original_dicts, source_matches_archived_labels
from reviewer_shared import private_output, sha256_file, summary, write_public

N = 7830
D = 1024
DOMAINS = ("pdot", "ods", "need")
VARIANTS = ("legacy_raw", "legacy_centered", "fulltext_raw", "fulltext_centered")


def replay_gate(report):
    """Only strong historical numerical reproduction permits reclassification."""
    if report.get("status") != "historical_original_alignment_replayed_candidate":
        raise ValueError("Historical replay must have completed")
    if report.get("n_corpus_rows") != N or report.get("n_original_descriptor_sentences") != 33:
        raise ValueError("Historical replay has different census/taxonomy size")
    if report.get("descriptor_encoding", {}).get("prefix") != "passage: ":
        raise ValueError("Historical replay did not use observed source prefix")
    if report.get("model") != "intfloat/multilingual-e5-large":
        raise ValueError("Historical model differs")
    details = {}
    for domain in DOMAINS:
        audit = report["domains"][domain]
        if audit["n"] != N or abs(audit["unordered_top3_set_agreement"] - 1) > 1e-9:
            raise ValueError(f"Historical top-3 replay not verified for {domain}")
        rank_mismatches = [
            audit["ranking"][str(rank)]["mismatch_count"]
            for rank in (1, 2, 3)
        ]
        for rank in (1, 2, 3):
            if audit["ranking"][str(rank)]["absolute_score_error_q99"] > 1e-5:
                raise ValueError(f"Historical score reconstruction differs: {domain}, rank {rank}")
        allowed = (0, 0, 0) if domain in ("ods", "pdot") else (1, 2, 1)
        if any(actual > maximum for actual, maximum in zip(rank_mismatches, allowed)):
            raise ValueError(f"Unexpected historical ranking differences in {domain}")
        details[domain] = {
            "replay_rank_1_to_3_mismatches": rank_mismatches,
            "historical_top3_set_agreement": audit["unordered_top3_set_agreement"],
            "highest_reported_p99_absolute_score_error": max(
                audit["ranking"][str(r)]["absolute_score_error_q99"]
                for r in (1, 2, 3)
            ),
        }
    return details


def cosine_scores(x, descriptor_vectors):
    if x.ndim != 2 or descriptor_vectors.ndim != 2:
        raise ValueError("Expected two 2D arrays")
    if x.shape[1] != descriptor_vectors.shape[1]:
        raise ValueError("Embedding width mismatch")
    z = np.asarray(x @ descriptor_vectors.T, dtype=np.float32)
    if not np.isfinite(z).all() or z.max() > 1.001 or z.min() < -1.001:
        raise ValueError("Invalid cosine scores")
    return z


def top3(scores):
    if scores.ndim != 2 or scores.shape[1] < 3:
        raise ValueError("Expected at least 3 categories")
    ordered = np.argsort(-scores, axis=1, kind="stable")
    best = np.take_along_axis(scores, ordered[:, :3], axis=1)
    return ordered[:, :3], best


def domain_summary(scores, names, legacy_labels, legacy_top3):
    """Summary only: no individual thesis IDs, indexes or raw scores."""
    if scores.shape != (N, len(names)):
        raise ValueError("Wrong score shape")
    indices, ordered_scores = top3(scores)
    categories = np.asarray(names, dtype=str)
    first = categories[indices[:, 0]]
    top_three_names = categories[indices]
    margin = ordered_scores[:, 0] - ordered_scores[:, 1]
    if len(legacy_labels) != N or legacy_top3.shape != (N, 3):
        raise ValueError("Mismatched historical comparison")
    return {
        "population": N,
        "top1_category_counts_candidate_unvalidated": {
            category: int(np.count_nonzero(first == category))
            for category in names
        },
        "top1_agreement_with_original_forced_assignment_not_accuracy":
            round(float(np.mean(first == legacy_labels)), 6),
        "top1_changed_against_original_n": int(np.count_nonzero(first != legacy_labels)),
        "unordered_top3_set_overlap_with_original_mean": round(float(np.mean([
            len(set(a) & set(b)) / 3
            for a, b in zip(top_three_names, legacy_top3)
        ])), 6),
        "identical_top3_set_against_original_n": int(sum(
            set(a) == set(b) for a, b in zip(top_three_names, legacy_top3)
        )),
        "best_cosine_score": summary(ordered_scores[:, 0]),
        "top1_minus_top2_margin": summary(margin),
        "uncalibrated_margin_le_counts": {
            f"{threshold:.3f}": int(np.count_nonzero(margin <= threshold))
            for threshold in (0.002, 0.005, 0.01, 0.02)
        },
        "warning": (
            "Top-1/3 comparisons refer only to historical forced predictions, "
            "not independent expert classification or impact."
        ),
    }


def numerical_replay_ties(archive, domains, replay_npz):
    """Privately verify the few mismatched historical ranks: no thesis IDs."""
    outcome = {}
    for domain in DOMAINS:
        names = list(domains[domain])
        scores = np.asarray(replay_npz[f"{domain}_legacy_scores"], dtype=np.float32)
        if scores.shape != (N, len(names)) or not np.isfinite(scores).all():
            raise ValueError(f"Historical replay private scores invalid: {domain}")
        ordered, ordered_scores = top3(scores)
        labels = np.asarray(names, dtype=str)
        differences = {}
        for rank in (1, 2, 3):
            legacy = archive[f"{domain}_top{rank}"].astype(str).to_numpy()
            changed = labels[ordered[:, rank - 1]] != legacy
            differences[str(rank)] = {
                "mismatches": int(changed.sum()),
                "max_replay_top1_top2_margin_among_mismatches": (
                    round(float((ordered_scores[changed, 0] -
                                 ordered_scores[changed, 1]).max()), 9)
                    if changed.any() else None
                ),
            }
        outcome[domain] = differences
    return outcome


def analyze(args):
    workspace = Path(__file__).resolve().parent.parent
    root = args.project_root.expanduser().resolve()
    output_root = private_output(args.private_dir, workspace)
    target = output_root / "reclassification_all_7830_PRIVATE.npz"
    if target.exists():
        raise FileExistsError("Existing private reclassification found; do not overwrite")
    if args.output.expanduser().resolve().exists():
        raise FileExistsError("Aggregate reclassification report exists; do not overwrite")

    inventory_path = (
        workspace / "data/revision_private/descriptor_inventory/"
        "descriptor_source_candidates_PRIVATE.json"
    )
    replay_private = args.replay_private.expanduser().resolve()
    fulltext_private = args.fulltext.expanduser().resolve()
    for name, path in (("Replay", replay_private), ("Fulltext", fulltext_private)):
        if not path.is_relative_to((workspace / "data").resolve()):
            raise ValueError(f"{name} private vectors must stay under revision/data")
    with inventory_path.open(encoding="utf-8") as stream:
        inventory = json.load(stream)
    taxonomies, source_hash = freeze_original_dicts(inventory, root)
    replay = json.loads(args.replay_report.expanduser().resolve().read_text(encoding="utf-8"))
    replay_summary = replay_gate(replay)
    fulltext_provenance = check_fulltext_report(args.fulltext_report.expanduser().resolve())
    if replay["source_file_sha256"] != source_hash or (
        replay["source_inventory_sha256"] != sha256_file(inventory_path)
    ):
        raise ValueError("Original source fingerprint mismatch")
    if replay["reference_fulltext_model_revision"] != fulltext_provenance["model_revision_from_cache"]:
        raise ValueError("Descriptor E5 model revision differs from fulltext model")
    if replay["model"] != fulltext_provenance["model"]:
        raise ValueError("Model identity differs")

    n, alignment = check_row_alignment(root)
    if n != N or not all(alignment.values()):
        raise ValueError("Original row provenance cannot be verified")
    columns = ["handle_id"]
    for domain in DOMAINS:
        columns.extend(f"{domain}_top{rank}" for rank in (1, 2, 3))
    archive = pd.read_parquet(
        root / "data/processed/07_alignment_pdot_ods_needs.parquet",
        columns=columns,
    )
    if len(archive) != N or archive.handle_id.isna().any() or archive.handle_id.duplicated().any():
        raise ValueError("Archive row identifiers missing or duplicated")
    source_matches = {domain: list(taxonomies[domain]) for domain in DOMAINS}
    for domain in DOMAINS:
        for r in (1, 2, 3):
            if not set(archive[f"{domain}_top{r}"].astype(str)).issubset(
                set(source_matches[domain])
            ):
                raise ValueError(f"Archived {domain} does not match source taxonomy")

    old, _ = normalize_checked(
        np.load(root / "data/processed/05_embeddings.npy",
                mmap_mode="r", allow_pickle=False),
        "Legacy embeddings"
    )
    new, _ = normalize_checked(
        np.load(fulltext_private, mmap_mode="r", allow_pickle=False),
        "Fulltext embeddings"
    )
    if old.shape != (N, D) or new.shape != (N, D):
        raise ValueError("Incorrect corpus vector shape")

    old_centered, _, _ = center_and_normalize(old)
    new_centered, _, _ = center_and_normalize(new)
    centers = {
        "legacy": old.mean(axis=0, dtype=np.float64).astype(np.float32),
        "fulltext": new.mean(axis=0, dtype=np.float64).astype(np.float32),
    }
    docs = {
        "legacy_raw": old, "legacy_centered": old_centered,
        "fulltext_raw": new, "fulltext_centered": new_centered,
    }

    per_domain = {}
    stored = {}
    with np.load(replay_private, allow_pickle=False) as frozen:
        keys = set(frozen.files)
        for domain in DOMAINS:
            if not {f"{domain}_descriptor_embeddings", f"{domain}_legacy_scores"}.issubset(keys):
                raise ValueError(f"Missing frozen legacy {domain} arrays")
        tie_diagnostics = numerical_replay_ties(archive, taxonomies, frozen)
        for domain in DOMAINS:
            names = source_matches[domain]
            descriptors = np.asarray(
                frozen[f"{domain}_descriptor_embeddings"], dtype=np.float32
            )
            if descriptors.shape != (len(names), D) or not np.isfinite(descriptors).all():
                raise ValueError(f"Frozen {domain} descriptors invalid")
            desc_norm = np.linalg.norm(descriptors, axis=1)
            if np.max(np.abs(desc_norm - 1)) > 1e-3:
                raise ValueError("Descriptor embeddings are not normalized")

            replay_score = np.asarray(
                frozen[f"{domain}_legacy_scores"], dtype=np.float32
            )
            recomputed_old = cosine_scores(old, descriptors)
            max_diff = float(np.max(np.abs(replay_score - recomputed_old)))
            if max_diff > 1e-5:
                raise ValueError(f"{domain} legacy frozen score mismatch {max_diff}")

            variants = {
                "legacy_raw": recomputed_old,
                "fulltext_raw": cosine_scores(new, descriptors),
                "legacy_centered": cosine_scores(
                    old_centered,
                    _normalize_residuals(descriptors, centers["legacy"])
                ),
                "fulltext_centered": cosine_scores(
                    new_centered,
                    _normalize_residuals(descriptors, centers["fulltext"])
                ),
            }
            archived_labels = archive[f"{domain}_top1"].astype(str).to_numpy()
            legacy_top3 = archive[
                [f"{domain}_top{rank}" for rank in (1,2,3)]
            ].astype(str).to_numpy()
            per_domain[domain] = {
                "number_of_categories": len(names),
                "source_dictionary": {"pdot":"PDOT","ods":"ODS","need":"NEEDS"}[domain],
                "baseline_reproduction": replay_summary[domain],
                "numerical_rank_discrepancy_audit": tie_diagnostics[domain],
                "legacy_score_replay_max_absolute_error": round(max_diff, 9),
                "representations": {
                    key: domain_summary(variants[key], names, archived_labels, legacy_top3)
                    for key in VARIANTS
                },
            }
            # Full cross-variant comparisons, not just comparison to historical top1.
            names_array = np.asarray(names)
            raw_top = names_array[np.argmax(variants["fulltext_raw"], axis=1)]
            center_top = names_array[np.argmax(variants["fulltext_centered"], axis=1)]
            per_domain[domain]["fulltext_raw_vs_fulltext_centered_top1_changed_n"] = int(
                np.count_nonzero(raw_top != center_top)
            )
            per_domain[domain]["fulltext_raw_vs_fulltext_centered_top1_agreement"] = round(
                float(np.mean(raw_top == center_top)), 6
            )
            for variant in VARIANTS:
                stored[f"{domain}_{variant}_scores"] = variants[variant].astype(np.float32)
                stored[f"{domain}_{variant}_top3_indices"] = top3(variants[variant])[0].astype(np.int16)

    # Nothing original is ever overwritten. Neither matrix nor archive labels
    # are published in aggregate audit output.
    np.savez_compressed(target, **stored)
    result = {
        "schema_version": 1,
        "status": "fulltext_and_centered_ods_pdot_needs_reclassification_exploratory_not_human_validated",
        "n_theses": N,
        "n_dimensions": D,
        "classifier": "original_source_E5_descriptor_cosine",
        "descriptor_source": "utn_atlas_pipeline.py, exact PDOT / ODS / NEEDS source mappings",
        "descriptor_source_sha256": source_hash,
        "frozen_replay_report_sha256": sha256_file(args.replay_report.expanduser().resolve()),
        "frozen_descriptor_vectors_sha256": sha256_file(replay_private),
        "fulltext_model_revision": fulltext_provenance["model_revision_from_cache"],
        "source_alignment_verified": alignment,
        "variants": list(VARIANTS),
        "mean_centering": (
            "For each embedding variant, subtract the mean of all 7830 "
            "document vectors from BOTH thesis and descriptor vectors, "
            "then L2-normalize before cosine. No calibration performed."
        ),
        "domains": per_domain,
        "official_pdot_policy_document_mapping_verified": False,
        "ten_needs_policy_origin_verified": False,
        "human_labels_available": False,
        "precision_recall_f1_measured": False,
        "important_limitations": [
            "All four versions use source-derived legacy descriptors; none is validated against independent human gold labels.",
            "Counts reflect forced, unsupervised top1 assignments, not measured SDG contribution or territorial impact.",
            "Mean-centered similarity margins and raw similarity margins do not share a calibrated numerical scale.",
            "New documents use full text with chunk pooling and FP16 inference, unlike historical single-input embeddings.",
            "A single legacy NEEDS top1 mismatch was observed in numerical replay and audited for top-score ties.",
            "No row-level thesis identifiers, author or advisor data, prediction scores or vectors are in this report.",
        ],
    }
    path = write_public(result, args.output, workspace)
    print("Complete 7830-thesis ODS/PDOT/NEEDS candidate reclassification:", path)
    for domain in DOMAINS:
        item = per_domain[domain]
        print(
            domain,
            "legacy vs new raw label agreement:",
            item["representations"]["fulltext_raw"][
                "top1_agreement_with_original_forced_assignment_not_accuracy"
            ],
            "fulltext raw vs centered top1 agreement:",
            item["fulltext_raw_vs_fulltext_centered_top1_agreement"],
        )
    print("Only AGGREGATE report is public-candidate; all row scores remain in ignored data")


def _normalize_residuals(descriptor_vectors, mean):
    residual = descriptor_vectors.astype(np.float64) - mean.astype(np.float64)
    length = np.linalg.norm(residual, axis=1)
    if np.any(length < 1e-8):
        raise ValueError("Descriptor collapsed when mean-centered")
    return (residual / length[:, None]).astype(np.float32)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root", type=Path, required=True)
    p.add_argument("--fulltext", type=Path, default=Path(
        "data/revision_private/fulltext_e5_large_v1/fulltext_e5_large_7830_PRIVATE.npy"))
    p.add_argument("--fulltext-report", type=Path, default=Path(
        "docs/audits/fulltext_e5_large_full_corpus_v1.json"))
    p.add_argument("--replay-report", type=Path, default=Path(
        "docs/audits/reviewer_legacy_alignment_replay.json"))
    p.add_argument("--replay-private", type=Path, default=Path(
        "data/revision_private/reviewer_alignment_replay/"
        "historical_replay_descriptor_vectors_and_scores_PRIVATE.npz"))
    p.add_argument("--private-dir", type=Path, default=Path(
        "data/revision_private/reviewer_fulltext_reclassification"))
    p.add_argument("--output", type=Path, default=Path(
        "docs/audits/reviewer_fulltext_reclassification_v1.json"))
    args = p.parse_args()
    analyze(args)


if __name__ == "__main__":
    main()
