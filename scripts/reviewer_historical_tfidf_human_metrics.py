#!/usr/bin/env python3
"""Reviewer-3 lexical TF-IDF ODS/PDOT baseline using recovered HISTORICAL descriptors.

Uses exact descriptor dictionaries from the frozen original utn_atlas_pipeline.py
source and a verified numerical E5 historical replay. This identifies what the
historical program USED. It does NOT assert those PDOT axes are legally
identical to the 2024/2026 Imbabura official PDOT components.

Fit unlabeled TF-IDF vocabulary/IDF on 7,710 source texts excluding the 120
probability-sampled evaluation theses, then transform all 7,830 texts. No
human labels are used in fitting or model selection. Encode ORIGINAL
analysis_text (legacy input, not verified entire PDFs). Compare top-1
source-descriptor cosine against human A and B separately; the 330 enriched
cases are descriptive, not prevalence weighted. All case-level outputs private.
No committee consensus or human F1 can be inferred from E5 self-agreement.
"""
from __future__ import annotations
import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from audit_annotation_progress import inspect_files
from reviewer_legacy_alignment_replay import freeze_original_dicts
from reviewer_fulltext_reclassification import replay_gate
from reviewer_human_validation_metrics import (
    PDOT_ID, NONE, labels_from_coder, metrics, output_metrics
)
from reviewer_shared import (
    normalize_codes, private_output, sha256_file, write_public
)

SPLITS=("random_120","enriched_330","pooled_450_descriptive_only")
SOURCE_DOMAINS=("ods","pdot")
N=7830


def prepare_lexical_texts(taxonomy,domain):
    if not isinstance(taxonomy,dict) or len(taxonomy)!=(
        17 if domain=="ods" else 6
    ):
        raise ValueError("Unexpected historical descriptor taxonomy size")
    names=list(taxonomy)
    if len(set(names))!=len(names) or any(
        not isinstance(k,str) or not isinstance(v,str) or
        not k.strip() or not v.strip() for k,v in taxonomy.items()
    ):
        raise ValueError("Malformed historical source descriptors")
    descriptions=[name+". "+taxonomy[name] for name in names]
    if domain=="ods":
        canon=list(normalize_codes(names))
        allowed={f"ODS {i}" for i in range(1,18)}
    else:
        canon=[PDOT_ID.get(k,"") for k in names]
        allowed={f"PDOT {i}" for i in range(1,7)}
    if len(set(canon))!=len(names) or set(canon)!=allowed:
        raise ValueError("Historical category labels do not match human codebook")
    return names,canon,descriptions


def fit_lexical_baseline(corpus,fit_mask,queries,max_features=150000):
    from sklearn.feature_extraction.text import TfidfVectorizer
    texts=list(corpus)
    train=np.asarray(fit_mask,dtype=bool)
    if train.ndim!=1 or train.size!=len(texts) or not train.any():
        raise ValueError("Missing unsupervised TF-IDF training data")
    if any(not isinstance(x,str) or not x.strip() for x in texts):
        raise ValueError("Empty historical analysis_text")
    vec=TfidfVectorizer(
        lowercase=True,strip_accents="unicode",sublinear_tf=True,
        ngram_range=(1,2),min_df=1,max_df=0.98,
        max_features=max_features,norm="l2",dtype=np.float32
    )
    vec.fit([texts[i] for i in np.flatnonzero(train)])
    matrix=vec.transform(texts)
    q=vec.transform(queries)
    if np.any(np.diff(q.indptr)==0):
        raise ValueError("One or more descriptor queries lack vocabulary overlap")
    scores=(matrix @ q.T).toarray().astype(np.float32)
    if not np.isfinite(scores).all() or scores.shape!=(len(texts),len(queries)):
        raise ValueError("Invalid TF-IDF baseline similarity matrix")
    return scores,len(vec.vocabulary_),int(matrix.nnz)


