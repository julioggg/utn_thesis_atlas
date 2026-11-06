#!/usr/bin/env python3
"""Build a PRIVATE section-boundary verification sheet for original UTN theses.

Read-only scan of thesis Parquet; only a four-stratum aggregate design report
can be published. Local CSV contains potentially sensitive source handles and
short thesis excerpts, therefore MUST remain in revision/data/ (git-ignored).

Does NOT alter the already selected 450-thesis independent coding sample.
Does NOT cut or filter any thesis texts.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from audit_thesis_structure import PATTERNS, analyze_text


STRATA = (
    "late_reference_with_appendix",
    "late_reference_without_appendix",
    "early_reference_only",
    "no_reference_heading",
)


def stratum_of(report):
    if report["late_reference"]:
        return (
            "late_reference_with_appendix" if report["appendix_after_reference"]
            else "late_reference_without_appendix"
        )
    if report["early_reference_only"]:
        return "early_reference_only"
    return "no_reference_heading"


def scan_strata(parquet, excluded_handles, min_late_fraction):
    import pyarrow.parquet as pq
    data = pq.ParquetFile(parquet)
    if not {"full_text", "handle_id"}.issubset(data.schema_arrow.names):
        raise ValueError("Original 04 corpus requires full_text and handle_id columns")
    slots = {k: [] for k in STRATA}
    counts = Counter()
    missing_handles = 0
    duplicated_handles = set()
    seen_handles = set()
    index = 0
    for batch in data.iter_batches(columns=["handle_id", "full_text"], batch_size=24):
        ids = batch.column(0)
        texts = batch.column(1)
        for offset in range(batch.num_rows):
            val = ids[offset].as_py()
            if val is None or not str(val).strip():
                missing_handles += 1
                index += 1
                continue
            handle = str(val).strip()
            if handle in seen_handles:
                duplicated_handles.add(handle)
            seen_handles.add(handle)
            report = analyze_text(texts[offset].as_py() or "", min_late_fraction)
            key = stratum_of(report)
            counts[key] += 1
            if handle not in excluded_handles:
                slots[key].append(index)
            index += 1
    if index != data.metadata.num_rows:
        raise RuntimeError("Streamed rows do not match original corpus metadata")
    if missing_handles or duplicated_handles:
        raise ValueError("Source has missing or duplicated handles; cannot create safe review sample")
    return slots, dict(counts), index


def choose_rows(slots, per_stratum, seed):
    import numpy as np
    rng = np.random.default_rng(seed)
    chosen = {}
    for key in STRATA:
        options = slots[key]
        if len(options) < per_stratum:
            raise ValueError(
                f"Not enough eligible documents in {key}: "
                f"{len(options)} < {per_stratum}"
            )
        chosen[key] = sorted(
            int(x) for x in rng.choice(options, size=per_stratum, replace=False)
        )
    all_rows = [r for v in chosen.values() for r in v]
    if len(all_rows) != len(set(all_rows)):
        raise AssertionError("Section review sample contains duplicate documents")
    return chosen


def get_selected_texts(parquet, indices):
    import pyarrow.parquet as pq
    wanted = set(indices)
    found = {}
    dataset = pq.ParquetFile(parquet)
    index = 0
    for batch in dataset.iter_batches(columns=["handle_id", "full_text"], batch_size=32):
        for j in range(batch.num_rows):
            if index in wanted:
                found[index] = (
                    batch.column(0)[j].as_py(), batch.column(1)[j].as_py() or ""
                )
            index += 1
        if len(found) == len(wanted):
            break
    if set(found) != wanted:
        raise RuntimeError("Failed to retrieve all selected full texts")
    return found


def candidate_context(text, min_late_fraction):
    """Short nearby snippets for human inspection; PRIVATE ONLY."""
    if not text:
        return {
            "candidate_position_fraction": "",
            "heading_line": "", "context_before": "", "context_after": "",
            "trailing_excerpt": "",
        }
    n = len(text)
    all_matches = list(PATTERNS["references"].finditer(text))
    plausible = [
        m for m in all_matches
        if min_late_fraction <= m.start() / n <= 0.99
    ]
    chosen = plausible[-1] if plausible else (all_matches[-1] if all_matches else None)
    if chosen is None:
        point = int(n * 0.80)
        return {
            "candidate_position_fraction": "",
            "heading_line": "",
            "context_before": text[max(0, point - 300):point],
            "context_after": text[point:min(n, point + 600)],
            "trailing_excerpt": text[max(0, n - 300):],
        }
    return {
        "candidate_position_fraction": f"{chosen.start() / n:.6f}",
        "heading_line": chosen.group(0).strip(),
        "context_before": text[max(0, chosen.start() - 300):chosen.start()],
        "context_after": text[chosen.end():min(n, chosen.end() + 600)],
        "trailing_excerpt": text[max(0, n - 300):],
    }


def safe_csv_value(value):
    text = "" if value is None else str(value)
    # Prevent spreadsheet formula interpretation without modifying original texts.
    return "'" + text if text and text.lstrip().startswith(("=", "+", "-", "@")) else text


def write_review_sheet(path, chosen, selected_texts, min_late_fraction):
    cols = [
        "review_id", "private_source_handle", "sampling_stratum",
        "extracted_fulltext_chars", "candidate_position_fraction",
        "heading_line", "context_before", "context_after", "trailing_excerpt",
        "human_heading_is_real_references_start",
        "human_corrected_boundary_fraction",
        "human_tail_contains_scientific_contribution",
        "human_trim_from_boundary_safe",
        "human_notes",
    ]
    with path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=cols, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        counter = 0
        for group in STRATA:
            for index in chosen[group]:
                counter += 1
                handle, text = selected_texts[index]
                record = {
                    "review_id": f"SB-{counter:04d}",
                    "private_source_handle": handle,
                    "sampling_stratum": group,
                    "extracted_fulltext_chars": len(text),
                    **candidate_context(text, min_late_fraction),
                    "human_heading_is_real_references_start": "",
                    "human_corrected_boundary_fraction": "",
                    "human_tail_contains_scientific_contribution": "",
                    "human_trim_from_boundary_safe": "",
                    "human_notes": "",
                }
                writer.writerow({key: safe_csv_value(record[key]) for key in cols})
    return counter


def read_excluded_handles(path):
    import pandas as pd
    if not path.is_file():
        raise FileNotFoundError(
            "Frozen 450-thesis private sample is required for exclusion"
        )
    master = pd.read_csv(
        path, usecols=["handle_id"], dtype={"handle_id": str},
        keep_default_na=False,
    )
    identifiers = set(master["handle_id"].str.strip().tolist())
    if len(master) != len(identifiers) or "" in identifiers:
        raise ValueError("Private 450-thesis master has duplicate or missing handles")
    return identifiers


def prepare(project, workspace, per_stratum, seed, min_late_fraction,
            private_output_dir, public_output):
    data_dir = (workspace / "data").resolve()
    private_dir = private_output_dir.expanduser().resolve()
    if not private_dir.is_relative_to(data_dir):
        raise ValueError("Private review sheets must stay under revision/data/")
    public_dest = public_output.expanduser().resolve()
    if not public_dest.is_relative_to((workspace / "docs/audits").resolve()):
        raise ValueError("Aggregate output must stay under revision/docs/audits/")
    private_path = private_dir / "section_boundary_review_private.csv"
    if private_path.exists() or public_dest.exists():
        raise FileExistsError(
            "Refusing to overwrite a previous review or audit. "
            "Choose a new output directory and report name."
        )
    excluded = read_excluded_handles(
        data_dir / "revision_private/validation/sample_master_private.csv"
    )
    corpus = project / "data/processed/04_clean_corpus.parquet"
    eligible, population_counts, population = scan_strata(corpus, excluded,
                                                          min_late_fraction)
    chosen = choose_rows(eligible, per_stratum, seed)
    selected = get_selected_texts(corpus, [x for v in chosen.values() for x in v])
    private_dir.mkdir(parents=True, exist_ok=True)
    number = write_review_sheet(private_path, chosen, selected, min_late_fraction)
    summary = {
        "schema_version": 1, "status": "boundary_review_prepared_unannotated",
        "source": "04_clean_corpus.parquet:full_text",
        "population_rows": population,
        "excluded_previously_selected_450_validation_rows": len(excluded),
        "method": "four-stratum purposive verification, NOT prevalence sampling",
        "random_seed": seed,
        "min_late_fraction": min_late_fraction,
        "strata_population_counts": population_counts,
        "strata_eligible_counts_after_exclusion": {
            key: len(eligible[key]) for key in STRATA
        },
        "private_review_records_total": number,
        "private_review_records_by_stratum": {
            key: len(chosen[key]) for key in STRATA
        },
        "manual_review_complete": False,
        "boundaries_approved_for_automatic_trimming": False,
        "notes": [
            "The study checks heading detection, not classifier performance.",
            "Each row contains private handle and short source excerpts; keep review CSV on CEDIA.",
            "Human reviewer must inspect full local theses and preserve potentially relevant appendices.",
            "Reviewers should not infer population prevalence from equally sampled strata.",
            "No original thesis file, extracted text, old embedding, or 450-thesis annotation template is modified.",
            "Only non-identifying aggregate sampling counts are written to docs/audits.",
        ],
    }
    public_dest.parent.mkdir(parents=True, exist_ok=True)
    public_dest.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root", type=Path, required=True)
    p.add_argument("--per-stratum", type=int, default=20)
    p.add_argument("--seed", type=int, default=20261106)
    p.add_argument("--late-fraction", type=float, default=.55)
    p.add_argument("--private-output-dir", type=Path,
                   default=Path("data/revision_private/section_boundary_review_v1"))
    p.add_argument("--output", type=Path,
                   default=Path("docs/audits/section_boundary_review_design.json"))
    args = p.parse_args()
    if not 1 <= args.per_stratum <= 50:
        p.error("per-stratum must be 1..50")
    if not 0.3 <= args.late_fraction <= 0.9:
        p.error("late-fraction must be between 0.3 and 0.9")
    workspace = Path(__file__).resolve().parent.parent
    report = prepare(
        args.project_root.expanduser().resolve(), workspace, args.per_stratum,
        args.seed, args.late_fraction, args.private_output_dir, args.output
    )
    print(f"Prepared {report['private_review_records_total']} private section reviews.")
    print("Excluded all 450 theses from the frozen validation sample.")
    print("Only the anonymous aggregate design JSON is a candidate for GitHub.")


if __name__ == "__main__":
    main()
