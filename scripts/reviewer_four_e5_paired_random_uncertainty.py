#!/usr/bin/env python3
"""Paired uncertainty for FOUR FROZEN E5 models on 120 probability-sampled theses.

No model/threshold selection, no replacement data, no model score changes.
Reports within-case paired accuracy change against original E5 (95% paired
nonparametric bootstrap CI and exact McNemar P). Analyses are exploratory:
the 120 cases have already been inspected in prior four-model comparisons.
A and B are separate imperfect human references, not adjudicated truth.
Class-level supports and source handles never enter the public-safe JSON.
"""
from __future__ import annotations
import argparse
import json
from math import comb
from pathlib import Path

import numpy as np
import pandas as pd

from audit_annotation_progress import inspect_files
from reviewer_four_e5_variant_dual_coder_metrics import (
    VARIANTS, CLASSES, validate_fulltext_source
)
from reviewer_human_validation_metrics import PDOT_ID, labels_from_coder
from reviewer_shared import normalize_codes, sha256_file, write_public


def paired_stats(correct_baseline, correct_candidate, seed=5142, n_boot=5000):
    a=np.asarray(correct_baseline,dtype=bool)
    b=np.asarray(correct_candidate,dtype=bool)
    if a.ndim!=1 or a.size==0 or a.shape!=b.shape:
        raise ValueError("Paired Boolean vectors must have same nonempty shape")
    gains=int((~a&b).sum())
    losses=int((a&~b).sum())
    old=int(a.sum())
    new=int(b.sum())
    delta=float((new-old)/len(a))
    rng=np.random.default_rng(seed)
    draws=rng.integers(0,len(a),size=(n_boot,len(a)))
    change=(b.astype(int)-a.astype(int))
    boot=change[draws].mean(axis=1)
    lo,hi=np.quantile(boot,[.025,.975])
    n=gains+losses
    if n:
        smaller=min(gains,losses)
        exact_p=min(1.0,2.0*sum(comb(n,k) for k in range(smaller+1))/2**n)
    else:
        exact_p=1.0
    return {
        "n":len(a),
        "baseline_correct_n":old,
        "candidate_correct_n":new,
        "candidate_correct_baseline_wrong_n":gains,
        "baseline_correct_candidate_wrong_n":losses,
        "accuracy_delta_points":round(delta*100,3),
        "delta_bootstrap95_points":[round(float(lo)*100,3),round(float(hi)*100,3)],
        "mcnemar_exact_two_sided_p_unadjusted":round(exact_p,7),
        "n_bootstrap":n_boot,"seed":seed,
        "interpretation":"Exploratory paired comparison; no prospective held-out model selection.",
    }


