#!/usr/bin/env python3
"""Reviewer 1-4 statistical reconstruction from the ORIGINAL (unvalidated) atlas.

Read-only. Five genuine faculties only, optional high-certainty career mapping,
17 SDGs, expected-cell checks, adjusted residuals, permutation chi-square,
rank-based faculty dispersion (not 'originality'), epsilon-squared, pairwise
post-hoc tests, entropy rarefaction, SDG-4 breakdown, abstention sensitivity,
and candidate need-coverage formula. All per-cell tables stay in ignored data/.
The public candidate JSON contains aggregate method audits only.
"""
from __future__ import annotations
import argparse
import itertools
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd

from reviewer_shared import (FIVE_FACULTIES, bh_adjust, normalized_entropy,
                             normalize_codes, private_output, read_original_embeddings,
                             summary, write_public, z_two_sided)


def clean_faculties(data, min_support=10, min_purity=.98):
    """Conservative career-to-faculty mapping using verified real faculty rows."""
    d = data.copy()
    d["faculty5"] = d["faculty"].astype("string").str.strip().where(
        d["faculty"].astype("string").str.strip().isin(FIVE_FACULTIES)
    )
    d["career_norm"] = d["career"].astype("string").fillna("").str.strip().str.casefold()
    d.loc[d["career_norm"].isin(["", "nan", "none"]), "career_norm"] = ""
    known = d["faculty5"].notna()
    ctab = pd.crosstab(d.loc[known & d["career_norm"].ne(""), "career_norm"],
                       d.loc[known & d["career_norm"].ne(""), "faculty5"])
    mapping = {}
    for name, values in ctab.iterrows():
        amount = int(values.sum())
        if amount >= min_support and (values.max() / amount) >= min_purity:
            mapping[name] = str(values.idxmax())
    needs = d["faculty5"].isna() & d["career_norm"].isin(mapping)
    d.loc[needs, "faculty5"] = d.loc[needs, "career_norm"].map(mapping)
    audit = {
        "strict_known_five_faculty_rows": int(known.sum()),
        "unknown_or_misc_input_rows": int((~known).sum()),
        "career_mappings_eligible": len(mapping),
        "career_imputed_rows": int(needs.sum()),
        "unresolved_rows": int(d["faculty5"].isna().sum()),
        "minimum_career_support": min_support,
        "minimum_mapping_purity": min_purity,
        "rule": "strict learned mapping from explicitly labeled real-faculty rows",
        "caution": "Imputed faculty is not an official administrative record; report sensitivity excluding it.",
    }
    return d, audit


def contingency_and_tests(group, labels, seed=42, permutations=499):
    group = np.asarray(group)
    labels = np.asarray(labels)
    fac = list(FIVE_FACULTIES)
    cats = [f"ODS {i}" for i in range(1, 18)]
    g = np.array([fac.index(x) for x in group], dtype=int)
    y = np.array([cats.index(x) for x in labels], dtype=int)
    n = len(y)
    observed = np.bincount(g * len(cats) + y, minlength=5 * 17).reshape(5, 17)
    row = observed.sum(1)
    col = observed.sum(0)
    expected = np.outer(row, col) / max(n, 1)
    if n < 1 or np.any(row == 0):
        raise ValueError("Insufficient nonempty faculty groups")
    chi = float(np.sum(np.divide((observed - expected) ** 2, expected,
                                 out=np.zeros_like(expected, dtype="float64"),
                                 where=expected > 0)))
    v = math.sqrt(chi / (n * min(observed.shape[0]-1, observed.shape[1]-1)))
    corr_residual = np.divide(observed - expected, np.sqrt(
        expected * (1-row[:, None]/n) * (1-col[None, :]/n)
    ), out=np.zeros_like(expected, dtype="float64"),
       where=(expected > 0) & (row[:, None] < n) & (col[None, :] < n))
    rng = np.random.default_rng(seed)
    larger = 0
    for _ in range(permutations):
        yy = rng.permutation(y)
        sim = np.bincount(g * 17 + yy, minlength=85).reshape(5, 17)
        score = np.sum(np.divide((sim - expected) ** 2, expected,
                                 out=np.zeros_like(expected, dtype="float64"),
                                 where=expected > 0))
        larger += score >= chi - 1e-12
    p_perm = (larger + 1)/(permutations + 1)
    tests = []
    for i, j in itertools.product(range(5), range(17)):
        exp = float(expected[i, j])
        if exp < 5:
            continue
        z = float(corr_residual[i, j])
        tests.append((i, j, z, z_two_sided(z)))
    adjusted = bh_adjust([x[3] for x in tests])
    significant = []
    for (i, j, z, p), q in zip(tests, adjusted):
        if q < .05:
            significant.append({
                "faculty": fac[i], "ods": cats[j], "observed": int(observed[i, j]),
                "expected": round(float(expected[i, j]), 3),
                "adjusted_residual_z": round(z, 3),
                "q_bh": q,
            })
    return observed, expected, {
        "five_faculty_n": n,
        "chi_squared": round(chi, 4),
        "permutation_p_value": round(float(p_perm), 6),
        "permutations": permutations,
        "df_nominal": (5-1)*(17-1),
        "cramers_v": round(v, 6),
        "min_expected": round(float(expected.min()), 6),
        "n_expected_below_5": int((expected < 5).sum()),
        "n_expected_below_1": int((expected < 1).sum()),
        "fraction_expected_below_5": round(float(np.mean(expected < 5)), 6),
        "residuals_compared_only_where_expected_at_least_5": len(tests),
        "significant_adjusted_residual_cells": significant,
        "interpretation": "Permutation inference avoids relying solely on asymptotic chi-square when expected cells are sparse. Association is expected for discipline-defined faculties.",
    }


