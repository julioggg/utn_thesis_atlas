#!/usr/bin/env python3
"""Audit PRIVATE human section-boundary reviews; export aggregate metrics only.

Reads the frozen 80-thesis private worksheet without changing it. Checks IDs,
strata, flags, boundary fractions, obvious logical contradictions and exclusion
of the separate 450-thesis thematic-validation sample. Does NOT infer that
unreviewed detected headings are correct or that text can be trimmed.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from prepare_section_boundary_review import STRATA

REQUIRED = {
    "review_id", "private_source_handle", "sampling_stratum",
    "candidate_position_fraction", "human_heading_is_real_references_start",
    "human_corrected_boundary_fraction",
    "human_tail_contains_scientific_contribution",
    "human_trim_from_boundary_safe", "human_notes",
}
FLAGS = ("human_heading_is_real_references_start",
         "human_tail_contains_scientific_contribution",
         "human_trim_from_boundary_safe")
ANSWERS = {"yes", "no", "uncertain"}


def parse_fraction(text, key):
    if not text.strip():
        return None
    try:
        number = float(text)
    except ValueError:
        raise ValueError(f"Invalid fraction in {key}") from None
    if not 0 <= number <= 1:
        raise ValueError(f"Out of range fraction in {key}")
    return number


def assess_row(row):
    """Return status and aggregate-only error codes; never include source content."""
    answers = {key: row.get(key, "").strip().lower() for key in FLAGS}
    issues = []
    for key, value in answers.items():
        if value not in ANSWERS | {""}:
            issues.append("invalid_" + key)
    try:
        candidate = parse_fraction(row["candidate_position_fraction"],
                                   "candidate_position_fraction")
        correction = parse_fraction(row["human_corrected_boundary_fraction"],
                                    "human_corrected_boundary_fraction")
    except ValueError:
        issues.append("invalid_boundary_fraction")
        candidate, correction = None, None
    if answers[FLAGS[0]] == "yes" and candidate is None:
        issues.append("candidate_marked_correct_without_candidate")
    if (answers[FLAGS[2]] == "yes" and
        (answers[FLAGS[0]] != "yes" or answers[FLAGS[1]] != "no")):
        issues.append("unsafe_trim_approval_conflict")
    if answers[FLAGS[0]] == "no" and correction is not None and candidate is not None:
        # A corrected position is allowed, but this needs explicit adjudication
        # before using the proposed heading in a preprocessing pipeline.
        issues.append("corrected_candidate_requires_adjudication")
    if issues:
        return "invalid", sorted(set(issues))
    if all(v == "" for v in answers.values()) and correction is None:
        return "not_started", []
    if any(v == "" for v in answers.values()):
        return "in_progress", []
    if any(v == "uncertain" for v in answers.values()):
        return "needs_adjudication", []
    return "reviewed", []


def summarize(private_csv, master_csv, expected_rows=80, expected_per_stratum=20):
    with private_csv.open(newline="", encoding="utf-8") as fp:
        reader = csv.DictReader(fp)
        if reader.fieldnames is None or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError("Review sheet has missing/duplicate header fields")
        if missing := REQUIRED - set(reader.fieldnames):
            raise ValueError("Review sheet lacks required columns: " + ", ".join(sorted(missing)))
        rows = list(reader)
    if len(rows) != expected_rows:
        raise ValueError("Unexpected number of boundary-review rows")
    with master_csv.open(newline="", encoding="utf-8") as fp:
        master = csv.DictReader(fp)
        if not master.fieldnames or "handle_id" not in master.fieldnames:
            raise ValueError("Missing private 450-thesis validation master handles")
        forbidden_handles = {
            (row.get("handle_id") or "").strip()
            for row in master
        }
    if not forbidden_handles or "" in forbidden_handles:
        raise ValueError("Validation master has missing handles")
    ids, handles = set(), set()
    counters = {stratum: Counter() for stratum in STRATA}
    total_issues = Counter()
    flag_counts = {key: Counter() for key in FLAGS}
    per_stratum_total = Counter()
    for row in rows:
        rid = (row["review_id"] or "").strip()
        handle = (row["private_source_handle"] or "").strip()
        if handle.startswith("'"):
            handle = handle[1:]
        stratum = (row["sampling_stratum"] or "").strip()
        if not rid or rid in ids or not handle or handle in handles:
            raise ValueError("Missing or repeated restricted source/review ID")
        ids.add(rid)
        handles.add(handle)
        if stratum not in STRATA:
            raise ValueError("Unknown section-review stratum")
        if handle in forbidden_handles:
            raise ValueError("Section-review sample overlaps 450-thesis thematic validation")
        per_stratum_total[stratum] += 1
        status, issues = assess_row(row)
        counters[stratum][status] += 1
        total_issues.update(issues)
        if status == "reviewed":
            for field in FLAGS:
                flag_counts[field][row[field].strip().lower()] += 1
    if any(per_stratum_total[key] != expected_per_stratum for key in STRATA):
        raise ValueError("Unexpected sample size in at least one stratum")
    reviewed = sum(count["reviewed"] for count in counters.values())
    return {
        "schema_version": 1,
        "status": "section_boundary_review_progress",
        "sample_rows": len(rows),
        "sample_integrity": "passed",
        "excluded_450_thematic_validation_overlap": True,
        "sample_design": "balanced purposive strata; not a representative prevalence estimator",
        "total_reviewed": reviewed,
        "total_not_started": sum(c["not_started"] for c in counters.values()),
        "total_in_progress": sum(c["in_progress"] for c in counters.values()),
        "total_needs_adjudication": sum(c["needs_adjudication"] for c in counters.values()),
        "total_invalid": sum(c["invalid"] for c in counters.values()),
        "by_stratum": {
            key: {
                "sample_rows": per_stratum_total[key],
                "reviewed": counters[key]["reviewed"],
                "not_started": counters[key]["not_started"],
                "in_progress": counters[key]["in_progress"],
                "needs_adjudication": counters[key]["needs_adjudication"],
                "invalid": counters[key]["invalid"],
            }
            for key in STRATA
        },
        "reviewed_answer_counts": {
            key: {answer: flag_counts[key][answer] for answer in ("yes", "no")}
            for key in FLAGS
        },
        "validation_issue_counts": dict(sorted(total_issues.items())),
        "manual_review_complete": (
            reviewed == len(rows) and not total_issues
        ),
        "boundaries_approved_for_automatic_trimming": False,
        "limitations": [
            "No thesis-specific IDs, positions, excerpts, notes or raw answers are exported.",
            "Even if human reviewers approve boundaries, automation requires a separately frozen, validated extraction protocol.",
            "No label/accuracy metrics can be claimed before sufficient independent validation.",
            "Strata were sampled equally; pooled proportions are not unbiased population prevalence estimates.",
            "Without manually verified negatives and positives across all cases, recall cannot be inferred from heading counts.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-csv", type=Path, default=Path(
        "data/revision_private/section_boundary_review_v1/section_boundary_review_private.csv"
    ))
    parser.add_argument("--validation-master", type=Path, default=Path(
        "data/revision_private/validation/sample_master_private.csv"
    ))
    parser.add_argument("--output", type=Path, default=Path(
        "docs/audits/section_boundary_review_progress.json"
    ))
    parser.add_argument("--expected-rows", type=int, default=80)
    parser.add_argument("--expected-per-stratum", type=int, default=20)
    a = parser.parse_args()
    workspace = Path(__file__).resolve().parent.parent
    private_base = (workspace / "data").resolve()
    csv_path = a.private_csv.expanduser().resolve()
    master = a.validation_master.expanduser().resolve()
    report_path = a.output.expanduser().resolve()
    if not csv_path.is_relative_to(private_base) or not master.is_relative_to(private_base):
        raise ValueError("Private inputs must stay under revision/data/")
    if not report_path.is_relative_to((workspace / "docs/audits").resolve()):
        raise ValueError("Aggregate report must stay under docs/audits/")
    if a.expected_rows <= 0 or a.expected_per_stratum <= 0:
        parser.error("Expected row counts must be positive")
    result = summarize(csv_path, master, a.expected_rows, a.expected_per_stratum)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(f"Integrity OK: {result['sample_rows']} private section reviews; "
          f"overlap with 450-thesis evaluation: none.")
    print(f"Reviewed={result['total_reviewed']}, "
          f"not_started={result['total_not_started']}, "
          f"in_progress={result['total_in_progress']}, "
          f"needs_adjudication={result['total_needs_adjudication']}, "
          f"invalid={result['total_invalid']}.")
    print("Public-safe aggregate progress report:", report_path)


if __name__ == "__main__":
    main()
