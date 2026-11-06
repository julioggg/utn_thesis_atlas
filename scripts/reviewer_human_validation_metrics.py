#!/usr/bin/env python3
"""Reviewer-requested VALIDATION METRICS once human worksheets are complete.

STRICT HUMAN-GROUND-TRUTH GATE. No synthetic/pseudo labels are used.
Separates 330 targeted-enrichment calibration rows from 120 independent
simple-random held-out rows. Cohen kappa reports inter-rater agreement.
Adjudicated reference is separately provided by human experts. This
program refuses to compute precision/recall/F1 before adjudication.
All per-label tables, confusions and row-level data remain private on CEDIA.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd

from reviewer_shared import normalize_codes, private_output, read_original_embeddings, summary, write_public
from audit_annotation_progress import inspect_files

PDOT_ID={
    "Sistema Físico Ambiental":"PDOT 1",
    "Sistema Socio Cultural":"PDOT 2",
    "Sistema Económico Productivo":"PDOT 3",
    "Asentamientos Humanos Movilidad Energía Conectividad":"PDOT 4",
    "Sistema Político Institucional":"PDOT 5",
    "Ejes Transversales":"PDOT 6",
}
NONE="NONE"


def labels_from_coder(df,domain):
    result=[]
    prefix="sdg" if domain=="ods" else "pdot"
    allowed={f"ODS {i}" for i in range(1,18)} if domain=="ods" else {
        f"PDOT {i}" for i in range(1,7)}
    for _,row in df.iterrows():
        primary=str(row[prefix+"_primary"]).strip().upper()
        flag=str(row[prefix+"_no_match"]).strip().lower()
        if flag not in ("yes","no",""):
            raise ValueError("Invalid no_match flag")
        if flag=="yes" and primary:
            raise ValueError("No-match contradiction in expert coding")
        if flag=="yes":
            result.append(NONE)
        elif primary in allowed:
            result.append(primary)
        else:
            raise ValueError("Expert annotations incomplete or invalid")
    return np.asarray(result,dtype=str)


def agreement(a,b):
    a=np.asarray(a,dtype=str)
    b=np.asarray(b,dtype=str)
    if len(a)!=len(b) or len(a)==0:
        raise ValueError("Reviewer label arrays not matched")
    labels=sorted(set(a)|set(b))
    po=float(np.mean(a==b))
    pa=np.array([np.mean(a==x) for x in labels])
    pb=np.array([np.mean(b==x) for x in labels])
    pe=float(pa@pb)
    kappa=(po-pe)/(1-pe) if pe<1-1e-12 else None
    return {
        "n":len(a),"observed_agreement":round(po,6),
        "chance_agreement":round(pe,6),
        "cohen_kappa":None if kappa is None else round(float(kappa),6),
        "classes_observed":len(labels),
        "interpretation":"Inter-rater agreement, not algorithm predictive validity.",
    }


def metrics(truth,pred,classes):
    a=np.asarray(truth,dtype=str)
    b=np.asarray(pred,dtype=str)
    if len(a)!=len(b):
        raise ValueError("Prediction and human labels are not matched")
    table=[]
    for label in classes:
        tp=int(np.sum((a==label)&(b==label)))
        fp=int(np.sum((a!=label)&(b==label)))
        fn=int(np.sum((a==label)&(b!=label)))
        n=tp+fn
        precision=tp/(tp+fp) if tp+fp else 0.
        recall=tp/n if n else 0.
        f1=2*precision*recall/(precision+recall) if (precision+recall) else 0.
        table.append({
            "class":label,"reference_n":n,"predicted_n":tp+fp,
            "tp":tp,"fp":fp,"fn":fn,
            "precision":precision,"recall":recall,"f1":f1,
            "f1_defined_for_reference_or_predicted_class":bool(n or tp+fp),
        })
    valid=[x["f1"] for x in table
           if x["f1_defined_for_reference_or_predicted_class"]]
    return {
        "n":len(a),
        "accuracy":round(float(np.mean(a==b)),6),
        "macro_f1_present_or_predicted_classes":round(float(np.mean(valid)),6)
        if valid else None,
        "no_match_reference_n":int(np.sum(a==NONE)),
        "no_match_predicted_n":int(np.sum(b==NONE)),
        "per_class_private":table,
        "macro_precision_including_all_listed_classes":round(
            float(np.mean([x["precision"] for x in table])),6),
        "macro_recall_including_all_listed_classes":round(
            float(np.mean([x["recall"] for x in table])),6),
        "macro_f1_including_all_listed_classes":round(
            float(np.mean([x["f1"] for x in table])),6),
    }


def thresholds_from_calibration(scores,truth,category_names):
    m=np.asarray(scores,dtype=np.float64)
    if not np.isfinite(m).all():
        raise ValueError("Nonfinite descriptor scores")
    order=np.argsort(-m,axis=1)
    top=order[:,0]
    best=m[np.arange(len(m)),top]
    runner=m[np.arange(len(m)),order[:,1]]
    gap=best-runner
    values=np.unique(np.quantile(best,[0,.1,.2,.3,.4,.5]))
    margins=np.unique(np.quantile(gap,[0,.1,.25,.5]))
    categories=list(category_names)+[NONE]
    best_setting=None
    best_metric=-1.
    for threshold in values:
        for margin in margins:
            predictions=np.asarray(category_names)[top].astype(str)
            predictions[(best<threshold)|(gap<margin)]=NONE
            val=metrics(truth,predictions,categories)
            f1=float(val["macro_f1_present_or_predicted_classes"] or 0.)
            if f1>best_metric+1e-12:
                best_metric=f1
                best_setting=(float(threshold),float(margin))
    return best_setting,best_metric


def output_metrics(metric,private_dir,key):
    import pandas as pd
    table=metric.pop("per_class_private")
    pd.DataFrame(table).to_csv(private_dir/f"{key}_perclass_PRIVATE.csv",index=False)
    return metric


def evaluate(args):
    root=args.project_root.expanduser().resolve()
    workspace=Path(__file__).resolve().parent.parent
    private=args.private_dir.expanduser().resolve()
    report_progress, _ = inspect_files(private)
    # inspect_files returns report and a cross-check count; verify full completion.
    if not report_progress["all_annotations_finished"]:
        raise RuntimeError("Both 450-thesis coder worksheets are NOT finished: cannot compute validation.")
    master=pd.read_csv(private/"sample_master_private.csv",dtype=str,keep_default_na=False)
    A=pd.read_csv(private/"coder_A_private.csv",dtype=str,keep_default_na=False)
    B=pd.read_csv(private/"coder_B_private.csv",dtype=str,keep_default_na=False)
    A=A.set_index("study_id").reindex(master["study_id"]).reset_index()
    B=B.set_index("study_id").reindex(master["study_id"]).reset_index()
    results={"schema_version":1,"status":"human_coder_agreement_completed",
             "coder_freeze_explicitly_confirmed":True,
             "n_sampled":len(master),
             "inter_rater":{
                 domain:agreement(labels_from_coder(A,domain),labels_from_coder(B,domain))
                 for domain in ("ods","pdot")
             },
             "model_evaluation_performed":False}
    if args.adjudicated is None:
        results["notes"]=[
            "Both coders completed their sheets, but no adjudicated human reference was supplied.",
            "Inter-coder kappa is NOT classifier precision/recall/F1."
        ]
        return results
    adjudicated_path=args.adjudicated.expanduser().resolve()
    if not adjudicated_path.is_relative_to((workspace/"data").resolve()):
        raise ValueError("Adjudicated reference must remain in private ignored data/")
    adjudicated=pd.read_csv(adjudicated_path,dtype=str,keep_default_na=False)
    if adjudicated["study_id"].duplicated().any() or set(adjudicated["study_id"])!=set(master["study_id"]):
        raise ValueError("Human adjudication IDs missing, extra or repeated")
    adjudicated=adjudicated.set_index("study_id").reindex(master["study_id"]).reset_index()
    source=pd.read_parquet(root/"data/processed/07_alignment_pdot_ods_needs.parquet",
                           columns=["handle_id","ods_top1","pdot_top1"])
    n,align=read_original_embeddings(root,len(source))
    rows=master["source_row_index"].astype(int).to_numpy()
    if len(set(rows.tolist()))!=len(rows) or rows.min()<0 or rows.max()>=n:
        raise ValueError("Invalid frozen private sample indices")
    if not np.array_equal(source["handle_id"].iloc[rows].astype(str).to_numpy(),
                          master["handle_id"].to_numpy()):
        raise ValueError("Sample handle positions do not align with original analytical corpus")
    strata=master["selection_stratum"].astype(str).to_numpy()
    random_mask=strata=="population_random"
    enrich_mask=strata=="targeted_enrichment"
    if random_mask.sum()!=120 or enrich_mask.sum()!=330:
        raise ValueError("Unexpected frozen sample random/enriched split")
    original={
        "ods":np.asarray(normalize_codes(source["ods_top1"]))[rows],
        "pdot":source["pdot_top1"].map(PDOT_ID).to_numpy(dtype=str)[rows],
    }
    if not np.isin(original["pdot"],list(PDOT_ID.values())).all():
        raise ValueError("Unrecognized original PDOT label")
    where={"heldout_probability_sample":random_mask,
           "enriched_calibration_sample":enrich_mask,
           "pooled_sample_descriptive_only":np.ones(len(rows),dtype=bool)}
    outdir=private_output(args.private_metrics_dir,workspace)
    results["human_adjudication_received"]=True
    results["model_evaluation_performed"]=True
    results["model_family"]="original forced top1 E5 legacy"
    results["source_provenance"]=align
    results["baseline"]={}
    for domain in ("ods","pdot"):
        truth=labels_from_coder(adjudicated,domain)
        classes=([f"ODS {i}" for i in range(1,18)] if domain=="ods"
                 else [f"PDOT {i}" for i in range(1,7)])+[NONE]
        results["baseline"][domain]={}
        for split,mask in where.items():
            met=metrics(truth[mask],original[domain][mask],classes)
            results["baseline"][domain][split]=output_metrics(
                met,outdir,f"legacy_{domain}_{split}")
    if args.descriptor_scores:
        files=args.descriptor_scores.expanduser().resolve()
        if not files.is_relative_to((workspace/"data").resolve()):
            raise ValueError("Descriptor scores must be private")
        results["descriptor_thresholds"]={}
        with np.load(files,allow_pickle=False) as source_npz:
            for domain in ("ods","pdot"):
                name=f"{domain}_descriptor"
                if name not in source_npz:
                    raise ValueError("Missing expected descriptor score matrix")
                score_all=source_npz[name]
                if score_all.shape[0]!=n:
                    raise ValueError("Descriptor score rows do not match original corpus")
                matrix=score_all[rows]
                truth=labels_from_coder(adjudicated,domain)
                names=[f"ODS {i}" for i in range(1,18)] if domain=="ods" else list(PDOT_ID.values())
                # The manifest uses original source label order, which for PDOT
                # is NOT guaranteed to match this hard-coded list. Require an
                # explicit taxonomy order below to avoid silently wrong labels.
                if domain=="pdot":
                    raise RuntimeError("PDOT descriptor score order requires verified manifest mapping. Refusing inference.")
                (threshold,margin),train_f1=thresholds_from_calibration(
                    matrix[enrich_mask],truth[enrich_mask],names
                )
                ranking=np.argsort(-matrix,axis=1)
                best=matrix[np.arange(len(rows)),ranking[:,0]]
                second=matrix[np.arange(len(rows)),ranking[:,1]]
                pred=np.asarray(names)[ranking[:,0]].astype(str)
                pred[(best<threshold)|((best-second)<margin)]=NONE
                results["descriptor_thresholds"][domain]={
                    "global_threshold_calibrated_on_enriched":round(threshold,7),
                    "global_margin_calibrated_on_enriched":round(margin,7),
                    "enriched_calibration_macro_f1":round(train_f1,6),
                    "heldout_random":output_metrics(
                        metrics(truth[random_mask],pred[random_mask],names+[NONE]),
                        outdir,f"descriptor_{domain}_heldout"),
                }
    results["limitations"]=[
        "The 120 thesis random test sample yields uncertain rare-class metrics; report CIs and class supports.",
        "The 330 enriched cases are not representative of original class prevalences; pooled metrics are descriptive only.",
        "Expert labels must be truly independent, adjudicated and source-documented.",
        "Do not imply that a forced top1 label is sustainability impact.",
        "Detailed per-class metrics stay in private data for controlled manuscript release.",
    ]
    return results


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root",type=Path,required=True)
    p.add_argument("--private-dir",type=Path,
                   default=Path("data/revision_private/validation"))
    p.add_argument("--adjudicated",type=Path)
    p.add_argument("--descriptor-scores",type=Path)
    p.add_argument("--coders-frozen",action="store_true",required=True)
    p.add_argument("--private-metrics-dir",type=Path,
                   default=Path("data/revision_private/reviewer_validation_metrics"))
    p.add_argument("--output",type=Path,
                   default=Path("docs/audits/reviewer_human_validation.json"))
    a=p.parse_args()
    if not a.coders_frozen:
        p.error("Human coding files must be independently completed and frozen first")
    result=evaluate(a)
    write_public(result,a.output,Path(__file__).resolve().parent.parent)
    print("Human evaluation status:",result["status"])
    print("Model evaluation completed:",result["model_evaluation_performed"])


if __name__=="__main__":
    main()
