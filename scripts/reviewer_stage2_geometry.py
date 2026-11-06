#!/usr/bin/env python3
"""Reviewer-requested original-space interdisciplinary geometry and time trends.

Uses aligned ORIGINAL (unvalidated truncated) E5 embeddings, never UMAP hulls.
Produces faculty centroid distances, stratified balanced kNN neighborhood
mixing, topic-level Rao-Stirling diversity based on faculty centroid semantic
distances, auditable candidate bridge-topic IDs and 2021-25 growth diagnostics
excluding partial 2026. No thesis records/handles, embeddings or raw texts
leave CEDIA. Metadata is NOT expert SDG ground truth.
"""
from __future__ import annotations
import argparse
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd

from reviewer_shared import (FIVE_FACULTIES, normalized_entropy,
                             private_output, read_original_embeddings, write_public)
from reviewer_stage1_stats import clean_faculties


def unit_rows(arr):
    x = np.asarray(arr, dtype=np.float32)
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    if not np.isfinite(x).all() or np.any(norms < 1e-8):
        raise ValueError("Invalid embedding or zero-norm row")
    return x / norms


def centroid_geometry(vectors, faculties):
    centers = []
    for fac in FIVE_FACULTIES:
        sub = np.asarray(vectors[np.asarray(faculties) == fac])
        if not len(sub):
            raise ValueError("Empty faculty")
        centroid = unit_rows(np.mean(sub, axis=0, keepdims=True))[0]
        centers.append(centroid)
    centers = np.asarray(centers)
    pairwise = np.clip(1 - centers @ centers.T, 0, 2)
    np.fill_diagonal(pairwise, 0)
    return pairwise, centers


def balanced_knn_mixing(vectors, faculties, per_faculty=400, ks=(5,15,30), seed=42):
    labels = np.asarray(faculties)
    rng = np.random.default_rng(seed)
    cap = min(int(np.sum(labels == f)) for f in FIVE_FACULTIES)
    n_pick = min(cap, per_faculty)
    if n_pick < max(ks)+1:
        raise ValueError("Not enough rows for largest KNN neighborhood")
    idx = np.concatenate([
        rng.choice(np.flatnonzero(labels == f), size=n_pick, replace=False)
        for f in FIVE_FACULTIES
    ])
    sample = unit_rows(np.asarray(vectors[idx]))
    fac = labels[idx]
    k_max = max(ks)
    per_row = np.zeros((len(idx), k_max), dtype=bool)
    # Compute only 128 x n similarity tiles to avoid a dense N x N allocation.
    for start in range(0, len(idx), 128):
        end = min(len(idx), start+128)
        sims = sample[start:end] @ sample.T
        sims[np.arange(end-start), np.arange(start, end)] = -np.inf
        # Sorted top-k neighbors: stable tie-breaking by original sample position.
        order = np.argpartition(-sims, kth=k_max-1, axis=1)[:, :k_max]
        scores = np.take_along_axis(sims, order, axis=1)
        sorted_ix = np.argsort(-scores, axis=1, kind="stable")
        nearest = np.take_along_axis(order, sorted_ix, axis=1)
        per_row[start:end] = fac[nearest] != fac[start:end, None]
    expected_between_groups = (len(idx)-n_pick)/(len(idx)-1)
    out = {
        "selection": "equal-size sample within each of five real faculty groups",
        "seed": seed, "sampling_without_replacement": True,
        "per_faculty_n": n_pick, "balanced_n": len(idx),
        "random_group_mix_expectation_exact": round(float(expected_between_groups),6),
        "k_statistics": {},
        "limitation": "Neighborhood mixing among faculties reflects embeddings and disciplinary metadata; not proof of cross-faculty research collaboration.",
    }
    for k in ks:
        out["k_statistics"][str(k)] = {
            "fraction_neighbors_other_faculty": round(float(per_row[:, :k].mean()),6),
            "mean_other_faculty_neighborhood_fraction_by_faculty": {
                f: round(float(per_row[fac == f, :k].mean()),6)
                for f in FIVE_FACULTIES
            },
        }
    return out