def kw_rank_dispersion(values, groups, seed=42, permutations=299):
    """Kruskal H with tie correction; contrasts use within-pair rank tests."""
    x = np.asarray(values, dtype="float64")
    g = np.asarray(groups)
    valid = np.isfinite(x)
    x, g = x[valid], g[valid]
    n = len(x)
    ranks = pd.Series(x).rank(method="average").to_numpy()
    names = list(FIVE_FACULTIES)
    count = np.array([np.sum(g == f) for f in names], dtype=int)
    if not np.all(count > 0):
        raise ValueError("All five faculties must have values")
    sums = np.array([ranks[g == f].sum() for f in names])
    h = 12 * np.sum(sums ** 2 / count) / (n*(n+1)) - 3*(n+1)
    _, multiplicity = np.unique(x, return_counts=True)
    ties = 1 - np.sum(multiplicity.astype(float) ** 3 - multiplicity) / (n**3-n)
    h = float(h / ties) if ties > 0 else 0.
    eps2 = max(0., (h - len(names) + 1)/(n - len(names)))
    rng = np.random.default_rng(seed)
    above = 0
    for _ in range(permutations):
        perm = rng.permutation(g)
        s = np.array([ranks[perm == f].sum() for f in names])
        test = 12 * np.sum(s ** 2 / count) / (n*(n+1)) - 3*(n+1)
        test = test / ties if ties > 0 else 0.
        above += test >= h - 1e-10
    contrast = []
    for a, b in itertools.combinations(names, 2):
        xx, yy = x[g == a], x[g == b]
        ab = np.r_[xx, yy]
        z = pd.Series(ab).rank(method="average").to_numpy()
        na, nb = len(xx), len(yy)
        U = float(z[:na].sum() - na*(na+1)/2)
        mult = np.unique(ab, return_counts=True)[1].astype("float64")
        variance = na*nb/12 * (
            na + nb + 1 - np.sum(mult ** 3-mult)/((na+nb)*(na+nb-1))
        )
        zs = (U - na*nb/2) / math.sqrt(variance) if variance > 0 else 0.
        contrast.append({
            "faculty_a": a, "faculty_b": b,
            "n_a": na, "n_b": nb,
            "rank_biserial": round(2*U/(na*nb)-1, 6),
            "approximate_p": z_two_sided(zs),
            "median_difference": round(float(np.median(xx)-np.median(yy)), 6),
        })
    q = bh_adjust([v["approximate_p"] for v in contrast])
    for entry, qval in zip(contrast, q):
        entry["posthoc_bh_q"] = qval
        entry.pop("approximate_p")
    return {
        "n": n, "H_tie_corrected": round(h, 4), "df": len(names)-1,
        "epsilon_squared_clamped": round(eps2, 6),
        "permutation_p_value": round((above+1)/(permutations+1), 6),
        "n_permutations": permutations,
        "group_semantic_distance": {
            f: summary(x[g == f]) for f in names
        },
        "posthoc_rank_biserial_bh": contrast,
        "label": "within-faculty semantic atypicality (cosine distance to its centroid), NOT scientific originality",
    }


