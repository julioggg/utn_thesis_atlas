#!/usr/bin/env python3
"""Safely preflight 47 human adjudications and freeze 450 expert reference only with signoff.

Cross-check uploaded private 47-case Excel against original frozen A/B study
IDs, source handles, original labels and 47 EXACT main-label conflicts.
On dry-run NEVER writes. --apply requires signed committee ratification JSON
and a separate signed committee record plus approved PDOT codebook.

47 conflicts use final K:N labels. Other 403 use agreed A=B primary labels
only if the committee explicitly approves that policy. Individual A/B/C
workbooks, original 47 XLSX and frozen 450 source CSV remain immutable.
This does not adjudicate secondary labels or generate machine accuracy.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path
from audit_annotation_progress import inspect_files
from export_blinded_validation_workbooks import WORKSPACE
from import_blinded_validation_excel import read_xlsx_rows
from prepare_thematic_adjudication_queue import canonical, load_csv
from reviewer_three_coder_comparison import label

PRIVATE=(WORKSPACE/"data/revision_private").resolve()
FIELDS=("study_id","private_source_handle","sdg_primary","sdg_no_match",
        "pdot_primary","pdot_no_match","human_reference_basis","human_signoff_date")
HEADS=(
    "ID de tesis","Handle institucional","Conflicto ODS","Conflicto PDOT",
    "ODS A","ODS B","ODS C (contexto)","PDOT A","PDOT B",
    "PDOT C (contexto)","ODS FINAL","ODS sin correspondencia",
    "PDOT FINAL","PDOT sin correspondencia","Fundamento científico del acuerdo",
    "Sección / página consultada","Responsable / comité",
    "Fecha AAAA-MM-DD","ESTADO","Observaciones adicionales",
)
def sha256(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""): h.update(c)
    return h.hexdigest()

def sheet(path,name):
    return dict(read_xlsx_rows(path,name))

def read_47(path):
    rows=sheet(path,"ADJUDICACION_47")
    hdr=rows.get(5,{})
    if tuple(hdr.get(j,"").strip() for j in range(1,21))!=HEADS:
        raise ValueError("Changed original 47-case header")
    if set(rows)-{1,2,3,5} != set(range(6,53)):
        raise ValueError("Unexpected 47-case Excel data row range")
    recs=[{j:rows[i].get(j,"").strip() for j in range(1,21)} for i in range(6,53)]
    if len({r[1] for r in recs})!=47 or any(not r[2] for r in recs):
        raise ValueError("Duplicate review IDs or empty source handle")
    return recs

def safe_final(primary,flag,kind):
    good={f"ODS {n}" for n in range(1,18)} if kind=="sdg" else {
        f"PDOT {n}" for n in range(1,7)}
    f=flag.strip().lower()
    x=primary.strip().upper()
    if f not in ("yes","no"):raise ValueError("Missing or invalid no-match response")
    if f=="yes":
        if x:raise ValueError("No-match conflicts with label")
        return "", "yes"
    if x not in good:raise ValueError("Missing/invalid final label")
    return x,"no"

def excel_label(value):
    v=value.strip().upper()
    return "NONE" if v in ("NINGUNO","NONE","SIN CORRESPONDENCIA") else v

def build_reference(master,a,b,records):
    if any(len(x)!=450 for x in (master,a,b)):
        raise ValueError("Expected 450 rows in all frozen A/B sources")
    M={x["study_id"]:x for x in master}
    A={x["study_id"]:x for x in a}
    B={x["study_id"]:x for x in b}
    if any(len(x)!=450 for x in (M,A,B)) or set(A)!=set(M) or set(B)!=set(M):
        raise ValueError("Frozen A/B original ID set differs from master")
    for sid,x in M.items():
        for label_name,source in (("A",A),("B",B)):
            if canonical(source[sid]["private_source_handle"])!=canonical(x["handle_id"]):
                raise ValueError(label_name+" source handle does not match frozen sample")
    conflict={
        sid for sid in M
        if any(label(A[sid],t)!=label(B[sid],t) for t in ("sdg","pdot"))
    }
    source={r[1]:r for r in records}
    if set(source)!=conflict or len(conflict)!=47:
        raise ValueError("47-case workbook differs from frozen A/B primary conflicts")
    decisions={}
    count=Counter()
    for sid in sorted(conflict):
        r=source[sid]
        if canonical(r[2])!=canonical(M[sid]["handle_id"]):
            raise ValueError("47-case source handle changed")
        for i,desired in ((5,label(A[sid],"sdg")),(6,label(B[sid],"sdg")),
                          (8,label(A[sid],"pdot")),(9,label(B[sid],"pdot"))):
            if excel_label(r[i])!=desired:
                raise ValueError("Original A/B response was modified in review workbook")
        for i,kind in ((3,"sdg"),(4,"pdot")):
            expected="SÍ" if label(A[sid],kind)!=label(B[sid],kind) else "NO"
            if r[i].upper()!=expected:
                raise ValueError("Wrong 47-case disagreement flag")
        ods,on=safe_final(r[11],r[12],"sdg")
        pdot,pn=safe_final(r[13],r[14],"pdot")
        if any(not r[i].strip() for i in (15,16,17,18)):
            raise ValueError("47-case human adjudication lacks evidence/reviewer/date")
        try:date.fromisoformat(r[18])
        except ValueError as exc:raise ValueError("Review date must be ISO YYYY-MM-DD") from exc
        if r[19].strip().upper()!="LISTO":
            raise ValueError("47-case final response is not marked LISTO")
        if r[17].casefold() in ("comite de revisión fica","comité de revisión fica"):
            count["generic_committee_attribution"]+=1
        count["ods_no_match_47"]+=on=="yes"
        count["pdot_no_match_47"]+=pn=="yes"
        decisions[sid]=(ods,on,pdot,pn,r[18])
    ref=[]
    for x in master:
        sid=x["study_id"]
        if sid in decisions:
            ods,on,pdot,pn,when=decisions[sid]
            basis="committee_reviewed_ab_primary_conflict"
            count["conflict_rows"]+=1
        else:
            od=label(A[sid],"sdg")
            pd=label(A[sid],"pdot")
            if od!=label(B[sid],"sdg") or pd!=label(B[sid],"pdot"):
                raise ValueError("Disagreement outside 47 approved cases")
            ods,on=("", "yes") if od=="NONE" else (od,"no")
            pdot,pn=("", "yes") if pd=="NONE" else (pd,"no")
            basis="committee_policy_ab_primary_agreement"
            when=""
            count["agreement_rows"]+=1
        ref.append({
            "study_id":sid,"private_source_handle":canonical(x["handle_id"]),
            "sdg_primary":ods,"sdg_no_match":on,
            "pdot_primary":pdot,"pdot_no_match":pn,
            "human_reference_basis":basis,"human_signoff_date":when,
        })
    if count["conflict_rows"]!=47 or count["agreement_rows"]!=403:
        raise ValueError("Wrong 47/403 split")
    return ref,count

def require_ratification(manifest,workbook):
    if manifest is None:raise ValueError("--apply requires --ratification-record")
    m=Path(manifest).expanduser().resolve()
    if not m.is_relative_to(PRIVATE) or not m.is_file():
        raise ValueError("Ratification manifest must exist in private data")
    doc=json.loads(m.read_text(encoding="utf-8"))
    fields=("workbook_sha256","committee_signatories","ratified_at",
            "approve_47_reviewed_cases","approve_403_ab_primary_agreement_policy",
            "codebook_source_and_version","codebook_approved_by",
            "provenance_and_ai_assistance_explained","signed_minutes_private_file")
    if any(x not in doc for x in fields):
        raise ValueError("Missing ratification manifest field")
    if doc["workbook_sha256"]!=sha256(workbook):
        raise ValueError("The ratification manifest identifies another Excel")
    names=doc["committee_signatories"]
    if not isinstance(names,list) or not names or any(
        not isinstance(n,str) or len(n.split())<2 for n in names
    ):
        raise ValueError("Names of actual individual committee signatories required")
    try:date.fromisoformat(doc["ratified_at"])
    except (TypeError,ValueError) as exc:raise ValueError("Invalid ratification date") from exc
    if doc["approve_47_reviewed_cases"] is not True or (
        doc["approve_403_ab_primary_agreement_policy"] is not True
    ):
        raise ValueError("Explicit approval of both the 47 and 403 label decisions required")
    for key in ("codebook_source_and_version","codebook_approved_by",
                "provenance_and_ai_assistance_explained"):
        if not isinstance(doc[key],str) or len(doc[key].strip())<10:
            raise ValueError("Incomplete human ratification record: "+key)
    signed=(PRIVATE/doc["signed_minutes_private_file"]).resolve()
    if not signed.is_relative_to(PRIVATE) or not signed.is_file() or signed in (m,workbook):
        raise ValueError("Separate signed committee minutes missing from private CEDIA")
    return doc,m

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workbook",type=Path,required=True)
    p.add_argument("--ratification-record",type=Path)
    p.add_argument("--output",type=Path,default=Path(
        "data/revision_private/validation/adjudicated_human_reference_450_PRIVATE.csv"))
    p.add_argument("--apply",action="store_true")
    a=p.parse_args()
    workbook=a.workbook.expanduser().resolve()
    output=a.output.expanduser().resolve()
    if not workbook.is_file() or not workbook.is_relative_to(PRIVATE):
        raise ValueError("Input 47-case XLSX must be in ignored private data")
    if not output.is_relative_to(PRIVATE):
        raise ValueError("Private reference output must remain under data/revision_private")
    report=inspect_files(PRIVATE/"validation")
    if not report["all_annotations_finished"]:
        raise ValueError("A/B original 450 human codes not complete")
    master=load_csv(PRIVATE/"validation/sample_master_private.csv")
    A=load_csv(PRIVATE/"validation/coder_A_private.csv")
    B=load_csv(PRIVATE/"validation/coder_B_private.csv")
    ref,counts=build_reference(master,A,B,read_47(workbook))
    controls=sheet(workbook,"CONTROL_TECNICO")
    pending=any("PENDIENTE" in controls.get(i,{}).get(2,"").upper()
                for i in (9,10,11))
    print("47 conflict review integrity: PASS | counts:",dict(counts))
    print("47 review workbook SHA256:",sha256(workbook))
    print("Frozen original A/B and master: verified")
    if pending:
        print("Original CONTROL_TECNICO still states PENDIENTE: preserve, don't erase.")
        print("Require separate signed ratification record before final reference.")
    if not a.apply:
        print("READ-ONLY preflight complete. No data modified.")
        return
    ratification,rec=require_ratification(a.ratification_record,workbook)
    if output.exists():raise FileExistsError("Reference exists; never overwrite")
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("x",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS,quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(ref)
    print("HUMAN-APPROVED PRIVATE 450 REFERENCE WRITTEN:",output)
    print("Ratification record SHA256:",sha256(rec))
    print("Human signatories in record:",len(ratification["committee_signatories"]))
    print("No original reviewer source, thesis text or XLSX changed.")
    print("Never upload private CSV or signed minutes to GitHub public.")

if __name__=="__main__":
    main()