def topic_bridge_candidates(topics, faculties, distances, minimum_n=20,
                            minimum_per_second_faculty=10):
    data = pd.DataFrame({"topic": np.asarray(topics).astype(str),
                         "faculty": np.asarray(faculties)})
    values = []
    for topic, group in data.groupby("topic"):
        numbers = np.array([(group["faculty"] == f).sum() for f in FIVE_FACULTIES],
                           dtype=np.float64)
        n = len(group)
        if n < minimum_n or np.sum(numbers >= minimum_per_second_faculty) < 2:
            continue
        proportions = numbers/n
        gini_simpson = 1 - float((proportions**2).sum())
        rao_stirling = float(proportions @ distances @ proportions)
        values.append({
            "original_topic_id": str(topic), "n_five_faculty": n,
            "faculties_at_least_10_theses": int((numbers>=minimum_per_second_faculty).sum()),
            "shannon_faculty_diversity_normalized": round(normalized_entropy(numbers),6),
            "gini_simpson_faculty_mix": round(gini_simpson,6),
            "rao_stirling_faculty_centroid_semantic_diversity": round(rao_stirling,6),
            "faculty_counts": {
                f: int(numbers[i]) for i, f in enumerate(FIVE_FACULTIES)
            },
        })
    values.sort(key=lambda x: (-x["rao_stirling_faculty_centroid_semantic_diversity"],
                               -x["n_five_faculty"], x["original_topic_id"]))
    return {
        "min_topic_n": minimum_n,
        "min_theses_in_at_least_two_faculties": minimum_per_second_faculty,
        "qualifying_topic_ids": len(values),
        "top_candidates": values[:20],
        "interpretation": "These are candidate topic IDs with cross-faculty presence, NOT verified scientific bridge topics; identify descriptive keywords and inspect documents before naming them.",
    }


def conservative_growth(topics, years, min_recent=10):
    d = pd.DataFrame({"topic": np.asarray(topics).astype(str),
                      "year": pd.to_numeric(years, errors="coerce")})
    annual = d["year"].value_counts().sort_index()
    periods = ((2021,2022),(2024,2025))
    counts = d.groupby(["topic","year"]).size()
    items = []
    for topic, _ in d.groupby("topic"):
        early = sum(int(counts.get((topic, yr), 0)) for yr in periods[0])
        recent = sum(int(counts.get((topic, yr), 0)) for yr in periods[1])
        if recent < min_recent:
            continue
        e_n = sum(int(annual.get(y, 0)) for y in periods[0])
        r_n = sum(int(annual.get(y, 0)) for y in periods[1])
        if e_n <= 0 or r_n <= 0:
            raise ValueError("Missing reference years")
        old_share, new_share = early/e_n, recent/r_n
        # Smoothed share ratio is a descriptive statistic, NOT evidence of emergence.
        ratio = ((recent+.5)/(r_n+1))/((early+.5)/(e_n+1))
        items.append({
            "original_topic_id": topic, "2021_22_n": early,
            "2024_25_n": recent, "2021_22_share": round(old_share,7),
            "2024_25_share": round(new_share,7),
            "smoothed_share_ratio": round(float(ratio),5),
        })
    items.sort(key=lambda v: (-v["smoothed_share_ratio"], -v["2024_25_n"],
                               v["original_topic_id"]))
    return {
        "included_years": [2021,2022,2023,2024,2025],
        "2026_excluded_due_to_incomplete_year": True,
        "annual_counts": {str(k): int(v) for k, v in annual.items()},
        "min_recent_period_n": min_recent,
        "top_growth_candidate_topic_ids": items[:20],
        "label": "relative topic-share growth, not proven novelty or impact",
        "warnings": [
            "2026 is excluded from period comparisons.",
            "Only 2021-22 versus 2024-25 shares are compared; no extrapolation.",
            "Topic IDs require review of the original 75-topic descriptor table.",
            "Multiple comparisons and topic-model instability are not corrected by descriptive ratios.",
        ],
    }