def rarefy_entropy(groups, labels, draws=300, sample_size=300, seed=42):
    rng = np.random.default_rng(seed)
    data = {}
    for fac in FIVE_FACULTIES:
        y = np.asarray(labels)[np.asarray(groups) == fac]
        if len(y) < sample_size:
            raise ValueError("Rarefaction size greater than a faculty's available sample")
        values = []
        for _ in range(draws):
            selected = rng.choice(y, sample_size, replace=False)
            count = np.array([np.count_nonzero(selected == f"ODS {i}") for i in range(1,18)])
            values.append(normalized_entropy(count))
        data[fac] = {
            "rarefied_mean_normalized_shannon": round(float(np.mean(values)), 6),
            "simulation_2p5": round(float(np.quantile(values, .025)), 6),
            "simulation_97p5": round(float(np.quantile(values, .975)), 6),
            "raw_full_group_entropy_not_comparable_without_rarefaction": round(
                normalized_entropy([np.count_nonzero(y == f"ODS {i}") for i in range(1,18)]), 6
            ),
            "n_group": int(len(y)),
        }
    return {"sampling_without_replacement": True, "draws_per_faculty": draws,
            "rarefaction_n": sample_size,
            "interval_type": "Monte Carlo subsampling quantiles, not inferential confidence intervals",
            "faculties": data}


def score_thresholds(frame):
    domains = [
        ("ods", "ods_top1_score", "ods_top2_score"),
        ("pdot", "pdot_top1_score", "pdot_top2_score"),
        ("need", "need_top1_score", "need_top2_score"),
    ]
    report = {}
    for name, col1, col2 in domains:
        a = pd.to_numeric(frame[col1], errors="coerce").to_numpy(dtype="float64")
        b = pd.to_numeric(frame[col2], errors="coerce").to_numpy(dtype="float64")
        if not np.isfinite(a).all() or not np.isfinite(b).all():
            raise ValueError("Non-finite score rows")
        if np.any(a < b - 1e-6):
            raise ValueError("Top-1 score below top-2: top-rank data corrupt")
        report[name] = {
            "top1_scores": summary(a),
            "top1_minus_top2_margin": summary(a-b),
            "top1_score_cutoffs": {
                f"{v:.3f}": {"abstain_n": int((a < v).sum()),
                             "abstain_share": round(float(np.mean(a < v)), 6)}
                for v in (.75,.78,.79,.80,.81,.82,.83)
            },
            "margin_cutoffs": {
                f"{v:.3f}": {"ambiguous_n": int(((a-b) < v).sum()),
                             "ambiguous_share": round(float(np.mean((a-b) < v)), 6)}
                for v in (.002,.005,.01,.02)
            },
            "joint_score_0p80_margin_0p01": {
                "would_abstain_n": int(np.sum((a < .80) | ((a-b)<.01))),
                "retained_n": int(np.sum((a >= .80) & ((a-b)>=.01))),
            },
            "warning": "Only threshold coverage, not calibrated accuracy; top-2 label IDs and full class similarity matrix are not stored here. Multi-label decisions require original descriptors."
        }
    return report


def coverage_need(frame):
    data = []
    total = len(frame)
    for name, subset in frame.groupby("need_top1", dropna=False):
        count = len(subset)
        mean = float(pd.to_numeric(subset["need_top1_score"]).mean())
        share = count/total
        data.append({
            "need": str(name), "n": count,
            "share": round(share, 6),
            "mean_assigned_cosine": round(mean, 6),
            "candidate_coverage_share_times_mean_cosine": round(share*mean, 8)
        })
    data.sort(key=lambda x: (-x["n"], x["need"]))
    return {
        "candidate_formula": "coverage_i = (n_i / N) * mean(top1_similarity_i)",
        "is_original_manuscript_formula_verified": False,
        "not_a_territorial_impact_metric": True,
        "needs": data,
    }


