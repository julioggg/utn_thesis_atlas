#!/usr/bin/env python3
"""Exploratory threshold/margin abstention calibration on 330 targeted cases.

For each existing E5 score representation, ODS/PDOT, and human coder A/B,
select candidate cosine score and top1-top2 margin cutoffs on the 330
targeted cases only. Apply them to the 120 random cases without refitting.
This is retrospective, NOT untouched confirmatory model validation: the
120 outcomes have already been inspected for accuracy/sensitivity.

Model may output NONE ("sin correspondencia"), instead of forced top1.
Covers a transparent grid, 60% minimum training coverage, and macro-F1
over present/predicted classes. No thresholds are transferable between
centered/raw geometry. Analytic PDOT labels may differ from official axes.
All individual rows and per-class outputs remain PRIVATE on CEDIA.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from audit_annotation_progress import inspect_files
from reviewer_four_e5_variant_dual_coder_metrics import (
    VARIANTS, CLASSES, validate_fulltext_source
)
from reviewer_human_validation_metrics import (
    PDOT_ID, NONE, labels_from_coder, metrics, output_metrics
)
from reviewer_shared import normalize_codes, sha256_file, write_public, private_output

QUANTILES=(0.00,0.05,0.10,0.20,0.30,0.40,0.50,0.60,0.70)
MIN_TRAIN_COVERAGE=0.60
DOMAINS=("ods","pdot")
CODERS=("A","B")


def predict_abstaining(scores,names,score_cutoff,margin_cutoff):
    x=np.asarray(scores,dtype=np.float32)
    if x.ndim!=2 or len(names)!=x.shape[1] or x.shape[1]<2:
        raise ValueError("Bad score grid or descriptor names")
    if not np.isfinite(x).all():
        raise ValueError("Nonfinite score values")
    rank=np.argsort(-x,axis=1,kind="stable")
    best=x[np.arange(len(x)),rank[:,0]]
    second=x[np.arange(len(x)),rank[:,1]]
    pred=np.asarray(names,dtype=str)[rank[:,0]]
    pred[(best<score_cutoff)|((best-second)<margin_cutoff)]=NONE
    return pred


def tune_on_330(scores,truth,names):
    score=np.asarray(scores,dtype=np.float32)
    truth=np.asarray(truth,dtype=str)
    if score.ndim!=2 or score.shape[0]!=330 or len(truth)!=330:
        raise ValueError("Calibration must use EXACTLY the 330 enriched cases")
    ordered=np.sort(score,axis=1)
    best=ordered[:,-1]
    margin=ordered[:,-1]-ordered[:,-2]
    if not np.isfinite(score).all():
        raise ValueError("Nonfinite scores")
    # Zero threshold should allow the unmodified top1 if signed cosine
    # is negative. These minima intentionally include the forced baseline.
    cuts=np.unique(np.r_[np.nextafter(best.min(),-np.inf),
                          np.quantile(best,QUANTILES)])
    gaps=np.unique(np.r_[np.nextafter(margin.min(),-np.inf),
                          np.quantile(margin,QUANTILES)])
    best_tuple=None
    best_selection=None
    best_stats=None
    tried=0
    for t in cuts:
        for m in gaps:
            pred=predict_abstaining(score,names,float(t),float(m))
            coverage=float(np.mean(pred!=NONE))
            if coverage < MIN_TRAIN_COVERAGE-1e-8:
                continue
            assessed=metrics(truth,pred,list(names)+[NONE])
            objective=assessed["macro_f1_present_or_predicted_classes"]
            if objective is None:continue
            tried+=1
            # Maximize macro-F1, break ties by greater coverage,
            # and then by weaker similarity/margin thresholds.
            choice=(objective,coverage,-float(t),-float(m))
            if best_tuple is None or choice>best_tuple:
                best_tuple=choice
                best_selection=(float(t),float(m))
                best_stats=assessed
    if not best_selection:
        raise ValueError("No eligible threshold pair")
    return best_selection,best_stats,tried


def analyze(args):
    workspace=Path(__file__).resolve().parent.parent
    private=(workspace/"data/revision_private").resolve()
    coded=args.private_dir.expanduser().resolve()
    score_path=args.scores.expanduser().resolve()
    destination=args.private_metrics_dir.expanduser().resolve()
    for file in (coded,score_path,destination):
        if not file.is_relative_to(private):
            raise ValueError("All record-level data must remain in private CEDIA data")
    if not inspect_files(coded)["all_annotations_finished"]:
        raise ValueError("Both human annotation workbooks must be complete")
    source_path=args.source_report.expanduser().resolve()
    v2_path=args.v2_report.expanduser().resolve()
    source=json.loads(source_path.read_text(encoding="utf-8"))
    validate_fulltext_source(source)
    v2=json.loads(v2_path.read_text(encoding="utf-8"))
    if v2.get("score_matrix_sha256")!=sha256_file(score_path) or set(v2.get("comparisons",{}))!=set(DOMAINS):
        raise ValueError("Frozen score arrays do not match completed four-model report")
    output=args.output.expanduser().resolve()
    if output.exists():
        raise FileExistsError("Aggregate abstention calibration report exists; refuse overwrite")
    target_names=[
        destination/f"{dom}_{variant}_{coder}_random120_perclass_PRIVATE.csv"
        for dom in DOMAINS for variant in VARIANTS for coder in CODERS
    ]
    if any(p.exists() for p in target_names):
        raise FileExistsError("One or more private per-class results exist; refuse overwrite")

    root=args.project_root.expanduser().resolve()
    original=pd.read_parquet(
        root/"data/processed/07_alignment_pdot_ods_needs.parquet",
        columns=["handle_id","ods_top1","pdot_top1"]
    )
    master=pd.read_csv(coded/"sample_master_private.csv",dtype=str,keep_default_na=False)
    if len(original)!=7830 or len(master)!=450 or master["study_id"].duplicated().any():
        raise ValueError("Frozen corpus/master mismatch")
    idx=master["source_row_index"].astype(int).to_numpy()
    if idx.min()<0 or idx.max()>=7830 or len(set(idx))!=450:
        raise ValueError("Unverified frozen source-row indices")
    if not np.array_equal(
        original["handle_id"].iloc[idx].astype(str).to_numpy(),
        master["handle_id"].to_numpy()
    ):
        raise ValueError("Source handle alignment mismatch")
    strata=master["selection_stratum"].astype(str).to_numpy()
    train=strata=="targeted_enrichment"
    test=strata=="population_random"
    if int(train.sum())!=330 or int(test.sum())!=120:
        raise ValueError("Expected 330 calibration and 120 evaluation cases")
    human={}
    for coder in CODERS:
        a=pd.read_csv(coded/f"coder_{coder}_private.csv",dtype=str,keep_default_na=False)
        if a["study_id"].duplicated().any() or set(a["study_id"])!=set(master["study_id"]):
            raise ValueError("Original coder 450-case roster changed")
        a=a.set_index("study_id").reindex(master["study_id"]).reset_index()
        if not np.array_equal(
            a["private_source_handle"].str.lstrip("'").to_numpy(),
            master["handle_id"].to_numpy()
        ):
            raise ValueError("Original coder source handle changed")
        human[coder]=a

    report={
        "schema_version":1,
        "status":"retrospective_E5_330_calibration_120_evaluation_abstention_two_coders",
        "origin":"previously frozen four E5 raw/centered score matrices",
        "score_matrix_sha256":sha256_file(score_path),
        "four_variant_report_sha256":sha256_file(v2_path),
        "n_calibration_targeted":330,"n_test_random":120,
        "minimum_calibration_coverage":MIN_TRAIN_COVERAGE,
        "objective":"maximize 330-sample macro-F1 of present/predicted ODS or PDOT + NONE, tie break toward coverage",
        "unmodified_legacy_top1_baseline_included":True,
        "none_category":"NONE",
        "confirmatory_claims_permitted":False,
        "comparisons":{}
    }
    with np.load(score_path,allow_pickle=False) as archive:
        for domain in DOMAINS:
            names_original=list(source["domains"][domain]["representations"]
                                  ["legacy_raw"]["top1_category_counts_candidate_unvalidated"])
            if domain=="ods":
                names=list(normalize_codes(names_original))
                replay=list(normalize_codes(original["ods_top1"]))
            else:
                names=[PDOT_ID.get(x,"") for x in names_original]
                replay=[PDOT_ID.get(x,"") for x in original["pdot_top1"]]
            if len(names)!=len(CLASSES[domain])-1 or set(names)!=set(CLASSES[domain])-{NONE}:
                raise ValueError("Descriptor ordering/taxonomy mismatch")
            truth={coder:labels_from_coder(human[coder],domain) for coder in CODERS}
            report["comparisons"][domain]={}
            for variant in VARIANTS:
                key=f"{domain}_{variant}_scores"
                if key not in archive:
                    raise ValueError("Missing frozen scores "+key)
                s=np.asarray(archive[key],dtype=np.float32)
                if s.shape!=(7830,len(names)) or not np.isfinite(s).all():
                    raise ValueError("Invalid candidate scores")
                if variant=="legacy_raw":
                    historical=np.asarray(names,dtype=str)[np.argmax(s,axis=1)]
                    if not np.array_equal(historical,np.asarray(replay,dtype=str)):
                        raise ValueError("Descriptor order does not replay original historical top1")
                split_scores=s[idx]
                result={}
                for coder in CODERS:
                    setting,calibrated,eligible=tune_on_330(
                        split_scores[train],truth[coder][train],names
                    )
                    pred=predict_abstaining(split_scores[test],names,*setting)
                    evaluation=metrics(truth[coder][test],pred,names+[NONE])
                    base=np.asarray(names,dtype=str)[
                        np.argmax(split_scores[test],axis=1)
                    ]
                    raw=metrics(truth[coder][test],base,names+[NONE])
                    filename=f"{domain}_{variant}_{coder}_random120"
                    final=output_metrics(
                        evaluation,private_output(destination,workspace),filename
                    )
                    result[coder]={
                        "threshold_cosine_calibrated_on_enriched":round(setting[0],8),
                        "margin_calibrated_on_enriched":round(setting[1],8),
                        "calibration_eligible_grid_pairs":eligible,
                        "calibration_macro_f1":calibrated["macro_f1_present_or_predicted_classes"],
                        "calibration_coverage":round(float(
                            1-calibrated["no_match_predicted_n"]/330),6),
                        "random_120_forced_top1_accuracy":raw["accuracy"],
                        "random_120_forced_top1_macro_f1":raw["macro_f1_present_or_predicted_classes"],
                        "random_120_after_abstention":final,
                        "random_120_coverage":round(float(1-final["no_match_predicted_n"]/120),6),
                        "random_120_classified_without_abstention_n":120-final["no_match_predicted_n"],
                    }
                report["comparisons"][domain][variant]=result
    report["limitations"]=[
        "The 120 random thesis scores were already inspected across model variants; this is NOT a prospectively untouched test.",
        "The 330 targeted examples overrepresent selected model/faculty categories, so tuned thresholds may not transfer to the population.",
        "Coder A/B thresholds are optimized separately because their decisions are not a signed adjudicated gold standard.",
        "The 60% minimum training coverage is an exploratory guardrail, not a theoretically optimal institutional minimum.",
        "No-match is treated as a valid reference class and exact-match primary categories are scored; secondary labels are not.",
        "Calibrated cosine and margin thresholds are representation-specific; never reuse raw cutoffs after mean-centering.",
        "Candidate official PDOT axes and descriptor provenance still require institutional approval.",
        "No claims of SDG achievement or territorial impact are implied.",
    ]
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root",type=Path,required=True)
    p.add_argument("--private-dir",type=Path,default=Path(
        "data/revision_private/validation"))
    p.add_argument("--scores",type=Path,default=Path(
        "data/revision_private/reviewer_fulltext_reclassification/reclassification_all_7830_PRIVATE.npz"))
    p.add_argument("--source-report",type=Path,default=Path(
        "docs/audits/reviewer_fulltext_reclassification_v1.json"))
    p.add_argument("--v2-report",type=Path,default=Path(
        "docs/audits/reviewer_four_e5_variant_dual_coder_metrics_v2.json"))
    p.add_argument("--private-metrics-dir",type=Path,default=Path(
        "data/revision_private/four_e5_abstention_calibration_v1"))
    p.add_argument("--output",type=Path,default=Path(
        "docs/audits/reviewer_four_e5_abstention_calibration_v1.json"))
    a=p.parse_args()
    report=analyze(a)
    out=write_public(report,a.output,Path(__file__).resolve().parent.parent)
    print("RETROSPECTIVE abstention calibration on 330 targeted cases:",out)
    for domain in DOMAINS:
        print(domain.upper())
        for variant in VARIANTS:
            entries=[]
            for coder in CODERS:
                r=report["comparisons"][domain][variant][coder]
                m=r["random_120_after_abstention"]
                entries.append(
                    f"{coder}: coverage={r['random_120_coverage']:.3f}, "
                    f"accuracy={m['accuracy']:.4f}, "
                    f"macroF1={m['macro_f1_present_or_predicted_classes']:.4f}, "
                    f"NONE(ref/pred)={m['no_match_reference_n']}/{m['no_match_predicted_n']}"
                )
            print(variant," | ".join(entries))
    print("Do not publish as confirmatory model selection or unqualified gains in model validity.")
    print("Private class-level results:",a.private_metrics_dir)

if __name__=="__main__":
    main()
