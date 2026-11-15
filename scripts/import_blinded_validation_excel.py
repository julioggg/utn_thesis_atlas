#!/usr/bin/env python3
"""Safely ingest independently completed blind Excel annotations back to CEDIA.

STD-LIB Excel OOXML reader supporting inline strings and Excel shared strings.
No macros, no dependencies on openpyxl, and no model predictions are read.
Default mode is DRY RUN; --apply takes a one-time backup and updates ONLY
the existing coder_{A,B}_private.csv human-answer columns in frozen ID order.

Human codes can be incomplete during drafting, but MUST pass the existing
audit_annotation_progress.py before agreement or metrics are reported.
"""
from __future__ import annotations

import argparse
import csv
import os
import shutil
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from export_blinded_validation_workbooks import ANNOTATION_FIELDS, WORKSPACE

NS={"m":"http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r":"http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "p":"http://schemas.openxmlformats.org/package/2006/relationships"}
ANSWERS=set(ANNOTATION_FIELDS[2:])

def read_xlsx_rows(path, sheet_name="ANOTACION"):
    with ZipFile(path,"r") as archive:
        if archive.testzip() is not None:
            raise ValueError("Invalid Excel ZIP CRC")
        wb=ET.fromstring(archive.read("xl/workbook.xml"))
        rels=ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        relationship={
            r.attrib["Id"]:r.attrib["Target"]
            for r in rels.findall("p:Relationship",NS)
        }
        chosen=None
        for sheet in wb.findall("m:sheets/m:sheet",NS):
            if sheet.attrib["name"]==sheet_name:
                rid=sheet.attrib["{"+NS["r"]+"}id"]
                chosen=relationship.get(rid)
                break
        if not chosen:
            raise ValueError(f"Expected Excel sheet missing: {sheet_name}")
        member=chosen.lstrip("/")
        if not member.startswith("xl/"):
            member="xl/"+member
        if ".." in member.split("/"):
            raise ValueError("Unexpected relative worksheet path in Excel")
        share=[]
        if "xl/sharedStrings.xml" in archive.namelist():
            strings=ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for si in strings.findall("m:si",NS):
                share.append("".join(t.text or "" for t in si.findall(".//m:t",NS)))
        doc=ET.fromstring(archive.read(member))
        rows=[]
        for row in doc.findall("m:sheetData/m:row",NS):
            number=int(row.attrib["r"])
            cells={}
            for c in row.findall("m:c",NS):
                ref=c.attrib["r"]
                letters="".join(ch for ch in ref if ch.isalpha())
                col=0
                for ch in letters:
                    col=col*26+ord(ch.upper())-64
                typ=c.attrib.get("t","")
                value=c.find("m:v",NS)
                if typ=="inlineStr":
                    inline=c.find("m:is",NS)
                    txt="".join(t.text or "" for t in inline.findall(".//m:t",NS)) if inline is not None else ""
                elif typ=="s":
                    if value is None or not (value.text or "").isdigit():
                        raise ValueError("Invalid Excel shared string index")
                    index=int(value.text)
                    if index>=len(share):raise ValueError("Shared string index out of range")
                    txt=share[index]
                else:
                    txt=value.text if value is not None and value.text is not None else ""
                cells[col]=txt
            rows.append((number,cells))
        return rows

def extract_annotations(path,expected_coder):
    rows=read_xlsx_rows(path)
    first=dict(rows).get(1,{})
    if expected_coder.upper() not in first.get(1,"").upper():
        raise ValueError("Excel does not identify requested independent coder")
    heads=dict(rows).get(5,{})
    observed=[heads.get(i,"") for i in range(1,len(ANNOTATION_FIELDS)+1)]
    if tuple(observed)!=ANNOTATION_FIELDS:
        raise ValueError("Excel annotation columns were modified")
    result=[]
    for pos,cells in rows:
        if pos<6:continue
        if pos>455:raise ValueError("Unexpected annotation row count")
        values={name:cells.get(i,"").strip() for i,name in enumerate(ANNOTATION_FIELDS,1)}
        result.append(values)
    if len(result)!=450:
        raise ValueError("Excel must contain exactly 450 frozen cases")
    ids=[x["study_id"] for x in result]
    if len(set(ids))!=450 or any(not x for x in ids):
        raise ValueError("Missing or duplicate Excel study IDs")
    for row in result:
        for flag in ("sdg_no_match","pdot_no_match","uncertain"):
            if row[flag] not in ("","yes","no"):
                raise ValueError("Flag must be yes, no or blank")
        for kind,valid in (("sdg",{f"ODS {i}" for i in range(1,18)}),
                           ("pdot",{f"PDOT {i}" for i in range(1,7)})):
            a,b=(row[f"{kind}_{x}"] for x in ("primary","secondary"))
            no=row[f"{kind}_no_match"]
            if (a and a not in valid) or (b and b not in valid):
                raise ValueError(f"Invalid {kind} category code")
            if (b and (not a or a==b)) or (no=="yes" and (a or b)):
                raise ValueError(f"Contradictory {kind} primary/secondary/no_match")
    return result

def read_csv(path):
    with path.open(newline="",encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))

