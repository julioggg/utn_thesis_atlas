#!/usr/bin/env python3
"""Freeze a traceable PRIVATE model snapshot for revised manuscript exhibits.

No re-embedding, no document text export, no source mutation. A single
predeclared descriptive variant is applied consistently to SDG, PDOT and
local needs. The fulltext-centered variant was examined on the same 120
random cases; it is EXPLORATORY, not prospectively test-selected.
The 47 thesis reviews are reported as human by the coordinator; this
script does not forge or certify signed committee minutes.

Private row-level parquet stays ignored; public JSON has aggregates only.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from reviewer_four_e5_variant_dual_coder_metrics import validate_fulltext_source
from reviewer_human_validation_metrics import PDOT_ID
from reviewer_shared import FIVE_FACULTIES, normalize_codes, sha256_file
from reviewer_stage1_stats import clean_faculties

N=7830
DOMAIN_COUNTS={"ods":17,"pdot":6,"need":10}
VARIANTS=("legacy_raw","legacy_centered","fulltext_raw","fulltext_centered")


def selected_labels(scores,original_keys,domain):
    if len(original_keys)!=DOMAIN_COUNTS[domain] or len(set(original_keys))!=len(original_keys):
        raise ValueError("Taxonomy size/uniqueness failed for "+domain)
    if domain=="ods":
        canonical=normalize_codes(original_keys)
        desired={f"ODS {i}" for i in range(1,18)}
        if set(canonical)!=desired:raise ValueError("ODS descriptor IDs changed")
    elif domain=="pdot":
        canonical=[PDOT_ID.get(k,"[invalid]") for k in original_keys]
        desired={f"PDOT {i}" for i in range(1,7)}
        if set(canonical)!=desired:raise ValueError("PDOT dictionary IDs changed")
    else:
        canonical=list(original_keys)
    matrix=np.asarray(scores,dtype=np.float32)
    if matrix.shape!=(N,len(canonical)) or not np.isfinite(matrix).all():
        raise ValueError("Invalid frozen score matrix: "+domain)
    order=np.argsort(-matrix,axis=1,kind="stable")
    top=order[:,0]
    best=matrix[np.arange(N),top]
    runner=matrix[np.arange(N),order[:,1]]
    return np.asarray(canonical,dtype=str)[top],best,best-runner


def freeze(args):
    workspace=Path(__file__).resolve().parent.parent
    private=(workspace/"data/revision_private").resolve()
    root=args.project_root.expanduser().resolve()
    scores_path=args.scores.expanduser().resolve()
    report_path=args.source_report.expanduser().resolve()
    out=args.output.expanduser().resolve()
    audit=args.audit.expanduser().resolve()
    if args.variant not in VARIANTS:raise ValueError("Unrecognized frozen representation")
    if not scores_path.is_relative_to(private) or not out.is_relative_to(private):
        raise ValueError("Case-level model arrays must remain inside private revision/data")
    if out.exists() or audit.exists():
        raise FileExistsError("Refuse overwriting a frozen manuscript snapshot/audit")
    report=json.loads(report_path.read_text(encoding="utf-8"))
    validate_fulltext_source(report)
    original_path=root/"data/processed/07_alignment_pdot_ods_needs.parquet"
    columns=["handle_id","faculty","career","year","topic","advisor",
             "ods_top1","pdot_top1","need_top1","need_top1_score"]
    frame=pd.read_parquet(original_path,columns=columns)
    if len(frame)!=N or frame["handle_id"].isna().any() or frame["handle_id"].duplicated().any():
        raise ValueError("Original 7830-case source is not unique and complete")
    faculty,audit_fac=clean_faculties(frame,min_support=10,min_purity=.98)
    cleaned=faculty["faculty5"].astype("string")
    is_real=cleaned.isin(FIVE_FACULTIES).fillna(False).to_numpy(dtype=bool)
    raw=frame["faculty"].astype("string").str.strip()
    originally_known=raw.isin(FIVE_FACULTIES).fillna(False).to_numpy(dtype=bool)
    source=np.full(N,"unresolved",dtype=object)
    source[originally_known]="metadata"
    source[is_real&~originally_known]="career_imputed"
    output=pd.DataFrame({
        "source_row_index":np.arange(N,dtype=np.int32),
        "handle_id":frame["handle_id"].astype(str),
        "year":pd.to_numeric(frame["year"],errors="coerce"),
        "topic":frame["topic"],
        "faculty5":cleaned.fillna("Unassigned").astype(str),
        "faculty_source":source,
        "advisor_reported":frame["advisor"].astype("string").fillna("").str.strip().ne("").to_numpy(),
    })
    source_names={}
    with np.load(scores_path,allow_pickle=False) as matrices:
        for domain,n_expected in DOMAIN_COUNTS.items():
            names=list(report["domains"][domain]["representations"]
                ["legacy_raw"]["top1_category_counts_candidate_unvalidated"].keys())
            source_names[domain]=names
            key=f"{domain}_{args.variant}_scores"
            if key not in matrices:raise ValueError("Missing source matrix "+key)
            label,sim,margin=selected_labels(matrices[key],names,domain)
            output[f"{domain}_label"]=label
            output[f"{domain}_top1_score"]=sim.astype("float32")
            output[f"{domain}_margin"]=margin.astype("float32")
            if domain=="ods":
                expected=normalize_codes(frame["ods_top1"])
            elif domain=="pdot":
                expected=[PDOT_ID.get(v,"[invalid]") for v in frame["pdot_top1"]]
            else:
                expected=frame["need_top1"].astype(str).tolist()
            if args.variant=="legacy_raw" and list(label)!=list(expected):
                raise ValueError("Legacy score replay failed on "+domain)
    if len(output)!=N or any(output[f"{d}_label"].isna().any() for d in DOMAIN_COUNTS):
        raise ValueError("Final private snapshot invalid")
    original_advisor=frame["advisor"].astype("string").fillna("").str.strip()
    advisors=original_advisor[original_advisor.ne("")]
    n_reported=int(len(advisors))
    n_unique=int(advisors.nunique())
    if n_reported!=7541 or n_unique!=1091:
        raise ValueError(
            f"Frozen original adviser census changed ({n_reported} reported, {n_unique} unique)"
        )
    fac_counts=output["faculty_source"].value_counts().to_dict()
    for field in ("metadata","career_imputed","unresolved"):
        fac_counts.setdefault(field,0)
    if fac_counts["metadata"]!=audit_fac["strict_known_five_faculty_rows"] or (
        fac_counts["career_imputed"]!=audit_fac["career_imputed_rows"]
    ):
        raise ValueError("Five-faculty lineage count inconsistent")
    counts={domain:{
        name:int((output[f"{domain}_label"]==name).sum())
        for name in output[f"{domain}_label"].unique()
    } for domain in DOMAIN_COUNTS}
    if any(sum(counts[domain].values())!=N for domain in DOMAIN_COUNTS):
        raise ValueError("Census totals do not add to 7830")
    # Atomic private data lock; no overwrite or fallback to legacy if missing.
    out.parent.mkdir(parents=True,exist_ok=True)
    output.to_parquet(out,index=False)
    status={
        "schema_version":1,
        "status":"frozen_descriptive_model_snapshot_exploratory",
        "model_variant":args.variant,
        "n_original_thesis_records":N,
        "single_consistent_domain_variant":True,
        "source_data_sha256":sha256_file(original_path),
        "source_matrix_sha256":sha256_file(scores_path),
        "source_reclassification_sha256":sha256_file(report_path),
        "private_snapshot_sha256":sha256_file(out),
        "private_snapshot_relative_path":str(out.relative_to(workspace)),
        "source_category_order":{"ods":[f"SDG {i}" for i in range(1,18)],
                                 "pdot":[f"Analytical axis {i}" for i in range(1,7)],
                                 "local_needs":"10 historically defined source categories; private strings not exported"},
        "label_totals":counts,
        "faculty_resolution":audit_fac,
        "faculty_provenance_counts":fac_counts,
        "adviser_records_with_nonempty_value":n_reported,
        "distinct_unstandardized_adviser_strings":n_unique,
        "labels_generated_from":"frozen source descriptors, not human validated",
        "reported_human_review_provenance":"author states A/B and 47-case committee decisions are human; this script does not verify signed minutes",
        "policy_taxonomy_status":"six PDOT analytical categories; official policy equivalence not yet independently approved",
        "incomplete_2026_caution":True,
        "limitations":[
            "Fulltext-centered was explored retrospectively on the 120 random cases. Never call it prospectively selected.",
            "Top-1 forced labels reflect thematic affinity only, not sustainability contribution.",
            "Ten local-need category labels are source-defined and await policy provenance approval.",
            "Career faculty imputations are heuristic; five-faculty statistics should report a strict-source sensitivity.",
            "The private model snapshot and ID-bearing input must never be uploaded to the public GitHub repo.",
        ]
    }
    audit.parent.mkdir(parents=True,exist_ok=True)
    audit.write_text(json.dumps(status,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("PRIVATE snapshot frozen:",out)
    print("Snapshot SHA-256:",status["private_snapshot_sha256"])
    print("Model variant:",args.variant,"N=",N)
    print("SDG 4:",counts["ods"].get("ODS 4",0),
          "PDOT analytical axes:",len(counts["pdot"]),
          "local priorities:",len(counts["need"]))
    print("Public-safe aggregate audit:",audit)
    print("Human provenance and PDOT source approval remain documentary tasks.")
    return status


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root",type=Path,required=True)
    p.add_argument("--variant",choices=VARIANTS,default="fulltext_centered")
    p.add_argument("--scores",type=Path,default=Path(
        "data/revision_private/reviewer_fulltext_reclassification/reclassification_all_7830_PRIVATE.npz"))
    p.add_argument("--source-report",type=Path,default=Path(
        "docs/audits/reviewer_fulltext_reclassification_v1.json"))
    p.add_argument("--output",type=Path,default=Path(
        "data/revision_private/manuscript_release_v1/model_snapshot_PRIVATE.parquet"))
    p.add_argument("--audit",type=Path,default=Path(
        "docs/revision_assets/v1/model_snapshot_audit.json"))
    args=p.parse_args()
    freeze(args)


if __name__=="__main__":
    main()
