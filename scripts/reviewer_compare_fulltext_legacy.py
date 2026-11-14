#!/usr/bin/env python3
"""Compare full-corpus E5 document vectors against original legacy vectors.

No ground-truth labels are available: results diagnose geometry, NOT
classifier performance. Reads two aligned private 7830 x 1024 matrices.
Writes only aggregate metrics and no raw vectors/IDs, titles or source text.

Checks the final fulltext two-MIG/single-MIG report for exact census success.
Random distinct pairs and anchor documents are sampled with a fixed seed;
all 7830 records are used for same-document cosine and global centering.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from audit_embedding_comparison import check_row_alignment, descriptive
from reviewer_shared import normalize_codes, write_public

N = 7830
D = 1024
EXPECTED_TOKENS = 286050084
EXPECTED_WINDOWS = 854145


def check_fulltext_report(path: Path):
    if not path.is_file():
        raise FileNotFoundError("Final verified full-corpus report unavailable")
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("status") != "complete_full_corpus_fulltext_E5_aggregated_candidate":
        raise ValueError("Fulltext pipeline has not declared verified completion")
    counts = doc.get("full_corpus_counts", {})
    if (
        doc.get("population") != N
        or counts.get("documents") != N
        or counts.get("private_matrix_rows") != N
        or counts.get("private_vector_dimension") != D
        or counts.get("content_tokens") != EXPECTED_TOKENS
        or counts.get("windows") != EXPECTED_WINDOWS
    ):
        raise ValueError("Fulltext final report does not match exact corpus census")
    return {
        "source_sha256": doc.get("source_corpus_sha256"),
        "model_revision_from_cache": doc.get("model_revision_from_cache"),
        "encoding_precision": doc.get("precision"),
        "model": doc.get("model"),
        "run_layout": doc.get("run_layout", "original dual MIG"),
    }


def normalize_checked(arr, name):
    v = np.asarray(arr, dtype=np.float32)
    if v.shape != (N, D) or not np.isfinite(v).all():
        raise ValueError(f"{name} has wrong shape or non-finite vectors")
    norms = np.linalg.norm(v, axis=1)
    if np.any(norms < 1e-8) or np.max(np.abs(norms - 1)) > 1e-3:
        raise ValueError(f"{name} contains zero-length or non-unit E5 vectors")
    return v / norms[:, None], descriptive(norms)


def sample_distinct_pairs(n, count, rng):
    """Each sampled pair has i != j; repeated pairs across draws allowed."""
    if n < 2 or count <= 0:
        raise ValueError("Need positive number of distinct-index pair samples")
    i = rng.integers(0, n, size=count, dtype=np.int64)
    j = rng.integers(0, n - 1, size=count, dtype=np.int64)
    j += (j >= i)
    return i, j


def paired_cosines(x, i, j, batch_size=2048):
    v = np.empty(len(i), dtype=np.float64)
    for pos in range(0, len(i), batch_size):
        sl = slice(pos, min(pos+batch_size, len(i)))
        v[sl] = np.einsum("ij,ij->i", x[i[sl]], x[j[sl]], optimize=True)
    return v


def sample_neighbors(x, anchors, k=10, batch_size=16):
    """Exact top-k across all corpus rows, but only for a random anchor sample."""
    if len(x) <= k or len(anchors) == 0:
        raise ValueError("Invalid nearest-neighbor request")
    out = []
    for pos in range(0, len(anchors), batch_size):
        ids = anchors[pos:pos+batch_size]
        sims = x[ids] @ x.T
        sims[np.arange(len(ids)), ids] = -np.inf
        top = np.argpartition(-sims, kth=k-1, axis=1)[:, :k]
        out.extend(top.tolist())
    return out


def geometry_diagnostics(old, new, pair_count=100000, anchors=256, k=10, seed=42):
    rng = np.random.default_rng(seed)
    i, j = sample_distinct_pairs(len(old), pair_count, rng)
    old_pairs = paired_cosines(old, i, j)
    new_pairs = paired_cosines(new, i, j)
    delta = new_pairs - old_pairs
    same_cosine = np.einsum("ij,ij->i", old, new, optimize=True)
    order_corr = pd.Series(old_pairs).rank().corr(
        pd.Series(new_pairs).rank(), method="pearson"
    )
    picked = rng.choice(len(old), size=min(len(old), anchors), replace=False)
    old_neighbors = sample_neighbors(old, picked, k)
    new_neighbors = sample_neighbors(new, picked, k)
    common = [
        len(set(x) & set(y))/k
        for x, y in zip(old_neighbors, new_neighbors)
    ]

    # Mean direction reveals anisotropy, but not why different theses share it.
    old_mean = old.mean(axis=0, dtype=np.float64)
    new_mean = new.mean(axis=0, dtype=np.float64)
    return {
        "seed": seed, "sampled_distinct_pairs_with_replacement": pair_count,
        "sampled_anchor_documents_without_replacement": len(picked),
        "top_k": k,
        "same_thesis_original_vs_fulltext_cosine": descriptive(same_cosine),
        "old_cross_thesis_cosine": descriptive(old_pairs),
        "fulltext_cross_thesis_cosine": descriptive(new_pairs),
        "fulltext_minus_old_cross_thesis_cosine": descriptive(delta),
        "sampled_pairwise_cosine_rank_spearman": (
            round(float(order_corr), 6) if np.isfinite(order_corr) else None
        ),
        "same_thesis_topk_neighbor_set_overlap": descriptive(common),
        "original_corpus_mean_direction_norm": round(float(np.linalg.norm(old_mean)), 6),
        "fulltext_corpus_mean_direction_norm": round(float(np.linalg.norm(new_mean)), 6),
        "warnings": [
            "Changing cosine geometry, mean direction, or KNN neighborhoods does NOT establish improved ODS/PDOT accuracy.",
            "Pair samples are not independent thesis-level observations; these distributions are descriptive, not confidence intervals.",
            "No direct selection of a better pooling method can be based on greater distance or lower cross-thesis cosine alone.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--fulltext", type=Path, default=Path(
        "data/revision_private/fulltext_e5_large_v1/fulltext_e5_large_7830_PRIVATE.npy"
    ))
    parser.add_argument("--fulltext-report", type=Path, default=Path(
        "docs/audits/fulltext_e5_large_full_corpus_v1.json"
    ))
    parser.add_argument("--pairs", type=int, default=100000)
    parser.add_argument("--anchors", type=int, default=256)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=Path(
        "docs/audits/fulltext_vs_legacy_7830_comparison.json"
    ))
    a = parser.parse_args()
    if a.pairs < 100 or not 10 <= a.anchors <= N or not 1 <= a.k < N:
        parser.error("Invalid pair/anchor/neighbor budget")
    workspace = Path(__file__).resolve().parent.parent
    root = a.project_root.expanduser().resolve()
    private = a.fulltext.expanduser().resolve()
    if not private.is_relative_to((workspace / "data").resolve()):
        raise ValueError("Fulltext matrix must remain under ignored revision/data/")
    source_report = check_fulltext_report(a.fulltext_report)
    n, alignment = check_row_alignment(root)
    if n != N or not all(alignment.values()):
        raise ValueError("Original 04/05/06/07 provenance is not aligned")
    old_mmap = np.load(
        root / "data/processed/05_embeddings.npy",
        mmap_mode="r", allow_pickle=False,
    )
    new_mmap = np.load(private, mmap_mode="r", allow_pickle=False)
    old, old_norms = normalize_checked(old_mmap, "Original E5")
    new, new_norms = normalize_checked(new_mmap, "Fulltext E5")
    diagnostic = geometry_diagnostics(old, new, a.pairs, a.anchors, a.k, a.seed)
    doc = {
        "schema_version": 1,
        "status": "full_corpus_geometric_comparison_complete_unvalidated",
        "n_documents": N,
        "dimensions": D,
        "original_embedding_row_alignment": alignment,
        "fulltext_census_provenance": source_report,
        "original_vector_norms": old_norms,
        "fulltext_vector_norms": new_norms,
        "geometry": diagnostic,
        "notes": [
            "Original 512-token-limited E5 is a legacy comparator; revised input is all extracted thesis text.",
            "No ODS/PDOT labels were recomputed by this geometry diagnostic.",
            "No human adjudication, classifier F1, calibration or policy-impact estimation was performed.",
            "No thesis handles, indexes, text, metadata, individual scores or vectors are exported.",
        ],
    }
    result = write_public(doc, a.output, workspace)
    print("Verified full-corpus E5 comparison:", result)
    print("Original vs fulltext same-thesis median cosine:",
          diagnostic["same_thesis_original_vs_fulltext_cosine"]["median"])
    print("Cross-thesis cosine medians (original/fulltext):",
          diagnostic["old_cross_thesis_cosine"]["median"],
          diagnostic["fulltext_cross_thesis_cosine"]["median"])
    print("No row-level vectors or individual record metadata exported.")


if __name__ == "__main__":
    main()
