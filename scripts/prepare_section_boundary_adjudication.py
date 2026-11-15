#!/usr/bin/env python3
"""Prepare PRIVATE adjudication roster for 80 human-reviewed thesis boundaries.

Only rows identified as needs_adjudication or invalid by the frozen
audit_section_boundary_review.assess_row are exported, never relabeled.
The source review remains immutable. Generated worksheet is exclusively in
git-ignored CEDIA data/, including identifiers, source handles, contexts,
human notes and independent adjudicator fields BLANK. A case's presence
does not imply an error in the evaluator's reasoning.

Do not use the roster to auto-trim thesis fulltext or claim validation.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

from audit_section_boundary_review import assess_row
from export_blinded_validation_workbooks import WORKSPACE


def make_adjudication_rows(rows):
    if len(rows)!=80 or len({x["review_id"] for x in rows})!=80:
        raise ValueError("Expected 80 unique original section-review IDs")
    result=[]
    counts=Counter()
    for item in rows:
        status,issues=assess_row(item)
        counts[status]+=1
        if status not in ("invalid","needs_adjudication"):
            continue
        row={key:item.get(key,"") for key in (
            "review_id","private_source_handle","sampling_stratum",
            "candidate_position_fraction","human_corrected_boundary_fraction",
            "human_heading_is_real_references_start",
            "human_tail_contains_scientific_contribution",
            "human_trim_from_boundary_safe","heading_line",
            "context_before","context_after","trailing_excerpt",
            "human_notes"
        )}
        row.update({
            "current_audit_status":status,
            "audit_reason_codes":";".join(issues),
            "adjudicator_independent_heading_status":"",
            "adjudicator_independent_boundary_fraction":"",
            "adjudicator_independent_tail_scientific_content":"",
            "adjudicator_independent_trim_safe":"",
            "adjudicator_reasoning_and_text_evidence":"",
            "adjudication_signed_date":"",
        })
        result.append(row)
    return result,counts


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--private-csv",type=Path,default=Path(
        "data/revision_private/section_boundary_review_v1/"
        "section_boundary_review_private.csv"
    ))
    p.add_argument("--output",type=Path,default=Path(
        "data/revision_private/section_boundary_review_v1/"
        "section_boundary_adjudication_PRIVATE.csv"
    ))
    a=p.parse_args()
    private=(WORKSPACE/"data/revision_private").resolve()
    source=a.private_csv.expanduser().resolve()
    output=a.output.expanduser().resolve()
    if not source.is_relative_to(private) or not output.is_relative_to(private):
        raise ValueError("Source and adjudication sheet must remain in private ignored revision/data/")
    if not source.is_file():
        raise FileNotFoundError("Original private 80-case review not found")
    if output.exists():
        raise FileExistsError("Private adjudication sheet exists; manual review required")
    if source==output:
        raise ValueError("Do not overwrite original review")
    with source.open("r",newline="",encoding="utf-8") as f:
        rows=list(csv.DictReader(f))
    pending,counts=make_adjudication_rows(rows)
    if not pending:
        print("No invalid or pending cases; no adjudication sheet created.")
        return
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("x",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(pending[0]))
        writer.writeheader()
        writer.writerows(pending)
    print("Private adjudication worksheet:",output)
    print("Cases:",len(pending),"| pending:",counts["needs_adjudication"],
          "| hard invalid:",counts["invalid"])
    print("Review IDs only:",", ".join(item["review_id"] for item in pending))
    print("All independent adjudicator fields are blank. Original review unchanged.")
    print("No PDF or source text modified, no automatic trimming approved.")
    print("Do NOT commit this private CSV to GitHub.")


if __name__=="__main__":
    main()