def analyze(args):
    workspace=Path(__file__).resolve().parent.parent
    private=(workspace/"data/revision_private").resolve()
    base=args.private_dir.expanduser().resolve()
    npz=args.scores.expanduser().resolve()
    if not base.is_relative_to(private) or not npz.is_relative_to(private):
        raise ValueError("Case-level labels/scores must remain in private CEDIA data")
    if not inspect_files(base)["all_annotations_finished"]:
        raise ValueError("450 human evaluations incomplete")
    source_path=args.source_report.expanduser().resolve()
    v2_path=args.v2_report.expanduser().resolve()
    source=json.loads(source_path.read_text(encoding="utf-8"))
    validate_fulltext_source(source)
    v2=json.loads(v2_path.read_text(encoding="utf-8"))
    if v2.get("status")!="four_frozen_E5_representations_vs_two_independent_coders_not_adjudicated":
        raise ValueError("Expected completed four-variant A/B report")
    if v2.get("score_matrix_sha256")!=sha256_file(npz):
        raise ValueError("Frozen score-matrix SHA differs from report")
    if set(v2.get("comparisons",{}))!={"ods","pdot"}:
        raise ValueError("Four-variant v2 report missing one domain")

    root=args.project_root.expanduser().resolve()
    archive=pd.read_parquet(
        root/"data/processed/07_alignment_pdot_ods_needs.parquet",
        columns=["handle_id","ods_top1","pdot_top1"]
    )
    master=pd.read_csv(base/"sample_master_private.csv",dtype=str,keep_default_na=False)
    if len(archive)!=7830 or len(master)!=450 or master["study_id"].duplicated().any():
        raise ValueError("Frozen 7830/450 corpus roster mismatch")
    indices=master["source_row_index"].astype(int).to_numpy()
    if indices.min()<0 or indices.max()>=7830 or len(set(indices))!=450:
        raise ValueError("Invalid frozen indices")
    if not np.array_equal(
        archive["handle_id"].iloc[indices].astype(str).to_numpy(),
        master["handle_id"].to_numpy()
    ):
        raise ValueError("Original corpus-to-human source handle alignment mismatch")
    chosen=np.flatnonzero(master["selection_stratum"].to_numpy()=="population_random")
    if len(chosen)!=120 or int(
        (master["selection_stratum"]=="targeted_enrichment").sum()
    )!=330:
        raise ValueError("Unexpected random 120 and enriched 330 frozen split")

    coders={}
    for name in ("A","B"):
        df=pd.read_csv(base/f"coder_{name}_private.csv",dtype=str,keep_default_na=False)
        if df["study_id"].duplicated().any() or set(df["study_id"])!=set(master["study_id"]):
            raise ValueError("Reviewer case IDs changed")
        df=df.set_index("study_id").reindex(master["study_id"]).reset_index()
        if not np.array_equal(
            df["private_source_handle"].str.lstrip("'").to_numpy(),
            master["handle_id"].to_numpy()
        ):
            raise ValueError("Original A/B source handles differ")
        coders[name]=df

    out={
        "schema_version":1,
        "status":"four_E5_representations_exploratory_paired_120_random",
        "model_selection_on_120_not_permitted":True,
        "prospective_untouched_holdout_claim":False,
        "n_random":120,
        "n_enriched_not_used_here":330,
        "source_v2_report_sha256":sha256_file(v2_path),
        "frozen_score_matrix_sha256":sha256_file(npz),
        "comparisons":{},
    }
    with np.load(npz,allow_pickle=False) as matrices:
        for domain in ("ods","pdot"):
            source_names=list(source["domains"][domain]["representations"]
                ["legacy_raw"]["top1_category_counts_candidate_unvalidated"])
            if domain=="ods":
                classes=list(normalize_codes(source_names))
                archived=list(normalize_codes(archive["ods_top1"]))
            else:
                classes=[PDOT_ID.get(x,"") for x in source_names]
                archived=[PDOT_ID.get(x,"") for x in archive["pdot_top1"]]
            if set(classes)!=set(CLASSES[domain]) - {"NONE"}:
                raise ValueError("Descriptor taxonomy mismatch for "+domain)
            predictions={}
            for variant in VARIANTS:
                key=f"{domain}_{variant}_scores"
                if key not in matrices:
                    raise ValueError("Missing "+key)
                scores=matrices[key]
                if scores.shape!=(7830,len(classes)) or not np.isfinite(scores).all():
                    raise ValueError("Bad scores for "+key)
                pred=np.asarray(classes)[np.argmax(scores,axis=1)]
                if variant=="legacy_raw" and not np.array_equal(
                    pred,np.asarray(archived,dtype=str)
                ):
                    raise ValueError("Legacy source descriptor ordering is corrupted")
                predictions[variant]=pred[indices[chosen]]
            out["comparisons"][domain]={}
            for reviewer in ("A","B"):
                truth=labels_from_coder(coders[reviewer],domain)[chosen]
                base_correct=predictions["legacy_raw"]==truth
                stats={}
                for cand in VARIANTS:
                    if cand=="legacy_raw":continue
                    stats[cand]=paired_stats(
                        base_correct,predictions[cand]==truth,
                        seed=args.seed,n_boot=args.bootstrap
                    )
                out["comparisons"][domain][reviewer]={
                    "reference_type":"one human reviewer, not adjudicated",
                    "legacy_correct_n":int(base_correct.sum()),
                    "variants_vs_legacy_raw":stats,
                }
    out["limitations"]=[
        "Two separate references A/B are correlated human annotations, not two independent samples of theses.",
        "Four variants have already been inspected on these 120 cases; the tests are retrospective/exploratory.",
        "Point and interval estimates are uncertain for rare ODS/PDOT classes; per-class supports remain in restricted metrics.",
        "Exact McNemar P values are not corrected for multiple hypotheses; use effect sizes and uncertainty rather than significance claims.",
        "No model is selected or tuned by these comparisons and no policy/SDG real-world impact is estimated.",
        "Pre-existing 330 enriched cases serve calibration, not unbiased population accuracy.",
    ]
    return out


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root",required=True,type=Path)
    parser.add_argument("--private-dir",type=Path,default=Path(
        "data/revision_private/validation"))
    parser.add_argument("--scores",type=Path,default=Path(
        "data/revision_private/reviewer_fulltext_reclassification/reclassification_all_7830_PRIVATE.npz"))
    parser.add_argument("--source-report",type=Path,default=Path(
        "docs/audits/reviewer_fulltext_reclassification_v1.json"))
    parser.add_argument("--v2-report",type=Path,default=Path(
        "docs/audits/reviewer_four_e5_variant_dual_coder_metrics_v2.json"))
    parser.add_argument("--output",type=Path,default=Path(
        "docs/audits/reviewer_four_e5_paired_random_uncertainty.json"))
    parser.add_argument("--bootstrap",type=int,default=5000)
    parser.add_argument("--seed",type=int,default=5142)
    a=parser.parse_args()
    if a.bootstrap<1000 or a.bootstrap>20000:
        parser.error("Bootstrap must be 1000..20000")
    result=analyze(a)
    out=write_public(result,a.output,Path(__file__).resolve().parent.parent)
    print("EXPLORATORY paired 120-thesis E5 confidence intervals:",out)
    for domain in ("ods","pdot"):
        print(domain.upper())
        for coder in ("A","B"):
            comp=result["comparisons"][domain][coder]["variants_vs_legacy_raw"]
            for variant,entry in comp.items():
                print(coder,variant,
                      "delta accuracy (points):",entry["accuracy_delta_points"],
                      "paired bootstrap 95%:",entry["delta_bootstrap95_points"],
                      "gains/losses:",entry["candidate_correct_baseline_wrong_n"],
                      entry["baseline_correct_candidate_wrong_n"],
                      "McNemar exploratory P:",entry["mcnemar_exact_two_sided_p_unadjusted"])
    print("No prospective holdout claims or model selection.")

if __name__=="__main__":
    main()
