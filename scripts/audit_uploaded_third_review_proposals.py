#!/usr/bin/env python3
"""READ-ONLY intake and scientific provenance gate for uploaded C review Excel files.

CEDIA source paths are exactly the unrenamed files in ignored
data/revision_private/. Validates the current frozen A/B thematic discrepancy
queue and structural adjudication queue, workbook schema, row uniqueness,
allowed response codes, no-match consistency, substantive notes and
independence/assisted-proposal disclosures.

IMPORTANT: These two uploaded files explicitly identify their content as
AI-assisted. Format matching is not an independent human review. This script
NEVER imports decisions into a human gold standard, changes A/B CSVs, changes
C spreadsheets, changes any original text, or approves automatic trimming.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

from export_blinded_validation_workbooks import WORKSPACE
from export_third_reviewer_blinded_packets import C_FIELDS, S_FIELDS
from import_blinded_validation_excel import read_xlsx_rows

PRIVATE_ROOT = (WORKSPACE / "data/revision_private").resolve()
FILES = {
    "thematic": "Evaluador_C_Tematico_COMPLETADO_PROPUESTA.xlsx",
    "structural": "Evaluador_C_Estructural_COMPLETADO_PROPUESTA.xlsx",
}
EXPECTED_C_SHEET = "Evaluación C"
ODS = {f"ODS {i}" for i in range(1,18)}
PDOT = {f"PDOT {i}" for i in range(1,7)}
DISCLOSURE = re.compile(
    r"\bIA\b|\bClaude\b|\bChatGPT\b|\bGPT\b|"
    r"no tercera evaluaci[oó]n humana independiente|"
    r"codificaci[oó]n asistida", re.I
)
HEADLINE_CONTRADICTION = re.compile(
    r"candidato.{0,80}(?:bibliograf[ií]a local|no (?:es|corresponde)|"
    r"anexo|gu[ií]a)|\bno [eé]s el inicio\b", re.I | re.S
)


def read_csv(path):
    with path.open("r",newline="",encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def normalized(value):
    return str(value or "").strip().removeprefix("'")


def hash_file(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()


def read_workbook_rows(path, headers):
    rows=read_xlsx_rows(path, EXPECTED_C_SHEET)
    index=dict(rows)
    if tuple(index.get(5,{}).get(j,"") for j in range(1,len(headers)+1))!=tuple(headers):
        raise ValueError(f"{path.name}: header order is not the frozen C workbook schema")
    records=[]
    for number,cells in rows:
        if number<6:continue
        if number>10000:
            raise ValueError("Unexpected Excel row range")
        record={key:cells.get(j,"").strip() for j,key in enumerate(headers,1)}
        if not record[headers[0]]:raise ValueError("Empty C review ID")
        records.append(record)
    return records


def compare_roster(rows, queue, id_field, file_suffix):
    if len(rows)!=len(queue) or not rows:
        raise ValueError(f"{file_suffix}: expected {len(queue)} records, received {len(rows)}")
    expectation={r[id_field]:normalized(r["private_source_handle"]) for r in queue}
    if len(expectation)!=len(queue):
        raise ValueError("Frozen adjudication queue has duplicate IDs")
    current={r[id_field]:normalized(r["private_source_handle"]) for r in rows}
    if len(current)!=len(rows) or expectation!=current:
        raise ValueError(f"{file_suffix}: C case IDs or source handles do not match frozen queue")
    for row in rows:
        expected=f"Evidencias/{row[id_field]}.txt"
        if row["documento_local"]!=expected:
            raise ValueError(f"{file_suffix}: C evidence path differs from frozen ID")


def validate_thematic(rows):
    result=Counter()
    errors=Counter()
    for row in rows:
        for domain,valid in (("sdg",ODS),("pdot",PDOT)):
            primary=row[f"{domain}_primary"]
            secondary=row[f"{domain}_secondary"]
            no_match=row[f"{domain}_no_match"].lower()
            if no_match not in ("yes","no"):
                errors[f"{domain}_blank_or_invalid_no_match"]+=1
            if primary and primary not in valid:
                errors[f"{domain}_invalid_primary"]+=1
            if secondary and secondary not in valid:
                errors[f"{domain}_invalid_secondary"]+=1
            if secondary and (not primary or secondary==primary):
                errors[f"{domain}_invalid_secondary_structure"]+=1
            if no_match=="yes":
                result[f"{domain}_no_match"]+=1
                if primary or secondary:
                    errors[f"{domain}_no_match_conflict"]+=1
            elif not primary:
                errors[f"{domain}_missing_primary"]+=1
        if row["uncertain"] not in ("yes","no"):
            errors["uncertainty_missing_or_invalid"]+=1
        if not row["brief_evidence"].strip():
            errors["missing_document_evidence"]+=1
        if not row["reviewer_identity_date"].strip():
            errors["missing_reviewer_identity_date"]+=1
        if DISCLOSURE.search(row["coder_notes"]+" "+row["reviewer_identity_date"]):
            result["self_declared_automated_assistance"]+=1
        if "NO tercera evaluación humana independiente" in row["coder_notes"]:
            result["explicit_nonhuman_proposal_claim"]+=1
        if row["brief_evidence"].lower().startswith("resumen:"):
            result["evidence_based_on_abstract_excerpt"]+=1
        if "Correspondencia temática inferida del objetivo y resumen" in row["coder_notes"]:
            result["repeated_inference_justification"]+=1
        if row["uncertain"]=="yes":
            result["uncertainty_yes"]+=1
    if errors:
        raise ValueError("C thematic invalid structured fields: "+str(dict(errors)))
    result["n_cases"]=len(rows)
    return result


def parse_fraction(value):
    if not value.strip():return None
    try:
        num=Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("C structural correction is not a decimal fraction") from exc
    if not num.is_finite() or not Decimal(0)<=num<=Decimal(1):
        raise ValueError("C structural correction outside 0..1")
    return num


def validate_structural(rows, frozen):
    by_id={r["review_id"]:r for r in frozen}
    result=Counter()
    warnings=[]
    errors=Counter()
    for r in rows:
        case_id=r["review_id"]
        original=by_id[case_id]
        candidate=parse_fraction(r["candidate_position_fraction"])
        original_candidate=parse_fraction(original["candidate_position_fraction"])
        if candidate!=original_candidate:
            raise ValueError("C candidate fraction disagrees with frozen structural queue")
        heading=r["independent_heading_is_real_references_start"].lower()
        tail=r["independent_tail_contains_scientific_contribution"].lower()
        trim=r["independent_trim_from_boundary_safe"].lower()
        correct=parse_fraction(r["independent_corrected_boundary_fraction"])
        if any(x not in ("yes","no","uncertain") for x in (heading,tail,trim)):
            errors["invalid_review_flag"]+=1
        if trim=="yes" and (heading!="yes" or tail!="no"):
            errors["unsafe_trim_approval_conflict"]+=1
        if not r["independent_notes_and_evidence"] or not r["reviewer_identity_date"]:
            errors["missing_evidence_or_reviewer_identity"]+=1
        if DISCLOSURE.search(r["reviewer_identity_date"]+" "+r["independent_notes_and_evidence"]):
            result["self_declared_automated_assistance"]+=1
        if tail=="yes":result["post_heading_scientific_content_yes"]+=1
        if trim=="yes":result["trim_safe_yes"]+=1
        if heading=="yes" and correct is not None and candidate is not None:
            if abs(correct-candidate)>=Decimal("0.05"):
                warnings.append({
                    "review_id":case_id,
                    "issue":"heading_yes_but_large_boundary_correction",
                })
        if heading=="yes" and HEADLINE_CONTRADICTION.search(r["independent_notes_and_evidence"]):
            warnings.append({
                "review_id":case_id,
                "issue":"heading_yes_but_notes_question_candidate",
            })
    if errors:raise ValueError("C structural invalid structured fields: "+str(dict(errors)))
    result["n_cases"]=len(rows)
    return result,warnings


def verify(root, incoming):
    private=root/"data/revision_private"
    base=incoming.expanduser().resolve()
    if not base.is_relative_to(private.resolve()):
        raise ValueError("Completed C files must remain in ignored private data")
    files={k:base/v for k,v in FILES.items()}
    for key,path in files.items():
        if not path.is_file():
            raise FileNotFoundError(f"{key}: expected exactly {path}")
    thematic_queue=read_csv(private/"validation/thematic_adjudication_queue_PRIVATE.csv")
    structural_queue=read_csv(private/"section_boundary_review_v1/section_boundary_adjudication_PRIVATE.csv")
    thematic=read_workbook_rows(files["thematic"],C_FIELDS)
    structural=read_workbook_rows(files["structural"],S_FIELDS)
    compare_roster(thematic,thematic_queue,"study_id","thematic")
    compare_roster(structural,structural_queue,"review_id","structural")
    t=validate_thematic(thematic)
    s,warnings=validate_structural(structural,structural_queue)
    return files,t,s,warnings


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--received-dir",type=Path,default=PRIVATE_ROOT)
    args=p.parse_args()
    files,thematic,structural,warnings=verify(WORKSPACE.resolve(),args.received_dir)
    print("PRIVATE C WORKBOOK INTAKE: READ-ONLY")
    for key,path in files.items():
        print(key, path.name,"| SHA-256",hash_file(path))
    print("Frozen case handles and evidence file ID associations: PASS")
    print("THEMATIC:",dict(thematic))
    print("STRUCTURAL:",dict(structural))
    print("Source-text check: not performed here; only pre-existing frozen identities checked")
    print("Structural notes/heading differences to inspect:",warnings)
    if thematic["self_declared_automated_assistance"] or structural["self_declared_automated_assistance"]:
        print("STATUS: AI_ASSISTED_PROPOSAL_NOT_INDEPENDENT_HUMAN_GROUND_TRUTH")
        print("PROVENANCE GATE: BLOCKED. Preserve original C Excel as proposals.")
        print("Do not import them as expert adjudication; do not compute model accuracy.")
    else:
        print("STATUS: FORMAT_CHECK_ONLY_NOT_HUMAN_CERTIFICATION")
        print("Proof of independent human review and PDOT codebook still required.")
    print("No source file, C workbook, human A/B answer or output report modified.")

if __name__=="__main__":
    main()
