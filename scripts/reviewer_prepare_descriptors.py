#!/usr/bin/env python3
"""Create PRIVATE version-controlled-by-hash descriptor manifest TEMPLATE.

Labels come from the actual 07 parquet taxonomy; descriptor texts and
provenance fields remain EMPTY until source-verified. Never invent text
descriptions or copy unverified metadata into a publication.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import pandas as pd
from reviewer_shared import normalize_codes, private_output, write_public


def template(frame):
    codes=set(normalize_codes(frame["ods_top1"]))
    ods=[f"ODS {i}" for i in range(1,18)]
    if codes != set(ods):
        raise ValueError("Actual original ODS labels fail to cover exactly 17 numeric codes")
    pdot=sorted(set(frame["pdot_top1"].astype(str)))
    needs=sorted(set(frame["need_top1"].astype(str)))
    if len(pdot)!=6 or len(needs)!=10:
        raise ValueError("Expected six PDOT axes and ten local-need labels in original atlas")
    def make(ids):
        return [{
            "id":item, "descriptor":"", "paraphrase_1":"",
            "paraphrase_2":"", "source_document":"",
            "source_location":"", "verified_by":""
        } for item in ids]
    return {
        "schema_version":1,
        "status":"TEMPLATE_REQUIRES_SOURCE_VERIFICATION",
        "model":"intfloat/multilingual-e5-large",
        "model_query_prefix":"query: ",
        "canonical_text_source":"Original thesis atlas classification code; verify actual generation separately",
        "official_pdot_edition":"",
        "needs_definition_source":"",
        "verified":False,
        "taxonomies":{"ods":make(ods),"pdot":make(pdot),"need":make(needs)},
        "notes":[
            "Fill ALL original descriptors from original verified code and documentary sources.",
            "Paraphrases must be human-written or source-justified and frozen before inspecting results.",
            "The query: prefix is a documented E5 retrieval convention but may differ from legacy implementation.",
            "Setting verified=true requires independent scientific review; this program never does it automatically.",
        ]
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root",type=Path,required=True)
    p.add_argument("--private-dir",type=Path,
                   default=Path("data/revision_private/descriptor_inventory"))
    p.add_argument("--report",type=Path,
                   default=Path("docs/audits/descriptor_template_status.json"))
    a=p.parse_args()
    workspace=Path(__file__).resolve().parent.parent
    private=private_output(a.private_dir,workspace)
    path=private/"verified_descriptors_PRIVATE.json"
    if path.exists():
        raise FileExistsError("Refusing to overwrite an existing private descriptor manifest")
    frame=pd.read_parquet(a.project_root.expanduser().resolve()/
                          "data/processed/07_alignment_pdot_ods_needs.parquet",
                          columns=["ods_top1","pdot_top1","need_top1"])
    manifest=template(frame)
    path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    report={
        "schema_version":1,"status":"private_descriptor_manifest_template_created",
        "rows":len(frame),
        "taxonomy_sizes":{k:len(v) for k,v in manifest["taxonomies"].items()},
        "original_descriptors_source_verified":False,
        "reworded_descriptors_prepared":False,
        "current_classifier_multi_label_accuracy_known":False,
        "notes":[
            "The private descriptor manifest is empty by design; do not run sensitivity until exact original strings and sources are verified.",
            "No descriptor text or document-level data were published.",
        ]
    }
    write_public(report,a.report,workspace)
    print("Private template created:",path)
    print("Descriptor strings intentionally missing: consult the original classifier source.")
    print("Public candidate status:",a.report)


if __name__=="__main__":
    main()
