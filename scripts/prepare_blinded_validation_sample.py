#!/usr/bin/env python3
"""Create a private, reproducible, double-blind SDG/PDOT annotation sample.

Never publishes thesis IDs, predictions, texts, or row-level annotation sheets.
Saves private CSV files under git-ignored data/revision_private/validation.
Public candidate output is ONLY a sanitized aggregate study-design JSON.

Two independent coders receive the same list of source handles but NO model
predictions, faculty assignments, confidence scores or sample-stratum flags.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

COLS = [
    "handle_id", "faculty", "year", "ods_top1", "pdot_top1",
    "ods_top1_score", "ods_top2_score",
    "pdot_top1_score", "pdot_top2_score",
]


def allocate_quotas(counts: dict[str, int], total: int, min_per_label: int) -> dict[str, int]:
    """Deterministic sqrt-frequency allocation with minimum rare-class quotas."""
    if total < 1 or min_per_label < 0 or not counts:
        raise ValueError("Invalid quota inputs")
    labels = sorted(counts)
    if any(counts[k] < 1 for k in labels):
        raise ValueError("Every class must contain at least one candidate")
    quotas = {k: min(min_per_label, counts[k]) for k in labels}
    if sum(quotas.values()) > total:
        raise ValueError("Stratification minimum exceeds enriched sample size")
    if sum(counts.values()) < total:
        raise ValueError("Population smaller than requested targeted sample")
    while sum(quotas.values()) < total:
        eligible = [k for k in labels if quotas[k] < counts[k]]
        if not eligible:
            raise ValueError("Failed to allocate remaining quotas")
        # Fill to the next sqrt-weighted target; deterministic class-name tie break.
        chosen = min(eligible, key=lambda k: (
            (quotas[k] - min(min_per_label, counts[k])) / math.sqrt(counts[k]),
            k,
        ))
        quotas[chosen] += 1
    return quotas


def select_samples(df, n_total: int, n_random: int, seed: int, min_per_label: int):
    import numpy as np
    import pandas as pd
    if not 0 < n_random < n_total <= len(df):
        raise ValueError("Need 0 < population_random < n_total <= population")
    required = set(COLS)
    if not required.issubset(df.columns):
        raise ValueError("Missing sampling fields: " + ", ".join(sorted(required - set(df.columns))))
    if df["handle_id"].isna().any() or df["handle_id"].astype(str).duplicated().any():
        raise ValueError("Corpus must contain nonempty unique thesis handles")
    if df["ods_top1"].isna().any() or df["pdot_top1"].isna().any():
        raise ValueError("Sampling requires original predicted labels for stratification")
    rng = np.random.default_rng(seed)
    random_idx = rng.choice(len(df), size=n_random, replace=False)
    sampled_set = set(int(i) for i in random_idx)
    remaining = df.loc[~df.index.isin(sampled_set)]
    target_n = n_total - n_random
    counts = {str(k): int(v) for k, v in
              remaining["ods_top1"].astype(str).value_counts().items()}
    quotas = allocate_quotas(counts, target_n, min_per_label)
    enriched_indices = []
    for label, quota in quotas.items():
        frame = remaining.loc[remaining["ods_top1"].astype(str).eq(label)].copy()
        frame["ambiguity"] = (
            (pd.to_numeric(frame["ods_top1_score"], errors="coerce")
             - pd.to_numeric(frame["ods_top2_score"], errors="coerce")).fillna(1)
            + (pd.to_numeric(frame["pdot_top1_score"], errors="coerce")
               - pd.to_numeric(frame["pdot_top2_score"], errors="coerce")).fillna(1)
        )
        ambiguous_n = min(quota // 3, len(frame))
        first = frame.sort_values(["ambiguity"], kind="stable").index[:ambiguous_n].tolist()
        eligible = frame.loc[~frame.index.isin(first)]
        needed = quota - len(first)
        if needed:
            faculty = eligible["faculty"].astype("string").fillna("[missing]").str.strip()
            faculty = faculty.replace("", "[missing]")
            freqs = faculty.value_counts()
            weights = faculty.map(lambda x: 1.0 / math.sqrt(int(freqs[x]))).to_numpy(
                dtype=np.float64)
            weights /= weights.sum()
            chosen = rng.choice(eligible.index.to_numpy(), size=needed,
                                replace=False, p=weights).tolist()
            enriched_indices.extend(first + [int(i) for i in chosen])
        else:
            enriched_indices.extend(first)
    all_indices = [int(x) for x in random_idx] + enriched_indices
    if len(all_indices) != n_total or len(set(all_indices)) != n_total:
        raise AssertionError("Selected sample contains duplicate/missing documents")
    selected = df.iloc[all_indices].copy()
    selected.insert(0, "source_row_index", all_indices)
    selected.insert(1, "study_id", [f"TH-{i + 1:04d}" for i in range(len(selected))])
    selected.insert(2, "selection_stratum", (
        ["population_random"] * n_random + ["targeted_enrichment"] * target_n))
    return selected, quotas


def make_private_and_aggregate(selected, quotas, population, n_random, seed, output_dir, report_file):
    import numpy as np
    import pandas as pd
    private_dir = output_dir.resolve()
    private_dir.mkdir(parents=True, exist_ok=True)
    master = selected.copy()
    master.to_csv(private_dir / "sample_master_private.csv", index=False)
    blind_cols = ["study_id", "handle_id"]
    response_cols = [
        "sdg_primary", "sdg_secondary", "sdg_no_match",
        "pdot_primary", "pdot_secondary", "pdot_no_match",
        "uncertain", "brief_evidence", "coder_notes",
    ]
    for coder, shuffle_seed in (("A", seed + 111), ("B", seed + 222)):
        frame = selected[blind_cols].sample(frac=1, random_state=shuffle_seed).copy()
        for col in response_cols:
            frame[col] = ""
        frame = frame.rename(columns={"handle_id": "private_source_handle"})
        # Coder sheets contain source references for access, never model predictions.
        # Prefix potential spreadsheet formulas while preserving internal identifiers.
        frame["private_source_handle"] = frame["private_source_handle"].astype(str).map(
            lambda x: "'" + x if x and x[0] in "=+-@" else x
        )
        frame.to_csv(private_dir / f"coder_{coder}_private.csv", index=False)
    n = len(selected)
    faculty = selected["faculty"].astype("string").fillna("[unassigned]").str.strip()
    faculty = faculty.replace("", "[unassigned]")
    pdot_counts = selected["pdot_top1"].astype(str).value_counts()
    report = {
        "schema_version": 1, "experiment": "two_coder_blinded_validation_design",
        "status": "prepared_unannotated", "population_rows": int(population),
        "selected_theses": int(n), "population_random_theses": int(n_random),
        "targeted_enrichment_theses": int(n - n_random), "random_seed": seed,
        "original_prediction_labels_used_only_for_sampling": True,
        "coder_sheets_include_model_predictions": False,
        "n_original_ods_strata": len(quotas),
        "minimum_targeted_per_class": min(quotas.values()),
        "maximum_targeted_per_class": max(quotas.values()),
        "n_coder_sheets": 2,
        "selected_predicted_pdot_labels": len(pdot_counts),
        "selected_faculty_strata": int(faculty.nunique()),
        "requirements": [
            "Two human coders must independently inspect source theses without access to model predictions.",
            "Provide a fixed 17-SDG and six-PDOT source-verified codebook, a no-alignment option and adjudication protocol.",
            "Determine valid document access and ethics permissions before distributing any private coder sheets.",
            "The 120-case probability subsample supports population estimates; oversampled cases need explicit design-aware analysis.",
            "Do not derive precision, recall, F1 or Cohen kappa before human annotations have been completed.",
            "Private sample master and coder sheets contain source identifiers; do not upload them to public GitHub.",
        ],
    }
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root", required=True, type=Path)
    p.add_argument("--sample-size", type=int, default=450)
    p.add_argument("--population-random", type=int, default=120)
    p.add_argument("--min-per-ods", type=int, default=8)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--private-output-dir", type=Path,
                   default=Path("data/revision_private/validation"))
    p.add_argument("--report", type=Path,
                   default=Path("docs/audits/validation_sample_design.json"))
    args = p.parse_args()
    project = args.project_root.expanduser().resolve()
    private = args.private_output_dir.expanduser().resolve()
    workspace = Path(__file__).resolve().parent.parent
    if not private.is_relative_to(workspace / "data"):
        raise ValueError("Private files must stay under git-ignored revision/data/")
    report = args.report.expanduser().resolve()
    if report.is_relative_to(workspace / "data"):
        raise ValueError("Aggregate design report should not be stored among private sheets")
    import pandas as pd
    src = project / "data/processed/07_alignment_pdot_ods_needs.parquet"
    frame = pd.read_parquet(src, columns=COLS).reset_index(drop=True)
    selected, quotas = select_samples(frame, args.sample_size, args.population_random,
                                      args.seed, args.min_per_ods)
    aggregate = make_private_and_aggregate(
        selected, quotas, len(frame), args.population_random, args.seed, private, report)
    print(f"Validation sampling prepared: {aggregate['selected_theses']} theses")
    print(f"Population-random: {aggregate['population_random_theses']}; enriched: "
          f"{aggregate['targeted_enrichment_theses']}")
    print("Private coordinator and two blinded coder files are in ignored data/.")
    print("No human validation has yet been completed.")
    print(f"Aggregate design report: {report}")


if __name__ == "__main__":
    main()
