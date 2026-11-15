#!/usr/bin/env python3
"""Exploratory per-class model scores vs original A and B coder labels separately.

IMPORTANT: A and B are alternative imperfect human references, NOT an
adjudicated gold standard. This compares frozen original (forced top-1) E5
predictions to each coder independently, with each class support reported
privately. No 47-case technical proposals, no C majority votes and no
synthetic human ground truth are used.

Sampling design: 120 frozen probability-sampled cases form the held-out
population probe; 330 enriched cases are a targeted calibration/diagnostic
sample. Pooled 450 metrics are descriptive only. Relative score comparisons
cannot prove performance of new full-text/centered models.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from audit_annotation_progress import inspect_files
from reviewer_human_validation_metrics import (
    PDOT_ID, NONE, labels_from_coder, metrics, output_metrics
)
from reviewer_shared import (
    normalize_codes, private_output, read_original_embeddings, write_public
)

def evaluate(root, private, output_private):
    root=Path(root).resolve()
    private=Path(private).resolve()
    progress=inspect_files(private)
    if not progress["all_annotations_finished"]:
        raise ValueError("Both A and B must pass complete private annotation audit")
    master=pd.read_csv(private/"sample_master_private.csv", dtype=str,keep_default_na=False)
    by_letter={}
    for letter in ("A","B"):
        df=pd.read_csv(private/f"coder_{letter}_private.csv",dtype=str,keep_default_na=False)
        if df["study_id"].duplicated().any() or set(df["study_id"])!=set(master["study_id"]):
            raise ValueError("A/B frozen ID roster changed")
        df=df.set_index("study_id").reindex(master["study_id"]).reset_index()
        if not np.array_equal(
            df["private_source_handle"].str.lstrip("'").to_numpy(),
            master["handle_id"].to_numpy()
        ):
            raise ValueError("A/B original source handles differ from frozen 450 master")
        by_letter[letter]=df
    original=pd.read_parquet(root/"data/processed/07_alignment_pdot_ods_needs.parquet",
        columns=["handle_id","ods_top1","pdot_top1"])
    count,alignment=read_original_embeddings(root,len(original))
    indices=master["source_row_index"].astype(int).to_numpy()
    if len(set(indices.tolist()))!=450 or indices.min()<0 or indices.max()>=count:
        raise ValueError("Invalid frozen 450 indexes")
    if not np.array_equal(
        original["handle_id"].iloc[indices].astype(str).to_numpy(),
        master["handle_id"].to_numpy()
    ):
        raise ValueError("Legacy E5 prediction rows differ from frozen A/B sample")
    classes={
        "ods":[f"ODS {i}" for i in range(1,18)]+[NONE],
        "pdot":[f"PDOT {i}" for i in range(1,7)]+[NONE],
    }
    pred={
        "ods":np.asarray(normalize_codes(original["ods_top1"]),dtype=str)[indices],
        "pdot":original["pdot_top1"].map(PDOT_ID).astype(str).to_numpy()[indices],
    }
    if not set(pred["ods"]).issubset(set(classes["ods"]) - {NONE}):
        raise ValueError("Legacy ODS predicted unknown label")
    if not set(pred["pdot"]).issubset(set(classes["pdot"]) - {NONE}):
        raise ValueError("Legacy PDOT predicted unknown label")
    strata=master["selection_stratum"].to_numpy(dtype=str)
    splits={
        "probability_sample_120":strata=="population_random",
        "targeted_enrichment_330":strata=="targeted_enrichment",
        "all_450_descriptive_only":np.ones(450,dtype=bool),
    }
    if splits["probability_sample_120"].sum()!=120 or splits["targeted_enrichment_330"].sum()!=330:
        raise ValueError("Unexpected 120/330 sampling design")
    dest=private_output(output_private,Path(__file__).resolve().parent.parent)
    expected=[
        dest/f"legacy_forced_top1_vs_{letter}_{domain}_{split}_perclass_PRIVATE.csv"
        for letter in ("A","B") for domain in classes for split in splits
    ]
    if any(file.exists() for file in expected):
        raise FileExistsError("Private per-class result already exists; no silent overwrite")
    result={
        "schema_version":1,
        "status":"legacy_e5_vs_two_coders_exploratory_not_adjudicated",
        "source_model":"original forced top1 E5 truncated-input baseline",
        "row_alignment_check":"passed",
        "validation_reference":"A and B separate; no expert-adjudicated gold standard",
        "coder_independence_provenance":"reviewers attest human decisions; separate signed addenda pending",
        "sampling":{"probability_sample":120,"targeted_enrichment":330,
                    "all_frozen":450},
        "model_evaluation_against_distinct_coder_labels":True,
        "comparisons":{},
    }
    for letter,annotation in by_letter.items():
        result["comparisons"][letter]={}
        for domain, categories in classes.items():
            truth=labels_from_coder(annotation,domain)
            result["comparisons"][letter][domain]={}
            for split_name,mask in splits.items():
                scores=metrics(truth[mask],pred[domain][mask],categories)
                filename=(
                    f"legacy_forced_top1_vs_{letter}_{domain}_{split_name}"
                    f"_perclass_PRIVATE.csv"
                )
                result["comparisons"][letter][domain][split_name]=output_metrics(
                    scores,dest,filename.removesuffix("_perclass_PRIVATE.csv")
                )
    result["limitations"]=[
        "These are two parallel reference comparisons, not independent agreement with adjudicated truth.",
        "All 47 main-label disagreements remain unresolved until human expert ratification.",
        "Per-class supports and confusions remain in ignored private data; do not suppress absent classes.",
        "The 330 enriched cases are not a representative sample of the 7830 thesis corpus.",
        "The 120 probability cases have high uncertainty for rare classes; report uncertainty intervals.",
        "Forced top1 has zero no-match predictions and may overstate thematic coverage.",
        "This result is not fulltext E5, mean-centered E5 or keyword baseline performance.",
        "No personal source identifiers, thesis text or predictions per case are included in public aggregate JSON.",
    ]
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root",type=Path,required=True)
    p.add_argument("--private-dir",type=Path,
        default=Path("data/revision_private/validation"))
    p.add_argument("--private-metrics-dir",type=Path,
        default=Path("data/revision_private/dual_coder_model_metrics"))
    p.add_argument("--output",type=Path,
        default=Path("docs/audits/reviewer_legacy_e5_dual_coder_provisional.json"))
    args=p.parse_args()
    result=evaluate(args.project_root,args.private_dir,args.private_metrics_dir)
    dest=write_public(result,args.output,Path(__file__).resolve().parent.parent)
    print("EXPLORE ONLY: E5 forced top-1 against A and B separately.")
    print("Aggregate report:",dest)
    for letter in ("A","B"):
        for domain in ("ods","pdot"):
            for split in ("probability_sample_120","targeted_enrichment_330"):
                x=result["comparisons"][letter][domain][split]
                print(letter,domain,split,"n=",x["n"],"accuracy=",x["accuracy"],
                      "macro_F1_present_classes=",x["macro_f1_present_or_predicted_classes"])
    print("No adjudicated gold standard. Fulltext/centered/threshold models not assessed.")
    print("Private per-class supports + precision/recall/F1:",args.private_metrics_dir)

if __name__=="__main__":
    main()
