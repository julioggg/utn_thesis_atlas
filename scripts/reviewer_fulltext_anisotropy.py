#!/usr/bin/env python3
"""Atlas-wide E5 anisotropy diagnostic: centered vs original-space geometry.

CPU-only, privacy-safe, read-only. Loads aligned private matrices of all
7,830 original/whole-text thesis vectors. Subtracts the entire-corpus
mean and L2-normalizes each vector, without recalculating neural embeddings.
Reports aggregate geometry and nearest-neighbor stability only.

IMPORTANT: Mean-centering is a diagnostic and candidate alternative;
it is NOT automatically an improved SDG/PDOT classifier. Any query
descriptor must undergo a compatible transformation, and thresholds
must be calibrated exclusively against independent human ground truth.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from audit_embedding_comparison import check_row_alignment
from reviewer_compare_fulltext_legacy import (
    N, D, check_fulltext_report, normalize_checked,
    sample_distinct_pairs, paired_cosines, sample_neighbors
)
from reviewer_shared import summary, write_public


def center_and_normalize(vectors):
    """Mean-center using the complete population, then row-wise unit norm."""
    x = np.asarray(vectors, dtype=np.float32)
    if x.ndim != 2 or not np.isfinite(x).all() or len(x) < 2:
        raise ValueError("Expected finite 2D input with at least two documents")
    mu = x.mean(axis=0, dtype=np.float64)
    raw_residual = x.astype(np.float64) - mu
    norms = np.linalg.norm(raw_residual, axis=1)
    if (norms <= 1e-8).any():
        raise ValueError("Mean centering created a zero residual vector")
    z = (raw_residual / norms[:, None]).astype(np.float32)
    return z, summary(norms), float(np.linalg.norm(mu))


def exact_off_diagonal_mean_cosine(unit_vectors):
    """Identity for unit vectors: (N * ||mean||^2 - 1)/(N - 1)."""
    x = np.asarray(unit_vectors, dtype=np.float64)
    if len(x) < 2:
        raise ValueError("At least two vectors required")
    if np.max(np.abs(np.linalg.norm(x, axis=1) - 1)) > 1e-4:
        raise ValueError("All vectors must be unit length")
    mu = x.mean(axis=0)
    return float((len(x) * (mu @ mu) - 1)/(len(x) - 1))


def same_anchor_knn_overlap(a, b, anchors, k):
    if len(a) != len(b):
        raise ValueError("Arrays have mismatched document counts")
    ix_a = sample_neighbors(a, anchors, k)
    ix_b = sample_neighbors(b, anchors, k)
    return summary([len(set(u) & set(v))/k for u, v in zip(ix_a, ix_b)])


def paired_distribution(emb, i, j):
    scores = np.clip(paired_cosines(emb, i, j), -1, 1)
    return {
        "sampled_cross_thesis_cosine": summary(scores),
        "n_sampled_pairs_at_or_above_0p99": int(np.count_nonzero(scores >= .99)),
        "n_sampled_pairs_at_or_above_0p9999": int(np.count_nonzero(scores >= .9999)),
        "n_sampled_pairs_at_or_above_0p999999": int(np.count_nonzero(scores >= .999999)),
        "exact_mean_cosine_of_all_distinct_unordered_pairs":
            round(exact_off_diagonal_mean_cosine(emb), 6),
    }, scores


def diagnose_pair(old, new, pair_count=100000, anchors=256, k=10, seed=42):
    if old.shape != new.shape:
        raise ValueError("Original and fulltext matrices must have same shape")
    rng = np.random.default_rng(seed)
    i, j = sample_distinct_pairs(len(old), pair_count, rng)
    anchor_ids = rng.choice(len(old), size=min(anchors, len(old)), replace=False)
    centered_old, residual_old, original_mu_norm = center_and_normalize(old)
    centered_new, residual_new, full_mu_norm = center_and_normalize(new)

    raw_a, raw_old_scores = paired_distribution(old, i, j)
    raw_b, raw_new_scores = paired_distribution(new, i, j)
    centered_a, center_old_scores = paired_distribution(centered_old, i, j)
    centered_b, center_new_scores = paired_distribution(centered_new, i, j)

    def spearman(left, right):
        r = pd.Series(left).rank(method="average").corr(
            pd.Series(right).rank(method="average"), method="pearson"
        )
        return round(float(r), 6) if np.isfinite(r) else None

    return {
        "n_documents": len(old),
        "sampled_distinct_pairs_with_replacement": pair_count,
        "anchor_documents": len(anchor_ids),
        "top_k_neighbors": k,
        "seed": seed,
        "original_raw_mean_direction_norm": round(original_mu_norm, 6),
        "fulltext_raw_mean_direction_norm": round(full_mu_norm, 6),
        "original_centered_residual_norms": residual_old,
        "fulltext_centered_residual_norms": residual_new,
        "pairwise_cosine_distributions": {
            "original_raw": raw_a,
            "fulltext_raw": raw_b,
            "original_mean_centered": centered_a,
            "fulltext_mean_centered": centered_b,
        },
        "rank_spearman": {
            "raw_original_vs_raw_fulltext": spearman(raw_old_scores, raw_new_scores),
            "centered_original_vs_centered_fulltext": spearman(center_old_scores, center_new_scores),
            "original_raw_vs_centered": spearman(raw_old_scores, center_old_scores),
            "fulltext_raw_vs_centered": spearman(raw_new_scores, center_new_scores),
        },
        "topk_neighbor_set_overlap": {
            "original_vs_fulltext_raw":
                same_anchor_knn_overlap(old, new, anchor_ids, k),
            "original_vs_fulltext_centered":
                same_anchor_knn_overlap(centered_old, centered_new, anchor_ids, k),
            "original_raw_vs_centered":
                same_anchor_knn_overlap(old, centered_old, anchor_ids, k),
            "fulltext_raw_vs_centered":
                same_anchor_knn_overlap(new, centered_new, anchor_ids, k),
        },
        "methodological_notes": [
            "Mean-centering removes an empirical corpus-level common vector direction; high original cosine can reflect E5 anisotropy, shared writing style, or document content.",
            "Raw cosine distribution is inherently inflated when the mean vector norm approaches one.",
            "Mean-centering re-normalizes every thesis vector; it is a sensitivity study, not proof of improved semantic or SDG classification.",
            "Keyword/SDG/PDOT descriptor vectors require matching centering/projection before cross-modal cosine scoring.",
            "Old absolute similarity cutoffs must NOT be reused after a geometric transformation.",
            "Sampled pair counts near cosine one do NOT prove duplicate theses; inspect candidate pairs privately before claiming duplication.",
            "No individual thesis vectors, source IDs, scores, predicted classifications, texts or neighbors are exported.",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root", type=Path, required=True)
    p.add_argument("--fulltext", type=Path, default=Path(
        "data/revision_private/fulltext_e5_large_v1/fulltext_e5_large_7830_PRIVATE.npy"
    ))
    p.add_argument("--fulltext-report", type=Path, default=Path(
        "docs/audits/fulltext_e5_large_full_corpus_v1.json"
    ))
    p.add_argument("--pairs", type=int, default=100000)
    p.add_argument("--anchors", type=int, default=256)
    p.add_argument("--k", type=int, default=10)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--output", type=Path, default=Path(
        "docs/audits/reviewer_fulltext_anisotropy.json"
    ))
    a = p.parse_args()
    if a.pairs < 100 or not 10 <= a.anchors <= N or not 1 <= a.k < N:
        p.error("Invalid pair/anchor/neighbor budget")
    workspace = Path(__file__).resolve().parent.parent
    root = a.project_root.expanduser().resolve()
    private_file = a.fulltext.expanduser().resolve()
    if not private_file.is_relative_to((workspace / "data").resolve()):
        raise ValueError("Fulltext embeddings must reside under ignored data/")
    provenance = check_fulltext_report(a.fulltext_report.expanduser().resolve())
    n, alignment = check_row_alignment(root)
    if n != N or not all(alignment.values()):
        raise ValueError("04/05/06/07 corpus not aligned")
    legacy = np.load(root / "data/processed/05_embeddings.npy",
                     mmap_mode="r", allow_pickle=False)
    fulltext = np.load(private_file, mmap_mode="r", allow_pickle=False)
    old, old_norm = normalize_checked(legacy, "original")
    new, new_norm = normalize_checked(fulltext, "fulltext")
    output = {
        "schema_version": 1,
        "status": "full_corpus_embedding_anisotropy_sensitivity_unvalidated",
        "source_rows": N,
        "original_vs_fulltext": alignment,
        "fulltext_provenance": provenance,
        "original_unit_norms": old_norm,
        "fulltext_unit_norms": new_norm,
        "diagnostics": diagnose_pair(old, new, a.pairs, a.anchors, a.k, a.seed),
        "classification_accuracy_evaluated": False,
        "human_ground_truth_available": False,
    }
    path = write_public(output, a.output, workspace)
    print("Anisotropy and mean-centering geometry report:", path)
    print("Original/fulltext mean direction norms:",
          output["diagnostics"]["original_raw_mean_direction_norm"],
          output["diagnostics"]["fulltext_raw_mean_direction_norm"])
    print("No individual thesis records exported; does not establish F1.")


if __name__ == "__main__":
    main()
