#!/usr/bin/env python3
"""Descriptive 450-case A/B agreement and 201-case A/B/C triage from CEDIA.

READ ONLY on all inputs. Can write aggregate JSON to docs/audits and optional
PRIVATE disagreement workbook-compatible CSV under data/revision_private.
Never makes a human gold standard, adjudicates, recalibrates E5, or rewrites
the C workbook's explicit AI provenance notes.

The C cases were selected because A and B disagreed (including secondary
codes), were uncertain or used no-match: C agreement on 201 IS NOT a
population estimate. A/B 120 population-random are separately reported.
Third-review independence and AI-editing-only claims must be documented,
not inferred from workbook completion.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

import numpy as np

from export_blinded_validation_workbooks import WORKSPACE
from audit_uploaded_third_review_proposals import (
    PRIVATE_ROOT, FILES, C_FIELDS, read_workbook_rows, compare_roster,
    validate_thematic
)
from prepare_thematic_adjudication_queue import read_csv as _unused  # noqa: F401
from prepare_thematic_adjudication_queue import (
    load_csv, select_cases, canonical
)
from prepare_section_boundary_review import safe_csv_value
from reviewer_human_validation_metrics import agreement
from reviewer_shared import write_public, sha256_file

DOMAIN_CLS={"sdg":"ODS","pdot":"PDOT"}
TRIAGE_FIELDS=(
    "study_id","private_source_handle",
    "ods_three_way_status","pdot_three_way_status",
    "A_ods_primary","B_ods_primary","C_ods_primary",
    "A_pdot_primary","B_pdot_primary","C_pdot_primary",
    "A_ods_secondary","B_ods_secondary","C_ods_secondary",
    "A_pdot_secondary","B_pdot_secondary","C_pdot_secondary",
    "A_ods_no_match","B_ods_no_match","C_ods_no_match",
    "A_pdot_no_match","B_pdot_no_match","C_pdot_no_match",
    "A_uncertain","B_uncertain","C_uncertain",
    "A_evidence","B_evidence","C_evidence",
    "A_notes","B_notes","C_notes",
    "expert_consensus_ods_primary","expert_consensus_ods_no_match",
    "expert_consensus_pdot_primary","expert_consensus_pdot_no_match",
    "expert_consensus_reasoning","expert_consensus_approved_by_and_date"
)
EMPTY_FINAL=TRIAGE_FIELDS[-6:]


def label(row,domain):
    flag=str(row.get(f"{domain}_no_match") or "").strip().lower()
    primary=str(row.get(f"{domain}_primary") or "").strip().upper()
    if flag=="yes" and not primary:return "NONE"
    if flag not in ("","no") or not primary:
        raise ValueError("Missing or contradictory thematic primary label")
    if domain=="sdg" and primary not in {f"ODS {x}" for x in range(1,18)}:
        raise ValueError("Invalid thematic ODS primary")
    if domain=="pdot" and primary not in {f"PDOT {x}" for x in range(1,7)}:
        raise ValueError("Invalid thematic PDOT primary")
    return primary


def pattern(x,y,z):
    if x==y==z:return "all_three_same"
    if x==y:return "a_b_same_c_differs"
    if x==z:return "a_c_same_b_differs"
    if y==z:return "b_c_same_a_differs"
    return "all_three_differ"


def comparison(master,a,b,c,queue):
    """Pure structured-data calculator; source IDs stay out of public output."""
    n=len(master)
    if n!=450 or len(a)!=450 or len(b)!=450:
        raise ValueError("Frozen A/B sample must contain 450 cases")
    ordered_master={row["study_id"]:row for row in master}
    if len(ordered_master)!=450:
        raise ValueError("Duplicate frozen master ID")
    A={row["study_id"]:row for row in a}
    B={row["study_id"]:row for row in b}
    C={row["study_id"]:row for row in c}
    Q={row["study_id"]:row for row in queue}
    if (
        len(A)!=450 or len(B)!=450 or len(C)!=len(c) or len(Q)!=len(queue) or
        set(A)!=set(ordered_master) or set(B)!=set(ordered_master) or
        set(C)!=set(Q)
    ):
        raise ValueError("One or more frozen A/B/C ID rosters disagree")
    for sid,row in ordered_master.items():
        handle=canonical(row["handle_id"])
        if canonical(A[sid]["private_source_handle"])!=handle or (
            canonical(B[sid]["private_source_handle"])!=handle
        ):
            raise ValueError("Frozen human A/B source handles differ")
        if sid in C and canonical(C[sid]["private_source_handle"])!=handle:
            raise ValueError("C source handle differs from original master")
    masks={
        "all_frozen_450":list(ordered_master),
        "population_random_120":[k for k,row in ordered_master.items()
                                 if row["selection_stratum"]=="population_random"],
        "targeted_enrichment_330":[k for k,row in ordered_master.items()
                                   if row["selection_stratum"]=="targeted_enrichment"],
    }
    if len(masks["population_random_120"])!=120 or len(masks["targeted_enrichment_330"])!=330:
        raise ValueError("Expected independently frozen 120 random and 330 enriched cases")
    result={
        "n_frozen":450,
        "n_c_selected":len(C),
        "sampling_split":{"population_random":120,"targeted_enrichment":330},
        "a_b_primary_inter_rater":{},
        "c_selected_201_patterns":{},
        "c_selected_201_selection_is_nonrepresentative":True,
    }
    triage=[]
    for dom,prefix in (("ods","sdg"),("pdot","pdot")):
        splits={}
        for stratum,ids in masks.items():
            av=np.asarray([label(A[k],prefix) for k in ids],dtype=str)
            bv=np.asarray([label(B[k],prefix) for k in ids],dtype=str)
            splits[stratum]=agreement(av,bv)
            splits[stratum]["disagreement_n"]=int(np.count_nonzero(av!=bv))
        result["a_b_primary_inter_rater"][dom]=splits
        counts=Counter(
            pattern(label(A[k],prefix),label(B[k],prefix),label(C[k],prefix))
            for k in C
        )
        result["c_selected_201_patterns"][dom]={
            key:counts[key] for key in (
                "all_three_same","a_b_same_c_differs",
                "a_c_same_b_differs","b_c_same_a_differs",
                "all_three_differ"
            )
        }
        result["c_selected_201_patterns"][dom]["n"]=len(C)
        result["c_selected_201_patterns"][dom]["not_ground_truth"]=True

    for sid in sorted(C):
        ra,rb,rc=A[sid],B[sid],C[sid]
        row={
            "study_id":sid,"private_source_handle":canonical(ra["private_source_handle"]),
            "ods_three_way_status":pattern(label(ra,"sdg"),label(rb,"sdg"),label(rc,"sdg")),
            "pdot_three_way_status":pattern(label(ra,"pdot"),label(rb,"pdot"),label(rc,"pdot"))
        }
        for letter,entry in (("A",ra),("B",rb),("C",rc)):
            for domain in ("ods","pdot"):
                pref="sdg" if domain=="ods" else "pdot"
                for field in ("primary","secondary","no_match"):
                    row[f"{letter}_{domain}_{field}"]=entry[f"{pref}_{field}"]
            row[f"{letter}_uncertain"]=entry.get("uncertain","")
            row[f"{letter}_evidence"]=entry.get("brief_evidence","")
            row[f"{letter}_notes"]=entry.get("coder_notes","")
        row.update({k:"" for k in EMPTY_FINAL})
        triage.append(row)
    return result,triage


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--c-workbook",type=Path,default=Path(
        "data/revision_private/Evaluador_C_Tematico_COMPLETADO_PROPUESTA.xlsx"
    ))
    parser.add_argument("--output",type=Path,default=Path(
        "docs/audits/reviewer_ab_c_primary_agreement_descriptive.json"
    ))
    parser.add_argument("--private-triage",type=Path,default=Path(
        "data/revision_private/validation/three_coder_comparison_PRIVATE.csv"
    ))
    args=parser.parse_args()
    workbook=args.c_workbook.expanduser().resolve()
    if not workbook.is_relative_to(PRIVATE_ROOT):
        raise ValueError("C source workbook must remain in private CEDIA data")
    out=args.private_triage.expanduser().resolve()
    if not out.is_relative_to(PRIVATE_ROOT):
        raise ValueError("Triage rows must remain in private data")
    if out.exists():
        raise FileExistsError("Existing private triage cannot be overwritten")
    source=PRIVATE_ROOT/"validation"
    master=load_csv(source/"sample_master_private.csv")
    a=load_csv(source/"coder_A_private.csv")
    b=load_csv(source/"coder_B_private.csv")
    queue=load_csv(source/"thematic_adjudication_queue_PRIVATE.csv")
    c=read_workbook_rows(workbook,C_FIELDS)
    compare_roster(c,queue,"study_id","C")
    flags=validate_thematic(c)
    aggregate,rows=comparison(master,a,b,c,queue)
    aggregate["schema_version"]=1
    aggregate["status"]="descriptive_three_coder_label_agreement_not_adjudicated"
    aggregate["c_original_excel_sha256"]=sha256_file(workbook)
    aggregate["c_workbook_self_declared_ai_assistance_n"]=flags[
        "self_declared_automated_assistance"]
    aggregate["c_human_authorship_clarification_reported"]=True
    aggregate["c_authorship_clarification_independently_verified"]=False
    aggregate["adjudication_or_model_validation_performed"]=False
    aggregate["notes"]=[
        "The coordinator reports reviewers assert human judgement with AI used for formatting/writing.",
        "Original C sheets explicitly state AI assistance/nonhuman third review. These contradictory provenance records have NOT been erased.",
        "C cases were flagged based on A/B discrepancy, uncertainty or no-match; their agreement is conditional and not population-generalizable.",
        "Agreement and Cohen kappa are properties of annotators, NOT machine model accuracy.",
        "No final reference or consensus labels have been entered in the private triage file.",
        "Source PDOT analytic-to-official policy correspondence and written provenance addenda remain pending."
    ]
    if rows:
        out.parent.mkdir(parents=True,exist_ok=True)
        with out.open("x",newline="",encoding="utf-8") as f:
            writer=csv.DictWriter(f,fieldnames=TRIAGE_FIELDS,quoting=csv.QUOTE_ALL)
            writer.writeheader()
            for row in rows:
                writer.writerow({key:safe_csv_value(row.get(key,"")) for key in TRIAGE_FIELDS})
    dest=write_public(aggregate,args.output,WORKSPACE)
    print("Privacy-controlled A/B primary inter-rater and C conditional comparison:",dest)
    print("PRIVATE triage (all consensus fields EMPTY):",out)
    for domain in ("ods","pdot"):
        print(domain.upper())
        for group,r in aggregate["a_b_primary_inter_rater"][domain].items():
            print(" ",group, "| n:",r["n"],"| agreement:",r["observed_agreement"],
                  "| Cohen kappa:",r["cohen_kappa"])
        print(" C conditional 3-way patterns:",aggregate["c_selected_201_patterns"][domain])
    print("No C results automatically adjudicated and NO model accuracy computed.")
    print("Three-way C provenance status remains contradictory pending signed clarification.")


if __name__=="__main__":
    main()
