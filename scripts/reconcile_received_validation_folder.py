#!/usr/bin/env python3
"""One-folder CEDIA intake for completed 450-case A/B + 80-case Excel reviews.

Default = READ-ONLY PRE-FLIGHT of the exact received filenames under
data/revision_private/validation/recibidos_sin_validar/.
No Excel copies, renames, changes or source-record modifications are made.

--apply A, B, or 80 imports ONE specific workbook after verifying its frozen
case IDs and source metadata. The underlying original importer creates a
private one-time backup and refuses to overwrite existing differing answers.
The 80-case audit may legitimately report pending adjudications.

A passed format/identity check is NOT evidence of human independence or
predictive accuracy. The original Excel responses remain private in CEDIA.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from export_blinded_validation_workbooks import ANNOTATION_FIELDS, BOUNDARY_FIELDS, WORKSPACE
from import_blinded_validation_excel import (
    ANSWERS, compare_input, extract_annotations,
    ingest as import_coder, read_csv as read_coder_csv
)
from import_section_boundary_excel import (
    FIELDS as STRUCTURAL_ANSWERS,
    ingest as import_structural, parse_boundary_excel,
    read_csv as read_structural_csv
)
from audit_section_boundary_review import assess_row

RECEIVED_RELATIVE = Path("data/revision_private/validation/recibidos_sin_validar")
FILE_NAMES = {
    "A": "Validacion_A_450_ODS_PDOT.xlsx",
    "B": "Validacion_450_ODS_PDOT_B.xlsx",
    "80": "Plantilla_revision_estructural_80_tesis_COMPLETA (1).xlsx",
}

def received_folder(root=WORKSPACE, incoming=None):
    root=Path(root).resolve()
    privacy=(root/"data/revision_private").resolve()
    chosen=(Path(incoming) if incoming is not None else root/RECEIVED_RELATIVE)
    chosen=chosen.expanduser().resolve()
    if not chosen.is_relative_to(privacy):
        raise ValueError("Received Excel folder must remain inside private ignored data")
    return chosen

def sha256_file(path):
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()

def source_identity(row):
    return (row.get("private_source_handle") or "").removeprefix("'")

def preflight_coder(letter, input_xlsx, root=WORKSPACE):
    private=Path(root)/"data/revision_private/validation"
    expected=read_coder_csv(private/f"coder_{letter}_private.csv")
    master=read_coder_csv(private/"sample_master_private.csv")
    if len(master)!=450 or len({x["study_id"] for x in master})!=450:
        raise ValueError("Frozen thematic master must contain 450 unique IDs")
    frozen={x["study_id"]:x["handle_id"] for x in master}
    if len(set(frozen.values()))!=450 or not all(frozen.values()):
        raise ValueError("Frozen thematic master has missing or duplicate handles")
    rows=extract_annotations(input_xlsx,letter)
    modifications,answered,_,_=compare_input(expected,rows)
    if any(frozen.get(x["study_id"])!=source_identity(x) for x in rows):
        raise ValueError("Incoming workbook disagrees with frozen 450-thesis master")
    complete=0
    no_match=Counter()
    for row in rows:
        for kind in ("sdg","pdot"):
            if row[f"{kind}_no_match"]=="yes": no_match[kind]+=1
        if (row["sdg_primary"] or row["sdg_no_match"]=="yes") and (
            row["pdot_primary"] or row["pdot_no_match"]=="yes"
        ) and row["uncertain"] in ("yes","no") and row["brief_evidence"]:
            complete+=1
    return {
        "type":"thematic_blinded_coder",
        "coder":letter,
        "received_filename":input_xlsx.name,
        "size_bytes":input_xlsx.stat().st_size,
        "file_sha256":sha256_file(input_xlsx),
        "frozen_ids_and_source_handles":"verified",
        "cases":len(rows),
        "complete_by_required_fields":complete,
        "not_complete_by_required_fields":450-complete,
        "nonblank_response_cells":answered,
        "new_or_modified_blank_answer_cells":modifications,
        "explicit_no_match_counts":dict(no_match),
        "import_shape_compatible":True,
        "human_independence_or_provenance_verified":False,
        "human_validation_accuracy_computed":False,
    }

def preflight_structural(input_xlsx, root=WORKSPACE):
    private=Path(root)/"data/revision_private"
    originals=read_structural_csv(
        private/"section_boundary_review_v1/section_boundary_review_private.csv"
    )
    master=read_coder_csv(private/"validation/sample_master_private.csv")
    rows=parse_boundary_excel(input_xlsx)
    if len(originals)!=80 or len(master)!=450:
        raise ValueError("Frozen structural or thematic sample has incorrect size")
    expected={x["review_id"]:x for x in originals}
    given={x["review_id"]:x for x in rows}
    if len(expected)!=80 or set(expected)!=set(given):
        raise ValueError("Structural review IDs are not the frozen 80-case sample")
    restricted={x["handle_id"] for x in master}
    counts=Counter()
    changes=0
    for rid,original in expected.items():
        row=given[rid]
        for field in BOUNDARY_FIELDS[:9]:
            former=(original.get(field) or "").strip()
            received=(row.get(field) or "").strip()
            if field=="private_source_handle":
                former=former.removeprefix("'")
                received=received.removeprefix("'")
            if former!=received:
                raise ValueError("Structural immutable row metadata differs: "+field)
        if source_identity(row) in restricted:
            raise ValueError("Structural document overlaps 450-case thematic sample")
        for field in STRUCTURAL_ANSWERS:
            previous=(original.get(field) or "").strip()
            current=row[field]
            if previous and previous!=current:
                raise ValueError("Cannot overwrite prior structural human answers")
            changes+=previous!=current
        status,_=assess_row(row)
        counts[status]+=1
    strata=Counter(x["sampling_stratum"] for x in rows)
    expected_strata={
        "late_reference_with_appendix",
        "late_reference_without_appendix",
        "early_reference_only",
        "no_reference_heading"
    }
    if set(strata)!=expected_strata or any(n!=20 for n in strata.values()):
        raise ValueError("Frozen structural sample must have 20 cases in each of 4 strata")
    return {
        "type":"section_boundary_human_review",
        "received_filename":input_xlsx.name,
        "size_bytes":input_xlsx.stat().st_size,
        "file_sha256":sha256_file(input_xlsx),
        "frozen_ids_and_source_handles":"verified",
        "cases":len(rows),
        "status_counts":{k:counts[k] for k in (
            "reviewed","needs_adjudication","invalid","in_progress","not_started"
        )},
        "new_or_modified_blank_answer_cells":changes,
        "import_shape_compatible":True,
        "complete_review_and_all_boundaries_approved":False,
        "automatic_reference_trimming_approved":False,
    }

def preflight_all(root=WORKSPACE, incoming=None):
    root=Path(root).resolve()
    folder=received_folder(root,incoming)
    if not folder.is_dir():
        raise FileNotFoundError(f"Missing received private folder: {folder}")
    report={}
    for key, filename in FILE_NAMES.items():
        file=folder/filename
        if not file.is_file():
            actual=sorted(p.name for p in folder.glob("*.xlsx"))
            raise FileNotFoundError(
                f"Expected exact filename not found: {filename}; received XLSX names: {actual}"
            )
        if not file.resolve().is_relative_to(folder):
            raise ValueError("Unexpected escaped source XLSX path")
        report[key]=(
            preflight_structural(file,root)
            if key=="80" else preflight_coder(key,file,root)
        )
    if report["A"]["file_sha256"]==report["B"]["file_sha256"]:
        raise ValueError("Thematic Excel A and B files are byte-for-byte identical")
    return folder,report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--received-dir",type=Path,default=None,
                   help="Optional private directory; defaults to fixed shared received folder")
    p.add_argument("--apply",choices=("A","B","80"),
                   help="Explicitly import ONE workbook after a full pre-flight")
    args=p.parse_args()
    folder,report=preflight_all(WORKSPACE,args.received_dir)
    print("ORIGINAL EXCELS / PRIVATE CEDIA:",folder)
    print("PRE-FLIGHT: all 3 source files, frozen IDs, source handles and format passed.")
    for key,item in report.items():
        print("\n",key,item["received_filename"])
        print("  cases:",item["cases"],"| SHA-256:",item["file_sha256"])
        if key=="80":
            print("  human structural statuses:",item["status_counts"])
            print("  blank-answer cells to import:",item["new_or_modified_blank_answer_cells"])
        else:
            print("  annotation rows complete by fields:",item["complete_by_required_fields"])
            print("  blank-answer cells to import:",item["new_or_modified_blank_answer_cells"])
    print("\nSCOPE: format/identity validation only; NOT human provenance or ground-truth accuracy.")
    print("IMPORTANT: any document conflicts/needs_adjudication remain unresolved.")
    if not args.apply:
        print("READ-ONLY: none of the 3 workbooks nor frozen coder/section CSVs were modified.")
        print("For a one-time import, explicitly run --apply A, --apply B or --apply 80.")
        return
    key=args.apply
    fullpath=folder/FILE_NAMES[key]
    print("\nEXPLICIT IMPORT:",key)
    if key in ("A","B"):
        import_coder(SimpleNamespace(coder=key,workbook=fullpath,apply=True))
        print("NEXT AUDIT: python scripts/audit_annotation_progress.py")
    else:
        import_structural(SimpleNamespace(workbook=fullpath,apply=True))
        print("NEXT AUDIT: python scripts/audit_section_boundary_review.py")
        count=report["80"]["status_counts"]
        if count["invalid"] or count["needs_adjudication"]:
            print("WARNING: imported structural data includes unresolved review statuses.")
            print("Do not claim manual review complete or approve automatic trimming.")
    print("Private original XLSX files were not renamed or changed.")

if __name__=="__main__":
    main()
