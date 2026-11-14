#!/usr/bin/env python3
"""Reviewer sensitivity: verified vs imputed faculties; legacy vs fulltext E5.

Reads original private 07 labels and both 7830-row embedding matrices. Uses
full-corpus mean-centered vectors as an EXPLORATORY geometry comparator.
Reports strict (only originally recorded 5 faculties) and conservative
career-imputed (same 5 faculties) sensitivity WITHOUT SDG ground truth.

Every kNN comparison uses identical seed and faculty-balanced document indices
within the same faculty-definition condition, so no model wins by changing
which documents were sampled. The resulting data are aggregate only.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from audit_embedding_comparison import check_row_alignment
from reviewer_shared import FIVE_FACULTIES, read_original_embeddings, write_public
from reviewer_stage1_stats import clean_faculties, contingency_and_tests
from reviewer_stage2_geometry import balanced_knn_mixing, centroid_geometry, unit_rows
from reviewer_fulltext_anisotropy import center_and_normalize
from reviewer_compare_fulltext_legacy import check_fulltext_report, normalize_checked

VIEWS = ("legacy_raw", "legacy_centered", "fulltext_raw", "fulltext_centered")


def strict_faculty_mask(frame):
    """Do not silently treat miscellaneous 'Facultades' as a sixth faculty."""
    values = frame["faculty"].astype("string").str.strip()
    return values.isin(FIVE_FACULTIES).fillna(False).to_numpy(dtype=bool)


def study_views(frame, embeddings, sample_n=350, seed=42):
    if set(embeddings) != set(VIEWS):
        raise ValueError("Expected exactly four aligned embedding variants")
    n = len(frame)
    if any(arr.shape != (n, 1024) for arr in embeddings.values()):
        raise ValueError("Incorrect/misaligned embedding dimensions")
    d, resolution = clean_faculties(frame)
    strict = strict_faculty_mask(d)
    inclusive = d["faculty5"].notna().to_numpy()
    if np.any(strict & ~inclusive):
        raise ValueError("A verified faculty was discarded by career mapping")
    if np.any(~strict & inclusive & ~d["faculty5"].isin(FIVE_FACULTIES).to_numpy()):
        raise ValueError("Imputation generated an invalid faculty")
    groups = {
        "strict_original_faculty_only": strict,
        "conservative_career_imputation": inclusive,
    }
    report = {
        "faculty_provenance": resolution,
        "strict_original_rows": int(strict.sum()),
        "conservative_including_imputed_rows": int(inclusive.sum()),
        "added_heuristic_imputed_rows": int((inclusive & ~strict).sum()),
        "original_missing_or_other_rows_excluded": int((~strict).sum()),
        "sensitivity": {},
    }
    for name, mask in groups.items():
        sub = d.loc[mask]
        faculty = sub["faculty5"].to_numpy(dtype=str)
        if not all((faculty == f).sum() >= 35 for f in FIVE_FACULTIES):
            raise ValueError("A faculty lacks enough rows for kNN-30")
        results = {}
        for variant in VIEWS:
            vectors = np.asarray(embeddings[variant][mask], dtype=np.float32)
            centers, _ = centroid_geometry(vectors, faculty)
            triangle = centers[np.triu_indices(5, k=1)]
            knn = balanced_knn_mixing(
                vectors, faculty, per_faculty=sample_n,
                ks=(5, 15, 30), seed=seed,
            )
            results[variant] = {
                "faculties_n": len(sub),
                "faculty_sizes": {
                    f: int(np.sum(faculty == f)) for f in FIVE_FACULTIES
                },
                "between_faculty_centroid_cosine_distances": {
                    "minimum": round(float(triangle.min()), 6),
                    "median": round(float(np.median(triangle)), 6),
                    "maximum": round(float(triangle.max()), 6),
                },
                "balanced_knn": knn,
            }
        report["sensitivity"][name] = results
    report["cautions"] = [
        "Only geometry and missing-faculty sensitivity; NOT accuracy, recall or F1.",
        "Centring uses the mean of all 7830 thesis vectors before selecting faculties.",
        "All faculty definitions are historical metadata, not independently adjudicated.",
        "A larger cross-faculty nearest-neighbor rate does not establish better science or collaboration.",
        "Missing-faculty rows are excluded from faculty associations, not silently imputed into the five groups.",
        "Original and fulltext vectors share positional provenance; no source records are exported.",
    ]
    return report


def analyze(args):
    root = args.project_root.expanduser().resolve()
    workspace = Path(__file__).resolve().parent.parent
    report = check_fulltext_report(args.fulltext_report.expanduser().resolve())
    n, alignment = check_row_alignment(root)
    frame = pd.read_parquet(
        root / "data/processed/07_alignment_pdot_ods_needs.parquet",
        columns=["handle_id", "faculty", "career"]
    )
    if len(frame) != n or frame["handle_id"].isna().any() or frame["handle_id"].duplicated().any():
        raise ValueError("Analysis file ID integrity failure")
    original, original_align = read_original_embeddings(root, n)
    private = args.fulltext.expanduser().resolve()
    if not private.is_relative_to((workspace / "data").resolve()):
        raise ValueError("Fulltext matrix must be in ignored revision/data")
    new = np.load(private, mmap_mode="r", allow_pickle=False)
    old, _ = normalize_checked(original, "Legacy original E5")
    full, _ = normalize_checked(new, "Fulltext E5")
    old_center, _, _ = center_and_normalize(old)
    new_center, _, _ = center_and_normalize(full)
    diagnostics = study_views(
        frame,
        {
            "legacy_raw": old, "legacy_centered": old_center,
            "fulltext_raw": full, "fulltext_centered": new_center,
        },
        sample_n=args.per_faculty, seed=args.seed,
    )
    return {
        "schema_version": 1,
        "status": "original_vs_fulltext_faculty_sensitivity_unvalidated",
        "n_corpus_rows": n,
        "alignment": alignment,
        "original_alignment": original_align,
        "fulltext_provenance": report,
        "per_faculty_sample_n_requested": args.per_faculty,
        "seed": args.seed,
        "diagnostics": diagnostics,
        "sdg_or_pdot_classifier_recomputed": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root", type=Path, required=True)
    p.add_argument("--fulltext", type=Path, default=Path(
        "data/revision_private/fulltext_e5_large_v1/fulltext_e5_large_7830_PRIVATE.npy"))
    p.add_argument("--fulltext-report", type=Path, default=Path(
        "docs/audits/fulltext_e5_large_full_corpus_v1.json"))
    p.add_argument("--per-faculty", type=int, default=350)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--output", type=Path, default=Path(
        "docs/audits/reviewer_fulltext_faculty_sensitivity.json"))
    args = p.parse_args()
    if not 35 <= args.per_faculty <= 500:
        p.error("per-faculty must be between 35 and 500")
    result = analyze(args)
    path = write_public(result, args.output, Path(__file__).resolve().parent.parent)
    print("Fulltext vs legacy strict/imputed faculty sensitivity complete:", path)
    print("Strict rows:", result["diagnostics"]["strict_original_rows"],
          "career-imputed added:", result["diagnostics"]["added_heuristic_imputed_rows"])
    print("No row-level vectors, metadata, labels or thesis names exported.")


if __name__ == "__main__":
    main()
