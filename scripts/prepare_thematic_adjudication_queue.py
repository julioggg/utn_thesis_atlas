#!/usr/bin/env python3
"""Prepare PRIVATE expert adjudication queue from two completed thematic coders.

This is a protocol / discrepancy-management aid, NOT human accuracy,
truth labels or inter-rater reliability. Neither A nor B is changed.
CEDIA-only output: no automated E5 predictions, descriptors, source text,
sample strata or individual annotation content in public files.

A case is queued when primary/secondary ODS or PDOT labels differ, either
coder marked uncertain=yes, either reported no-match, or one coder's
free-text evidence indicates potential source ambiguity. The queue can
be reviewed by a third expert only AFTER A and B coding are frozen.
Adjudication fields remain empty; no evaluator decision is fabricated.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

from audit_annotation_progress import inspect_files
from export_blinded_validation_workbooks import WORKSPACE, safe_csv_value

CODES=("sdg_primary","sdg_secondary","sdg_no_match",
       "pdot_primary","pdot_secondary","pdot_no_match")
FIELDS=(
    "study_id","private_source_handle","reasons_for_review",
    "coder_A_sdg_primary","coder_B_sdg_primary",
    "coder_A_sdg_secondary","coder_B_sdg_secondary",
    "coder_A_sdg_no_match","coder_B_sdg_no_match",
    "coder_A_pdot_primary","coder_B_pdot_primary",
    "coder_A_pdot_secondary","coder_B_pdot_secondary",
    "coder_A_pdot_no_match","coder_B_pdot_no_match",
    "coder_A_uncertain","coder_B_uncertain",
    "coder_A_evidence","coder_B_evidence",
    "coder_A_notes","coder_B_notes",
    "adjudicator_sdg_primary","adjudicator_sdg_no_match",
    "adjudicator_pdot_primary","adjudicator_pdot_no_match",
    "adjudicator_evidence","adjudicator_uncertainty",
    "adjudicator_date_and_identity",
)
ADJUDICATION_FIELDS=FIELDS[-7:]

def load_csv(path):
    with path.open(newline="",encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))

def canonical(value):
    return str(value or "").removeprefix("'").strip()

def roster(master, a, b):
    if len(master)!=450 or len(a)!=450 or len(b)!=450:
        raise ValueError("Expected exact frozen 450-case roster")
    master_ids={row["study_id"]:canonical(row["handle_id"]) for row in master}
    if len(master_ids)!=450 or len(set(master_ids.values()))!=450:
        raise ValueError("Invalid frozen master sample")
    pair={}
    for label, rows in (("A",a),("B",b)):
        cases={}
        for row in rows:
            sid=row["study_id"]
            if sid in cases or sid not in master_ids:
                raise ValueError(f"Duplicate or unknown {label} study ID")
            if canonical(row["private_source_handle"])!=master_ids[sid]:
                raise ValueError(f"Wrong {label} source handle")
            cases[sid]=row
        if set(cases)!=set(master_ids):
            raise ValueError(f"{label} worksheet is not the full frozen roster")
        pair[label]=cases
    return master_ids,pair

def select_cases(master, a, b):
    ids, pair=roster(master,a,b)
    pending=[]
    reasons=Counter()
    for sid in sorted(ids):
        ra=pair["A"][sid]
        rb=pair["B"][sid]
        flags=[]
        if any(ra.get(x,"").strip()!=rb.get(x,"").strip()
               for x in ("sdg_primary","sdg_secondary","sdg_no_match")):
            flags.append("ods_disagreement")
        if any(ra.get(x,"").strip()!=rb.get(x,"").strip()
               for x in ("pdot_primary","pdot_secondary","pdot_no_match")):
            flags.append("pdot_disagreement")
        if any(row.get("uncertain","").strip().lower()=="yes"
               for row in (ra,rb)):
            flags.append("human_uncertainty")
        if any(row.get(field,"").strip().lower()=="yes"
               for row in (ra,rb)
               for field in ("sdg_no_match","pdot_no_match")):
            flags.append("explicit_no_match")
        if not flags:
            continue
        reasons.update(flags)
        result={
            "study_id":sid,
            "private_source_handle":ids[sid],
            "reasons_for_review":";".join(flags),
        }
        for label,row in (("A",ra),("B",rb)):
            for domain in ("sdg","pdot"):
                for field in ("primary","secondary","no_match"):
                    result[f"coder_{label}_{domain}_{field}"]=row[f"{domain}_{field}"]
            for name,field in (("uncertain","uncertain"),
                               ("evidence","brief_evidence"),
                               ("notes","coder_notes")):
                result[f"coder_{label}_{name}"]=row.get(field,"")
        result.update({x:"" for x in ADJUDICATION_FIELDS})
        pending.append(result)
    return pending,reasons

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--private-dir",type=Path,default=Path(
        "data/revision_private/validation"
    ))
    p.add_argument("--output",type=Path,default=Path(
        "data/revision_private/validation/"
        "thematic_adjudication_queue_PRIVATE.csv"
    ))
    a=p.parse_args()
    private_root=(WORKSPACE/"data/revision_private").resolve()
    private=a.private_dir.expanduser().resolve()
    output=a.output.expanduser().resolve()
    if not private.is_relative_to(private_root) or not output.is_relative_to(private_root):
        raise ValueError("All source annotations and adjudication output must stay private")
    if output.exists():
        raise FileExistsError("Existing private adjudication queue must never be overwritten")
    report=inspect_files(private)
    if not report["all_annotations_finished"] or any(
        report["coder_progress"][key]["invalid"]
        for key in ("A","B")
    ):
        raise ValueError("A/B human coding must be complete and structurally valid")
    master=load_csv(private/"sample_master_private.csv")
    coder_a=load_csv(private/"coder_A_private.csv")
    coder_b=load_csv(private/"coder_B_private.csv")
    pending,counts=select_cases(master,coder_a,coder_b)
    if not pending:
        print("No differences, uncertainty, or no-match decisions found.")
        print("No ground-truth or expert agreement inferred.")
        return
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("x",newline="",encoding="utf-8") as stream:
        writer=csv.DictWriter(stream,fieldnames=FIELDS,quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for row in pending:
            writer.writerow({k:safe_csv_value(row.get(k,"")) for k in FIELDS})
    print("PRIVATE A/B discrepancy and adjudication queue:",output)
    print("Cases queued:",len(pending),"of 450; reasons:",dict(counts))
    print("All adjudicator conclusions BLANK. No model predictions included.")
    print("Before interpreting as expert ground truth: document independence/provenance")
    print("and approve PDOT operational codebook. Do NOT commit this private CSV.")

if __name__=="__main__":
    main()