def run(args):
    root = args.project_root.expanduser().resolve()
    workspace = Path(__file__).resolve().parent.parent
    data = pd.read_parquet(root / "data/processed/07_alignment_pdot_ods_needs.parquet",
                           columns=[
                               "handle_id","faculty","career","year","topic",
                               "ods_top1","pdot_top1","need_top1",
                               "ods_top1_score","ods_top2_score",
                               "pdot_top1_score","pdot_top2_score",
                               "need_top1_score","need_top2_score",
                           ])
    if len(data) != 7830 or data["handle_id"].isna().any() or data["handle_id"].duplicated().any():
        raise ValueError("Unexpected corpus size or source-ID integrity issue")
    n = len(data)
    ods = np.asarray(normalize_codes(data["ods_top1"]))
    if "[invalid]" in ods:
        raise ValueError("Unexpected SDG code in original classification")
    frame, faculty_report = clean_faculties(
        data, args.min_career_support, args.min_career_purity
    )
    mask = frame["faculty5"].notna().to_numpy()
    fac = frame.loc[mask, "faculty5"].to_numpy(dtype="str")
    assigned = ods[mask]
    cont, expected, association = contingency_and_tests(
        fac, assigned, args.seed, args.permutations
    )
    original, alignment = read_original_embeddings(root, n)
    clean_vec = np.asarray(original[mask], dtype=np.float32)
    norms = np.linalg.norm(clean_vec, axis=1, keepdims=True)
    if not np.isfinite(norms).all() or np.any(norms < 1e-8):
        raise ValueError("Original embedding vectors have zero/invalid norms")
    clean_vec = clean_vec/norms
    semantic_distance = np.zeros(len(clean_vec), dtype=np.float64)
    for f in FIVE_FACULTIES:
        ix = np.flatnonzero(fac == f)
        centroid = clean_vec[ix].astype("float64").mean(axis=0)
        mag = np.linalg.norm(centroid)
        if mag < 1e-8:
            raise ValueError("Degenerate faculty centroid")
        centroid /= mag
        semantic_distance[ix] = 1 - clean_vec[ix] @ centroid.astype("float32")
    dispersion = kw_rank_dispersion(semantic_distance, fac, args.seed, max(99, args.permutations // 2))
    small_n = min(int(np.sum(fac == f)) for f in FIVE_FACULTIES)
    rarefied = rarefy_entropy(fac, assigned, draws=args.entropy_draws,
                             sample_size=min(args.entropy_n, small_n), seed=args.seed)
    score_report = score_thresholds(frame)
    needs = coverage_need(frame)
    private = private_output(args.private_dir, workspace)
    pd.DataFrame(cont, index=FIVE_FACULTIES,
                 columns=[f"ODS {x}" for x in range(1,18)]).to_csv(
                     private / "faculty_sdg_contingency_private.csv")
    pd.DataFrame(expected, index=FIVE_FACULTIES,
                 columns=[f"ODS {x}" for x in range(1,18)]).to_csv(
                     private / "faculty_sdg_expected_private.csv")
    pd.DataFrame({"original_row_index": np.flatnonzero(mask),
                  "faculty5": fac, "semantic_atypicality": semantic_distance,
                  "ods": assigned}).to_csv(private / "semantic_dispersion_by_thesis_private.csv", index=False)
    report = {
        "schema_version": 1, "status": "original_atlas_review_statistics_unvalidated",
        "model_version": "ORIGINAL legacy truncated E5; not a full-text regeneration",
        "n_original": n, "alignment": alignment,
        "faculty_resolution": faculty_report,
        "faculty_ods": association,
        "rarefied_entropy": rarefied,
        "semantic_atypicality": dispersion,
        "classifier_score_threshold_diagnostics": score_report,
        "candidate_territorial_need_coverage": needs,
        "ods4": {
            "overall_count_original": int(np.sum(ods == "ODS 4")),
            "known_or_imputed_five_faculty_count": int(np.sum(assigned == "ODS 4")),
            "five_faculty_distribution": {
                f: {"total": int(np.sum(fac == f)),
                    "ods4": int(np.sum((fac == f)&(assigned == "ODS 4")))}
                for f in FIVE_FACULTIES
            },
        },
        "limitations": [
            "All observed SDG/PDOT labels are unvalidated legacy forced top-1 predictions.",
            "Career-based faculty imputation is high-purity heuristic and not confirmed administration.",
            "Sparse cells invalidate naive asymptotic chi-square interpretation; use permutation checks.",
            "SDG 4 prevalence outside education does not by itself prove false-positive assignment.",
            "The coverage index is a candidate formula, not recovered proof of manuscript's equation.",
            "No human SDG/PDOT ground truth or alternate embedding methods are evaluated here.",
            "Per-thesis values and full contingency/expected tables are kept private on CEDIA.",
        ]
    }
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root", type=Path, required=True)
    p.add_argument("--min-career-support", type=int, default=10)
    p.add_argument("--min-career-purity", type=float, default=.98)
    p.add_argument("--permutations", type=int, default=499)
    p.add_argument("--entropy-draws", type=int, default=300)
    p.add_argument("--entropy-n", type=int, default=300)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--private-dir", type=Path,
                   default=Path("data/revision_private/reviewer_stage1"))
    p.add_argument("--output", type=Path,
                   default=Path("docs/audits/reviewer_stage1_statistics.json"))
    args = p.parse_args()
    if args.permutations < 19 or args.entropy_draws < 10 or args.entropy_n < 2:
        p.error("Increase Monte Carlo draws for reproducibility")
    start = time.perf_counter()
    result = run(args)
    result["elapsed_seconds"] = round(time.perf_counter()-start, 3)
    path = write_public(result, args.output, Path(__file__).resolve().parent.parent)
    print("Stage 1 statistical audit complete. Public aggregate candidate:", path)
    print("Verified five-faculty rows:", result["faculty_ods"]["five_faculty_n"])
    print("Sparse expected cells (<5):", result["faculty_ods"]["n_expected_below_5"])
    print("Private per-thesis/stat tables remain under ignored data/.")


if __name__ == "__main__":
    main()