def analyze(args):
    from sklearn.feature_extraction.text import TfidfVectorizer
    workspace=Path(__file__).resolve().parent.parent
    private=(workspace/"data/revision_private").resolve()
    coder_dir=args.private_dir.expanduser().resolve()
    metric_dir=args.private_metrics_dir.expanduser().resolve()
    inventory_path=args.inventory.expanduser().resolve()
    for path in (coder_dir,metric_dir,inventory_path):
        if not path.is_relative_to(private):
            raise ValueError("All case-level files must remain in ignored CEDIA private data")
    if not inventory_path.is_file():
        raise FileNotFoundError("Frozen descriptor inventory required")
    if not inspect_files(coder_dir)["all_annotations_finished"]:
        raise ValueError("Original 450 A/B coding not complete")

    original=args.project_root.expanduser().resolve()
    inventory=json.loads(inventory_path.read_text(encoding="utf-8"))
    taxonomies,source_hash=freeze_original_dicts(inventory,original)
    replay_file=args.replay_report.expanduser().resolve()
    replay=json.loads(replay_file.read_text(encoding="utf-8"))
    replay_gate(replay)
    if replay.get("source_file_sha256")!=source_hash or (
        replay.get("source_inventory_sha256")!=sha256_file(inventory_path)
    ):
        raise ValueError("Historical descriptor source does not match numerical replay")
    if args.output.expanduser().resolve().exists():
        raise FileExistsError("Baseline aggregate report exists; no silent overwrite")
    private_npz=metric_dir/"historical_source_tfidf_scores_PRIVATE.npz"
    expected=[
        metric_dir/f"historical_tfidf_{domain}_vs_{coder}_{split}_perclass_PRIVATE.csv"
        for domain in SOURCE_DOMAINS for coder in ("A","B") for split in SPLITS
    ]
    if private_npz.exists() or any(x.exists() for x in expected):
        raise FileExistsError("Historical TF-IDF baseline files already exist; refuse overwrite")

    master=pd.read_csv(coder_dir/"sample_master_private.csv",
                       dtype=str,keep_default_na=False)
    if len(master)!=450 or master["study_id"].duplicated().any():
        raise ValueError("Frozen human sample must contain 450 unique IDs")
    indices=master["source_row_index"].astype(int).to_numpy()
    if indices.min()<0 or indices.max()>=N or len(set(indices.tolist()))!=450:
        raise ValueError("Invalid sample source indices")
    strata=master["selection_stratum"].to_numpy(dtype=str)
    test=strata=="population_random"
    enrich=strata=="targeted_enrichment"
    if test.sum()!=120 or enrich.sum()!=330:
        raise ValueError("Expected frozen 120 random / 330 targeted cases")

    df=pd.read_parquet(
        original/"data/processed/07_alignment_pdot_ods_needs.parquet",
        columns=["handle_id","analysis_text","ods_top1","pdot_top1"]
    )
    if len(df)!=N or df["handle_id"].isna().any() or (
        df["handle_id"].duplicated().any()
    ):
        raise ValueError("Historical population source index invalid")
    if not np.array_equal(
        df["handle_id"].iloc[indices].astype(str).to_numpy(),
        master["handle_id"].to_numpy()
    ):
        raise ValueError("Historical text and frozen human sample handle mismatch")

    coders={}
    for coder in ("A","B"):
        rows=pd.read_csv(coder_dir/f"coder_{coder}_private.csv",
                         dtype=str,keep_default_na=False)
        if rows["study_id"].duplicated().any() or set(rows["study_id"])!=set(master["study_id"]):
            raise ValueError("A/B study IDs differ from original frozen sample")
        rows=rows.set_index("study_id").reindex(master["study_id"]).reset_index()
        if not np.array_equal(
            rows["private_source_handle"].str.lstrip("'").to_numpy(),
            master["handle_id"].to_numpy()
        ):
            raise ValueError("Coder source handles do not match frozen sample")
        coders[coder]=rows

    train_mask=np.ones(N,dtype=bool)
    train_mask[indices[test]]=False
    if train_mask.sum()!=7710:
        raise ValueError("TF-IDF fit must exclude all 120 held-out texts")
    corpus=df["analysis_text"].fillna("").astype(str).tolist()
    if any(not s.strip() for s in corpus):
        raise ValueError("Empty original analysis_text; cannot fit lexical baseline")
    start=time.perf_counter()
    # Use the SAME frozen TF-IDF IDF vocabulary for ODS and PDOT, as both
    # domains are compared over the same 7,830 original thesis texts.
    vec=TfidfVectorizer(
        lowercase=True,strip_accents="unicode",sublinear_tf=True,
        ngram_range=(1,2),min_df=1,max_df=0.98,
        max_features=args.max_features,norm="l2",dtype=np.float32
    )
    vec.fit([corpus[i] for i in np.flatnonzero(train_mask)])
    matrix=vec.transform(corpus)
    output={
        "schema_version":1,
        "status":"historical_source_lexical_TFIDF_ODS_PDOT_AB_validation_exploratory",
        "original_n":N,
        "human_n":450,"random_heldout_n":120,"targeted_n":330,
        "input_text":"frozen legacy analysis_text, not full-text PDF",
        "fit_unlabeled_texts_n":7710,
        "heldout_texts_excluded_from_unsupervised_fit":120,
        "human_labels_used_for_tfidf_fit":False,
        "descriptor_source_sha256":source_hash,
        "descriptor_inventory_sha256":sha256_file(inventory_path),
        "historical_replay_report_sha256":sha256_file(replay_file),
        "vocabulary_size":len(vec.vocabulary_),
        "sparse_document_nnz":int(matrix.nnz),
        "tfidf":{"word_ngrams":[1,2],"min_df":1,"max_df":0.98,
                 "max_features":args.max_features,"strip_accents":"unicode",
                 "sublinear_tf":True,"L2_normalized":True},
        "comparisons":{},
    }
    arrays={}
    split_masks={
        "random_120":test,"enriched_330":enrich,
        "pooled_450_descriptive_only":np.ones(450,dtype=bool)
    }
    for domain in SOURCE_DOMAINS:
        _,names,queries=prepare_lexical_texts(taxonomies[domain],domain)
        q=vec.transform(queries)
        query_nnz=np.diff(q.indptr)
        if np.any(query_nnz<1):
            raise ValueError(f"At least one {domain} historical descriptor has no TF-IDF overlap")
        scores=(matrix @ q.T).toarray().astype(np.float32)
        if scores.shape!=(N,len(names)) or not np.isfinite(scores).all():
            raise ValueError("Lexical score array invalid")
        arrays[f"{domain}_scores"]=scores
        arrays[f"{domain}_source_names"]=np.asarray(names,dtype=str)
        prediction=np.asarray(names,dtype=str)[np.argmax(scores,axis=1)]
        output["comparisons"][domain]={
            "historical_descriptor_classes":len(names),
            "descriptor_query_nnz_min":int(query_nnz.min()),
            "forced_top1_has_no_abstention":True,
            "population_class_counts":{
                name:int(np.count_nonzero(prediction==name)) for name in names
            },
            "human_coders":{},
        }
        for coder in ("A","B"):
            truth=labels_from_coder(coders[coder],domain)
            output["comparisons"][domain]["human_coders"][coder]={}
            for split,mask in split_masks.items():
                met=metrics(truth[mask],prediction[indices][mask],names+[NONE])
                metric=output_metrics(
                    met,private_output(metric_dir,workspace),
                    f"historical_tfidf_{domain}_vs_{coder}_{split}"
                )
                output["comparisons"][domain]["human_coders"][coder][split]=metric
    if len(arrays)!=4:
        raise ValueError("Expected two frozen lexical score matrices and two taxonomy orders")
    private_output(metric_dir,workspace)
    np.savez_compressed(private_npz,**arrays)
    output["elapsed_cpu_seconds"]=round(time.perf_counter()-start,3)
    output["limitations"]=[
        "The lexical baseline uses EXACT historically reconstructed source descriptors, not separately approved official PDOT terminology.",
        "PDOT analytical categories may differ from the official provincial plan, requiring separate expert validation.",
        "A and B are correlated human references, not an adjudicated 450-case gold standard.",
        "No positive sustainability impact can be inferred from lexical or semantic similarity.",
        "No text PDF or thesis identifier was published; all raw similarity arrays stay in private CEDIA data.",
        "The 330 selected enriched cases are not representative of the original thesis population.",
        "No threshold was tuned and the top-1 lexical baseline cannot abstain.",
        "This model uses historical analysis_text, not entire theses, and differs from fulltext E5 both in features and model.",
        "Historical text preprocessing may include truncation and boilerplate.",
    ]
    return output


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root",type=Path,required=True)
    p.add_argument("--inventory",type=Path,default=Path(
        "data/revision_private/descriptor_inventory/descriptor_source_candidates_PRIVATE.json"))
    p.add_argument("--replay-report",type=Path,default=Path(
        "docs/audits/reviewer_legacy_alignment_replay.json"))
    p.add_argument("--private-dir",type=Path,default=Path(
        "data/revision_private/validation"))
    p.add_argument("--private-metrics-dir",type=Path,default=Path(
        "data/revision_private/reviewer_historical_tfidf_human_metrics_v1"))
    p.add_argument("--max-features",type=int,default=150000)
    p.add_argument("--output",type=Path,default=Path(
        "docs/audits/reviewer_historical_tfidf_human_metrics_v1.json"))
    a=p.parse_args()
    if not 10000<=a.max_features<=300000:
        p.error("max-features must be 10000..300000")
    report=analyze(a)
    out=write_public(report,a.output,Path(__file__).resolve().parent.parent)
    print("HISTORICAL TEXT TF-IDF vs independent human A/B:",out)
    print("This is lexical matching to SOURCE descriptors; PDOT policy source still under review.")
    for domain in SOURCE_DOMAINS:
        print(domain.upper())
        for coder in ("A","B"):
            for split in ("random_120","enriched_330"):
                met=report["comparisons"][domain]["human_coders"][coder][split]
                print(coder,split,met["n"],"accuracy",met["accuracy"],
                      "macro_F1",met["macro_f1_present_or_predicted_classes"])
    print("Private per-class precision/recall/F1 under:",a.private_metrics_dir)

if __name__=="__main__":
    main()
