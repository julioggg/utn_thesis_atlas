#!/usr/bin/env python3
"""Audit fulltext SDG/PDOT/NEEDS label shifts, including frozen blinded sample.

CPU, no E5 inference. Original 450-case sample remains untouched. No
predictions, labels, strata or confidence values are added to coder sheets.
Only aggregate outputs can appear in docs/audits; all individual predictions
remain in the existing private NPZ.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from reviewer_legacy_alignment_replay import freeze_original_dicts
from reviewer_shared import private_output, sha256_file, write_public

DOMAINS = ("ods", "pdot", "need")
VARIANTS = ("legacy_raw", "legacy_centered", "fulltext_raw", "fulltext_centered")
STRATA = ("population_random", "targeted_enrichment")
EXPECTED = {"population_random": 120, "targeted_enrichment": 330}
N = 7830


def compare_cohort(archive, predicted, ix):
    """Counts only, without cases, handles, titles, per-document predictions."""
    if len(ix) == 0 or len(set(ix.tolist())) != len(ix):
        raise ValueError("Cohort must contain unique source rows")
    base = archive[ix]
    raw = predicted["fulltext_raw"][ix]
    centered = predicted["fulltext_centered"][ix]
    if any(len(values) != len(ix) for values in (base, raw, centered)):
        raise ValueError("Cohort indices invalid")
    return {
        "n_theses": len(ix),
        "historical_vs_fulltext_raw_changed_n": int(np.sum(base != raw)),
        "historical_vs_fulltext_raw_changed_share": round(float(np.mean(base != raw)), 6),
        "historical_vs_fulltext_centered_changed_n": int(np.sum(base != centered)),
        "historical_vs_fulltext_centered_changed_share": round(float(np.mean(base != centered)), 6),
        "fulltext_raw_vs_centered_changed_n": int(np.sum(raw != centered)),
        "fulltext_raw_vs_centered_changed_share": round(float(np.mean(raw != centered)), 6),
    }


def report_domain(archive, variants, cohorts):
    if len(archive) != N or set(variants) != set(VARIANTS):
        raise ValueError("Invalid historical/variant corpus coverage")
    if any(len(x) != N for x in variants.values()):
        raise ValueError("Reclassification source row count differs")
    results = {
        "n_corpus_rows": N,
        "all_theses": compare_cohort(archive, variants, np.arange(N)),
        "frozen_sample_strata": {
            name: compare_cohort(archive, variants, idx) for name, idx in cohorts.items()
        },
        "changed_class_prevalence": [],
    }
    ids = sorted(set(archive.tolist()) | set(variants["fulltext_raw"].tolist())
                 | set(variants["fulltext_centered"].tolist()))
    for label in ids:
        a = int(np.sum(archive == label))
        b = int(np.sum(variants["fulltext_raw"] == label))
        c = int(np.sum(variants["fulltext_centered"] == label))
        results["changed_class_prevalence"].append({
            "category": label,
            "historical_count": a,
            "fulltext_raw_count": b,
            "fulltext_centered_count": c,
            "net_change_raw": b - a,
            "net_change_centered": c - a,
        })
    results["changed_class_prevalence"].sort(
        key=lambda row: (-abs(row["net_change_raw"]), row["category"])
    )
    if any(sum(row[key] for row in results["changed_class_prevalence"]) != N
           for key in ("historical_count", "fulltext_raw_count", "fulltext_centered_count")):
        raise ValueError("Mismatch in class-count totals")
    return results


def analyze(args):
    workspace = Path(__file__).resolve().parent.parent
    root = args.project_root.expanduser().resolve()
    private_root = (workspace / "data").resolve()
    private_file = args.private_scores.expanduser().resolve()
    master_path = args.sample_master.expanduser().resolve()
    if not private_file.is_relative_to(private_root) or not master_path.is_relative_to(private_root):
        raise ValueError("Row-level predictions and sample master must be private")
    source_manifest = (workspace / "data/revision_private/descriptor_inventory/"
                       "descriptor_source_candidates_PRIVATE.json")
    manifest = json.loads(source_manifest.read_text(encoding="utf-8"))
    taxonomy, source_hash = freeze_original_dicts(manifest, root)
    gate = json.loads(args.reclassification_report.expanduser().resolve().read_text(encoding="utf-8"))
    if gate.get("status") != "fulltext_and_centered_ods_pdot_needs_reclassification_exploratory_not_human_validated" or gate.get("n_theses") != N:
        raise ValueError("Fulltext reclassification not completed/verified")
    if gate.get("descriptor_source_sha256") != source_hash:
        raise ValueError("Reclassification does not use original source taxonomy")
    frame = pd.read_parquet(root / "data/processed/07_alignment_pdot_ods_needs.parquet",
                            columns=["handle_id", "ods_top1", "pdot_top1", "need_top1"])
    if len(frame) != N or frame["handle_id"].isna().any() or frame["handle_id"].duplicated().any():
        raise ValueError("Original analysis corpus row provenance invalid")
    master = pd.read_csv(master_path, keep_default_na=False, dtype=str)
    required = {"study_id", "handle_id", "source_row_index", "selection_stratum"}
    if not required.issubset(set(master.columns)) or len(master) != 450:
        raise ValueError("Missing required fields in original 450-case sample")
    ix = master["source_row_index"].astype(int).to_numpy()
    if np.any(ix < 0) or np.any(ix >= N) or len(set(ix.tolist())) != len(ix):
        raise ValueError("Invalid/duplicated source row indices")
    if (not np.array_equal(frame["handle_id"].iloc[ix].astype(str).to_numpy(),
                           master["handle_id"].astype(str).to_numpy())
            or master["study_id"].duplicated().any()):
        raise ValueError("Frozen human sample source handles or study IDs changed")
    strata = master["selection_stratum"].astype(str).to_numpy()
    cohorts = {name: ix[strata == name] for name in STRATA}
    if any(len(cohorts[name]) != EXPECTED[name] for name in STRATA):
        raise ValueError("Frozen 120/330 sample size invalid")
    if set(strata) != set(STRATA):
        raise ValueError("Unexpected sample stratum")
    domain_reports = {}
    with np.load(private_file, allow_pickle=False) as saved:
        for domain in DOMAINS:
            names = list(taxonomy[domain])
            archived = frame[f"{domain}_top1"].astype(str).to_numpy()
            if not set(archived).issubset(set(names)):
                raise ValueError(f"Historical source labels do not match taxonomy {domain}")
            variants = {}
            for v in VARIANTS:
                key = f"{domain}_{v}_top3_indices"
                if key not in saved:
                    raise ValueError(f"Missing private predictions {key}")
                indices = np.asarray(saved[key])
                if indices.shape != (N, 3) or np.any(indices < 0) or np.any(indices >= len(names)):
                    raise ValueError("Invalid private top-3 category indices")
                variants[v] = np.asarray(names)[indices[:, 0]]
            out = report_domain(archived, variants, cohorts)
            calculated_changed = out["all_theses"]["historical_vs_fulltext_raw_changed_n"]
            expected_changed = gate["domains"][domain]["representations"]["fulltext_raw"]["top1_changed_against_original_n"]
            if calculated_changed != expected_changed:
                raise ValueError(f"Fulltext raw flip count mismatch for {domain}")
            raw_centered_changed = out["all_theses"]["fulltext_raw_vs_centered_changed_n"]
            if raw_centered_changed != gate["domains"][domain]["fulltext_raw_vs_fulltext_centered_top1_changed_n"]:
                raise ValueError(f"Fulltext centered flip count mismatch for {domain}")
            domain_reports[domain] = out
    report = {
        "schema_version": 1,
        "status": "fulltext_label_shift_and_frozen_validation_sample_audit_unvalidated",
        "population_n": N,
        "blinded_sample_n": 450,
        "population_probability_subset_n": 120,
        "targeted_enrichment_subset_n": 330,
        "source_taxonomy_sha256": source_hash,
        "private_reclassification_scores_sha256": sha256_file(private_file),
        "private_frozen_validation_sample_sha256": sha256_file(master_path),
        "source_corpus_handle_alignment_verified": True,
        "domains": domain_reports,
        "notes": [
            "Each change is compared with ORIGINAL UNSUPERVISED top1; it is not an error rate or expert accuracy.",
            "Class-level net changes are prevalence differences, not individual transition counts.",
            "The 120-case simple random sample and the targeted 330-case sample remain identical to their frozen versions.",
            "Original 450-case blinded coder sheets were neither read nor modified.",
            "No ground truth, Cohen's kappa, classifier precision, recall or F1 is reported.",
            "Detailed thesis identifiers and individual predictions remain strictly private in the original data.",
            "Do not use changes to modify the frozen blinded sample or show predicted categories to human coders.",
        ],
    }
    result = write_public(report, args.output, workspace)
    print("Aggregate fulltext label-shift and validation-sample coverage:", result)
    for domain, r in domain_reports.items():
        all_ = r["all_theses"]
        test = r["frozen_sample_strata"]["population_random"]
        print(domain,
              "full corpus flips", all_["historical_vs_fulltext_raw_changed_n"],
              "| frozen random 120 flips", test["historical_vs_fulltext_raw_changed_n"])
    print("No original source, coder sheets, scores or samples were modified")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root", type=Path, required=True)
    p.add_argument("--reclassification-report", type=Path, default=Path(
        "docs/audits/reviewer_fulltext_reclassification_v1.json"))
    p.add_argument("--private-scores", type=Path, default=Path(
        "data/revision_private/reviewer_fulltext_reclassification/reclassification_all_7830_PRIVATE.npz"))
    p.add_argument("--sample-master", type=Path, default=Path(
        "data/revision_private/validation/sample_master_private.csv"))
    p.add_argument("--output", type=Path, default=Path(
        "docs/audits/reviewer_fulltext_label_shift_validation_coverage.json"))
    args = p.parse_args()
    if args.output.expanduser().resolve().exists():
        raise FileExistsError("Existing aggregate audit should not be overwritten")
    analyze(args)


if __name__ == "__main__":
    main()