def compare_input(original,new):
    if len(original)!=450 or len(new)!=450:
        raise ValueError("Frozen source and workbook size mismatch")
    src={row["study_id"]:row for row in original}
    if len(src)!=450 or {x["study_id"] for x in new}!=set(src):
        raise ValueError("Study identifiers do not match frozen coder roster")
    new_by_id={x["study_id"]:x for x in new}
    modified=0
    answered=0
    for sid,row in src.items():
        entry=new_by_id[sid]
        original_handle=row["private_source_handle"].lstrip("'")
        if original_handle != entry["private_source_handle"].lstrip("'"):
            raise ValueError("One or more source handles changed")
        for key in ANSWERS:
            before=(row.get(key) or "").strip()
            now=entry[key]
            if before and before!=now:
                raise ValueError("Refusing to silently alter an already recorded human answer")
            if now:answered+=1
            if before!=now:modified+=1
    return modified,answered,src,new_by_id

def ingest(args):
    private=(WORKSPACE/"data/revision_private/validation").resolve()
    book=args.workbook.expanduser().resolve()
    source=private/f"coder_{args.coder}_private.csv"
    backup=private/f"coder_{args.coder}_before_excel_import_PRIVATE.csv"
    if not book.is_file() or not source.is_file():
        raise FileNotFoundError("Workbook and original coder CSV required")
    expected=read_csv(source)
    values=extract_annotations(book,args.coder)
    modified,answered,src,by_id=compare_input(expected,values)
    print("Coder:",args.coder,"| cases:",len(expected),
          "| newly populated answer cells:",modified,
          "| total nonblank answer cells:",answered)
    if not args.apply:
        print("DRY RUN: no original coder files modified. Use --apply only after review.")
        return
    if backup.exists():
        raise FileExistsError("Original coder backup already exists; manual reconciliation required")
    shutil.copy2(source,backup)
    columns=list(expected[0])
    with tempfile.NamedTemporaryFile(
        "w",dir=private,prefix=".coder-import-",suffix=".csv",
        encoding="utf-8",newline="",delete=False
    ) as tmp:
        staging=Path(tmp.name)
        writer=csv.DictWriter(tmp,fieldnames=columns,extrasaction="ignore")
        writer.writeheader()
        for row in expected:
            for key in ANSWERS:
                row[key]=by_id[row["study_id"]][key]
            writer.writerow(row)
    os.replace(staging,source)
    print("Applied human answers to:",source)
    print("One-time pre-import backup:",backup)
    print("Run: python scripts/audit_annotation_progress.py")
    print("DO NOT compare A and B until both reviews are independently frozen.")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--coder",required=True,choices=["A","B"])
    p.add_argument("--workbook",required=True,type=Path)
    p.add_argument("--apply",action="store_true")
    args=p.parse_args()
    ingest(args)

if __name__=="__main__":
    main()
