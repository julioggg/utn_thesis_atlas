#!/usr/bin/env python3
"""Dry-run / safely ingest the 80-case human section review Excel in CEDIA.

Reads only the annotation sheet; never alters thesis source, embedded text
or the independent 450-case blinded ODS/PDOT reviewer packages. Explicit
--apply saves a pre-import backup and updates ONLY human-answer fields in
the frozen original section-boundary CSV. No use of model predictions.
"""
from __future__ import annotations

import argparse
import csv
import os
import shutil
import tempfile
from pathlib import Path

from export_blinded_validation_workbooks import BOUNDARY_FIELDS, WORKSPACE
from import_blinded_validation_excel import read_xlsx_rows

FIELDS = BOUNDARY_FIELDS[9:]

def read_csv(path):
    with path.open(newline="",encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))

def parse_boundary_excel(path):
    rows=read_xlsx_rows(path, "REVISION_80")
    sheet=dict(rows)
    headers=[sheet.get(5,{}).get(i,"") for i in range(1,len(BOUNDARY_FIELDS)+1)]
    if tuple(headers)!=BOUNDARY_FIELDS:
        raise ValueError("Structural worksheet headers changed")
    values=[]
    for index,row in rows:
        if index<6:continue
        if index>85:raise ValueError("More than 80 structural sample rows")
        record={k:row.get(i,"").strip() for i,k in enumerate(BOUNDARY_FIELDS,1)}
        values.append(record)
    if len(values)!=80 or len({x["review_id"] for x in values})!=80:
        raise ValueError("Expected 80 unique frozen section review IDs")
    for x in values:
        for key in (
            "human_heading_is_real_references_start",
            "human_tail_contains_scientific_contribution",
            "human_trim_from_boundary_safe"
        ):
            if x[key] not in ("","yes","no","uncertain"):
                raise ValueError("Invalid section-review flag, expected yes/no/uncertain")
        frac=x["human_corrected_boundary_fraction"]
        if frac:
            try: num=float(frac)
            except ValueError:raise ValueError("Boundary position must be decimal fraction")
            if not (0<=num<=1):
                raise ValueError("Boundary correction outside [0,1]")
        if x["human_trim_from_boundary_safe"]=="yes" and (
            x["human_heading_is_real_references_start"]!="yes" or
            x["human_tail_contains_scientific_contribution"]!="no"
        ):
            raise ValueError("Unsafe structural trim approval contradiction")
    return values

def ingest(args):
    private=(WORKSPACE/"data/revision_private/section_boundary_review_v1").resolve()
    source=private/"section_boundary_review_private.csv"
    backup=private/"section_boundary_review_before_excel_import_PRIVATE.csv"
    old=read_csv(source)
    new=parse_boundary_excel(args.workbook.expanduser().resolve())
    if len(old)!=80:
        raise ValueError("Frozen 80-case review master size changed")
    original={x["review_id"]:x for x in old}
    submitted={x["review_id"]:x for x in new}
    if len(original)!=80 or set(original)!=set(submitted):
        raise ValueError("Review ID roster changed")
    updated=0
    for rid,old_row in original.items():
        fresh=submitted[rid]
        for key in BOUNDARY_FIELDS[:9]:
            orig=old_row.get(key,"").lstrip("'") if key=="private_source_handle" else old_row.get(key,"")
            supplied=fresh.get(key,"").lstrip("'") if key=="private_source_handle" else fresh.get(key,"")
            if orig!=supplied:
                raise ValueError("Immutable section-review data changed: "+key)
        for key in FIELDS:
            old_val=(old_row.get(key) or "").strip()
            new_val=fresh[key]
            if old_val and old_val!=new_val:
                raise ValueError("Existing original manual structural review cannot be overwritten")
            if old_val!=new_val:updated+=1
    print("Structural review: 80 frozen cases | new human answer cells:",updated)
    if not args.apply:
        print("DRY RUN. Nothing changed. Apply explicitly only after review.")
        return
    if backup.exists():
        raise FileExistsError("Structural pre-import backup already exists")
    shutil.copy2(source,backup)
    columns=list(old[0])
    with tempfile.NamedTemporaryFile(
        "w",dir=private,prefix=".boundary-import-",suffix=".csv",
        encoding="utf-8",newline="",delete=False
    ) as temp:
        staging=Path(temp.name)
        writer=csv.DictWriter(temp,fieldnames=columns,extrasaction="ignore")
        writer.writeheader()
        for row in old:
            row.update({key:submitted[row["review_id"]][key] for key in FIELDS})
            writer.writerow(row)
    os.replace(staging,source)
    print("Applied 80-case structural answers; backup:",backup)
    print("Run: python scripts/audit_section_boundary_review.py")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workbook",required=True,type=Path)
    p.add_argument("--apply",action="store_true")
    ingest(p.parse_args())

if __name__=="__main__":
    main()
