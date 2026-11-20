#!/usr/bin/env python3
"""Round-2 read-only readiness audit for the Sustainability thesis atlas.

Creates a STATUS-ONLY report. It does not read thesis content, export annotations,
publish file paths, or claim that a present report has passed scientific review.
Run in the separate revision clone, never in the original research project.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

PUBLIC_REPORTS = {
    "corpus_audit": "reports/public/corpus_audit.json",
    "provenance_audit": "reports/public/provenance_audit.json",
    "token_length_audit": "reports/public/token_length_audit.json",
    "hpc_inventory": "reports/public/hpc_inventory.json",
    "faculty_statistics": "docs/audits/reviewer_stage1_statistics.json",
    "geometry_and_trends": "docs/audits/reviewer_stage2_geometry_trends.json",
    "k_and_seed_stability": "docs/audits/reviewer_stage3_stability.json",
    "figure_reconciliation": "docs/audits/reviewer_figure_reconciliation.json",
    "descriptor_source_inventory": "docs/audits/descriptor_source_inventory.json",
    "suite_status": "docs/audits/reviewer_suite_run_status.json",
    "lexical_human_baseline": "docs/audits/reviewer_historical_tfidf_human_metrics_v1.json",
    "historical_alignment_replay": "docs/audits/reviewer_legacy_alignment_replay.json",
}

PRIVATE_CHECKS = {
    "frozen_original_alignment": "data/processed/07_alignment_pdot_ods_needs.parquet",
    "human_sample_master": "data/revision_private/validation/sample_master_private.csv",
    "human_coder_A": "data/revision_private/validation/coder_A_private.csv",
    "human_coder_B": "data/revision_private/validation/coder_B_private.csv",
    "descriptor_source_candidates": "data/revision_private/descriptor_inventory/descriptor_source_candidates_PRIVATE.json",
    "frozen_lexical_scores": "data/revision_private/reviewer_historical_tfidf_human_metrics_v1/historical_source_tfidf_scores_PRIVATE.npz",
}

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=Path("docs/audits/round2_readiness.json"))
    args = parser.parse_args()
    original = args.project_root.expanduser().resolve()
    workspace = args.workspace.expanduser().resolve()
    if not original.is_dir():
        parser.error("The original HPC project directory is not accessible")
    if original == workspace or original in workspace.parents or workspace in original.parents:
        parser.error("Original project and revision workspace must be separate directories")
    output = (workspace / args.output).resolve()
    allowed = (workspace / "docs/audits").resolve()
    if output.parent != allowed or output.suffix != ".json":
        parser.error("Output must be a JSON directly inside docs/audits")
    if output.exists():
        parser.error("Output exists: move/archive after review; no silent overwrite")
    public = {key: {"present": (workspace / rel).is_file(), "not_content_verified": True}
              for key, rel in PUBLIC_REPORTS.items()}
    private = {key: {"present_on_HPC": (original / rel).is_file() if key == "frozen_original_alignment"
                       else (workspace / rel).is_file()}
               for key, rel in PRIVATE_CHECKS.items()}
    report = {
        "schema_version": 1,
        "purpose": "Sustainability second-round readiness; presence checks only",
        "public_report_status": public,
        "private_input_status": private,
        "interpretation": [
            "Presence is not evidence of successful execution, scientific validity, or public-release approval.",
            "No PDF, thesis text, student/advisor record, annotation, prediction, embedding, private path or raw log was exported.",
            "All aggregate JSON reports require individual disclosure and scientific review before GitHub publication.",
            "Missing results may exist under alternative paths or may not have been committed."
        ]
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Readiness status written:", output.relative_to(workspace))
    for key, state in public.items():
        print("PUBLIC", key, "PRESENT" if state["present"] else "MISSING")
    for key, state in private.items():
        print("PRIVATE", key, "PRESENT" if state["present_on_HPC"] else "NOT_FOUND_AT_EXPECTED_PATH")
    print("Review output manually before any git add/commit/push.")

if __name__ == "__main__":
    main()
