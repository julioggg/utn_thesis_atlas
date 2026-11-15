#!/usr/bin/env python3
"""READ-ONLY audit of the completed private 450-thesis expert consensus XLSX.

Checks the complete frozen A/B/C roster and every immutable comparison cell
against regenerated PRIVATE source data. Reports missing/invalid expert
judgments, without filling gaps, importing any decision or computing E5
accuracy. The original workbook may be partially completed. Expert signoff
and PDOT codebook/document provenance are separate scientific prerequisites.

No identifiable individual row or expert rationale is written or printed.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from audit_uploaded_third_review_proposals import C_FIELDS, read_workbook_rows
from export_blinded_validation_workbooks import WORKSPACE
from import_blinded_validation_excel import read_xlsx_rows
from prepare_expert_consensus_450_workbook import FIELDS, EDITABLE, generate, PRIVATE
from prepare_thematic_adjudication_queue import load_csv

ODS={f"ODS {n}" for n in range(1,18)}
PDOT={f"PDOT {n}" for n in range(1,7)}

def workbook_rows(path):
    data=read_xlsx_rows(path,"ADJUDICACION_450")
    header=dict(data).get(5,{})
    observed=tuple(header.get(j,"").strip() for j in range(1,len(FIELDS)+1))
    if observed!=FIELDS:
        raise ValueError("Expert consensus columns are missing, reordered or altered")
    records=[]
    for row_idx,cells in data:
        if row_idx<6:continue
        if row_idx>455:raise ValueError("More than 450 expert review cases")
        values={key:cells.get(j,"").strip() for j,key in enumerate(FIELDS,1)}
        records.append(values)
    if len(records)!=450:
        raise ValueError(f"Expected 450 review records, found {len(records)}")
    if len({r["study_id"] for r in records})!=450:
        raise ValueError("Duplicate or missing frozen study IDs")
    return records

def source_unchanged(received,expected):
    expected_map={r["study_id"]:r for r in expected}
    if len(expected_map)!=450 or {r["study_id"] for r in received}!=set(expected_map):
        raise ValueError("Consensus workbook study IDs do not match 450 frozen cases")
    for row in received:
        original=expected_map[row["study_id"]]
        for field in FIELDS[:18]:
            # The Excel source is supposed to preserve the literal original
            # text; no normalization of evidence or labels is permitted.
            if row[field]!=str(original.get(field,"")):
                raise ValueError(
                    "One or more immutable expert-consensus columns differ "
                    "from original frozen A/B/C evidence; stop before import."
                )

def evaluate_final(row):
    problems=[]
    untouched=not any(row[k] for k in EDITABLE)
    if untouched:return "not_started", []
    for kind,allowed in (("sdg",ODS),("pdot",PDOT)):
        label=row[f"final_{kind}_primary"]
        no=row[f"final_{kind}_no_match"].lower()
        if no and no not in ("yes","no"):
            problems.append(f"{kind}_invalid_no_match_flag")
        if label and label not in allowed:
            problems.append(f"{kind}_invalid_primary")
        if no=="yes" and label:
            problems.append(f"{kind}_no_match_conflict")
    if problems:
        return "invalid", problems
    incomplete=any(
        row[f"final_{kind}_no_match"].lower() not in ("yes","no")
        or (row[f"final_{kind}_no_match"].lower()=="no"
            and not row[f"final_{kind}_primary"])
        for kind in ("sdg","pdot")
    )
    if incomplete or not row["final_expert_rationale"].strip() or not row["final_expert_name_and_date"].strip():
        return "in_progress", []
    return "complete", []

def audit(received,expected):
    source_unchanged(received,expected)
    status=Counter()
    issues=Counter()
    priority=Counter()
    for row in received:
        condition,problems=evaluate_final(row)
        status[condition]+=1
        priority[row["review_priority"]+"_"+condition]+=1
        issues.update(problems)
    return {
        "rows":len(received),
        "by_status":dict(status),
        "by_priority_and_status":dict(priority),
        "problem_reasons":dict(issues),
        "ready_for_separate_provenance_and_source_adjudication_gate":
            status["complete"]==450,
    }

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workbook",type=Path,default=Path(
        "data/revision_private/validation/CONSENSO_450_PARA_REVISION_EXPERTA_PRIVADO.xlsx"
    ))
    args=p.parse_args()
    workbook=args.workbook.expanduser().resolve()
    if not workbook.is_relative_to(PRIVATE):
        raise ValueError("Expert workbook must stay inside ignored private CEDIA data")
    if not workbook.is_file():
        raise FileNotFoundError(f"Expected private workbook: {workbook}")
    private=PRIVATE/"validation"
    master=load_csv(private/"sample_master_private.csv")
    a=load_csv(private/"coder_A_private.csv")
    b=load_csv(private/"coder_B_private.csv")
    queue=load_csv(private/"thematic_adjudication_queue_PRIVATE.csv")
    c=read_workbook_rows(
        PRIVATE/"Evaluador_C_Tematico_COMPLETADO_PROPUESTA.xlsx", C_FIELDS
    )
    baseline=generate(master,a,b,c,queue)
    current=workbook_rows(workbook)
    summary=audit(current,baseline)
    print("PRIVATE 450 THESIS EXPERT CONSENSUS -- READ ONLY")
    print("Frozen A/B/C source columns and case IDs: VERIFIED")
    print("Final decisions:",summary["by_status"])
    print("By review priority:",summary["by_priority_and_status"])
    print("Response consistency problems:",summary["problem_reasons"])
    if summary["ready_for_separate_provenance_and_source_adjudication_gate"]:
        print("All 450 final fields populated, BUT provenance, PDOT codebook,")
        print("source verification and expert signoff still need approval.")
    else:
        print("NOT READY FOR MODEL EVALUATION. Final human decisions incomplete.")
    print("No workbook or original annotations were changed.")
    print("No labels, thesis handles, evidence text or individual cases exported.")

if __name__=="__main__":
    main()