def analyze(args):
    root = args.project_root.expanduser().resolve()
    workspace = Path(__file__).resolve().parent.parent
    data = pd.read_parquet(root / "data/processed/07_alignment_pdot_ods_needs.parquet",
                           columns=["handle_id","faculty","career","topic","year"])
    n = len(data)
    if n != 7830 or data["handle_id"].isna().any() or data["handle_id"].duplicated().any():
        raise ValueError("Corpus provenance check failed")
    d, fac_audit = clean_faculties(data, args.min_career_support, args.min_career_purity)
    mask = d["faculty5"].notna().to_numpy()
    embeddings, order_audit = read_original_embeddings(root, n)
    vectors = unit_rows(np.asarray(embeddings[mask], dtype=np.float32))
    faculty = d.loc[mask, "faculty5"].to_numpy(dtype=str)
    centroid_distances, _ = centroid_geometry(vectors, faculty)
    mixing = balanced_knn_mixing(vectors, faculty,
                                 args.per_faculty, (5,15,30), args.seed)
    bridge = topic_bridge_candidates(
        d.loc[mask, "topic"].to_numpy(), faculty, centroid_distances,
        args.min_topic_n, args.min_second_faculty_n
    )
    trends = conservative_growth(d["topic"].to_numpy(), d["year"].to_numpy(),
                                 args.min_recent)
    private = private_output(args.private_dir, workspace)
    pd.DataFrame(centroid_distances, index=FIVE_FACULTIES,
                 columns=FIVE_FACULTIES).to_csv(
                     private / "five_faculty_centroid_cosine_distances_private.csv")
    return {
        "schema_version": 1, "status": "original_embedding_geometry_and_topic_trends",
        "source_model": "original truncated E5 1024D; NOT fulltext or a human-labeled truth",
        "n_source_records": n,
        "n_five_faculty_rows": int(mask.sum()),
        "faculty_resolution": fac_audit,
        "embedding_provenance": order_audit,
        "centroid_cosine_distances": {
            f: {t: round(float(centroid_distances[i,j]),6)
                for j,t in enumerate(FIVE_FACULTIES)}
            for i,f in enumerate(FIVE_FACULTIES)
        },
        "balanced_original_space_knn": mixing,
        "topic_bridge_candidates": bridge,
        "conservative_topic_trends": trends,
        "warnings": [
            "UMAP plot areas and convex hulls are not measures of original-space interdisciplinarity.",
            "Topic and faculty metadata are original and imperfect; imputation is sensitivity-only.",
            "Bridge-topic IDs need manual topic keyword descriptions before manuscript interpretation.",
            "This report does NOT establish scientific originality or sustainability contribution.",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root", type=Path, required=True)
    p.add_argument("--per-faculty", type=int, default=400)
    p.add_argument("--min-topic-n", type=int, default=20)
    p.add_argument("--min-second-faculty-n", type=int, default=10)
    p.add_argument("--min-recent", type=int, default=10)
    p.add_argument("--min-career-support", type=int, default=10)
    p.add_argument("--min-career-purity", type=float, default=.98)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--private-dir", type=Path, default=Path("data/revision_private/reviewer_stage2"))
    p.add_argument("--output", type=Path,
                   default=Path("docs/audits/reviewer_stage2_geometry_trends.json"))
    args = p.parse_args()
    if args.per_faculty < 35 or args.min_topic_n < 10:
        p.error("Insufficient data for neighborhoods or bridging")
    start = time.perf_counter()
    report = analyze(args)
    report["elapsed_seconds"] = round(time.perf_counter()-start,3)
    path = write_public(report, args.output, Path(__file__).resolve().parent.parent)
    print("Stage 2 completed:", path)
    print("Balanced neighborhood sample:", report["balanced_original_space_knn"]["balanced_n"])
    print("Candidate topic bridges:", report["topic_bridge_candidates"]["qualifying_topic_ids"])
    print("No row-level source information exported.")


if __name__ == "__main__":
    main()
