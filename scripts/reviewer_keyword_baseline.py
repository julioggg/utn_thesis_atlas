#!/usr/bin/env python3
"""Transparent unsupervised TF-IDF keyword/bigram SDG/PDOT/need baseline.

Requires source-verified descriptor manifest and scikit-learn. Compares
keyword lexical similarity with legacy E5 forced top1 categories on EXACT
same original analysis_text. A diagnostic baseline only: it cannot report
precision/F1 before expert labels. Source text and row-level scores stay
on CEDIA. Avoids unverified generic keyword dictionaries.
"""
from __future__ import annotations
import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from reviewer_shared import normalize_codes, private_output, sha256_file, write_public
from reviewer_descriptor_sensitivity import load_verified_manifest


def compare_domain(document_matrix, vectorizer, taxonomy, legacy_categories, domain):
    descriptions=[x["descriptor"] for x in taxonomy]
    queries=vectorizer.transform(descriptions)
    nnz=np.diff(queries.indptr)
    if np.any(nnz<1):
        raise ValueError(f"At least one verified {domain} descriptor has no vocabulary overlap with corpus; cannot score")
    sim=(document_matrix @ queries.T).toarray().astype("float32")
    categories=np.asarray([x["id"] for x in taxonomy])
    indices=np.argsort(-sim,axis=1,kind="stable")
    tops=categories[indices[:,0]]
    runners=categories[indices[:,1]]
    scores=np.take_along_axis(sim,indices[:,:2],axis=1)
    return {
        "domain":domain,"n_documents":len(sim),
        "n_descriptors":len(taxonomy),
        "top1_agreement_with_legacy_forced_labels":round(
            float(np.mean(tops==np.asarray(legacy_categories))),6),
        "original_keyword_classifier_top1_counts":{
            label:int(np.sum(tops==label)) for label in categories
        },
        "top1_top2_margin_distribution":{
            "median":round(float(np.median(scores[:,0]-scores[:,1])),6),
            "mean":round(float(np.mean(scores[:,0]-scores[:,1])),6)
        },
        "unvalidated_first_vs_second_relative_margin_under_0p01":int(
            np.sum(scores[:,0]-scores[:,1] < .01)
        ),
        "top2_label_ids_private_not_exported": True,
        "warning":"Lexical descriptor matching is an unsupervised baseline, not independent ground truth.",
    },tops,sim


def analyze(args):
    from sklearn.feature_extraction.text import TfidfVectorizer
    root=args.project_root.expanduser().resolve()
    workspace=Path(__file__).resolve().parent.parent
    m=args.manifest.expanduser().resolve()
    if not m.is_relative_to((workspace/"data").resolve()):
        raise ValueError("Descriptor manifest must be under ignored revision/data")
    manifest=load_verified_manifest(m)
    df=pd.read_parquet(root/"data/processed/07_alignment_pdot_ods_needs.parquet",
                       columns=["handle_id","analysis_text","ods_top1","pdot_top1","need_top1"])
    if df["handle_id"].isna().any() or df["handle_id"].duplicated().any():
        raise ValueError("Missing/duplicate index IDs")
    corpus=df["analysis_text"].fillna("").astype(str).tolist()
    if sum(not s.strip() for s in corpus):
        raise ValueError("Empty original analysis_text; cannot establish baseline")
    estimator=TfidfVectorizer(
        lowercase=True,strip_accents="unicode",sublinear_tf=True,
        ngram_range=(1,2), min_df=1,max_df=.98,max_features=args.max_features,
        norm="l2",dtype=np.float32
    )
    start=time.perf_counter()
    x=estimator.fit_transform(corpus)
    expected={
        "ods":normalize_codes(df["ods_top1"]),
        "pdot":df["pdot_top1"].astype(str).tolist(),
        "need":df["need_top1"].astype(str).tolist(),
    }
    outcomes={}
    private_arrays={}
    for domain in ("ods","pdot","need"):
        taxa=manifest["taxonomies"][domain]
        if domain!="ods" and set(x["id"] for x in taxa)!=set(expected[domain]):
            raise ValueError("Taxonomy does not match real PDOT/need labels")
        stats,labels,similarity=compare_domain(x,estimator,taxa,expected[domain],domain)
        outcomes[domain]=stats
        private_arrays[domain+"_scores"]=similarity
        private_arrays[domain+"_top1_index"] = np.argmax(similarity,axis=1).astype(np.int16)
    dst=private_output(args.private_dir,workspace)
    np.savez_compressed(dst/"keyword_baseline_scores_PRIVATE.npz",**private_arrays)
    return {
        "schema_version":1,"status":"transparent_unsupervised_keyword_baseline_completed",
        "model":"TF-IDF word 1-2 grams, L2, Unicode accent stripping",
        "original_analysis_input":"07_alignment_pdot_ods_needs.parquet:analysis_text",
        "n_source_theses":len(df),
        "vocabulary_size":len(estimator.vocabulary_),
        "sparse_nnz":int(x.nnz),
        "max_features":args.max_features,
        "descriptor_manifest_sha256":sha256_file(m),
        "elapsed_cpu_seconds":round(time.perf_counter()-start,3),
        "taxonomies":outcomes,
        "limitations":[
            "Source-verified descriptor strings are used for lexical scoring; no invented keywords.",
            "Input is original analysis_text, not verified whole-document content.",
            "Legacy top1 agreement does NOT demonstrate performance; human-coded F1, precision/recall are still pending.",
            "All original analysis texts and row-level score arrays remain private on CEDIA.",
        ]
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root",type=Path,required=True)
    p.add_argument("--manifest",type=Path,
                   default=Path("data/revision_private/descriptor_inventory/verified_descriptors_PRIVATE.json"))
    p.add_argument("--max-features",type=int,default=150000)
    p.add_argument("--private-dir",type=Path,
                   default=Path("data/revision_private/reviewer_keyword_baseline"))
    p.add_argument("--output",type=Path,
                   default=Path("docs/audits/reviewer_keyword_baseline.json"))
    a=p.parse_args()
    if not 1000<=a.max_features<=300000:
        p.error("max_features must be 1000..300000")
    report=analyze(a)
    path=write_public(report,a.output,Path(__file__).resolve().parent.parent)
    print("Keyword baseline aggregate:",path)
    print("This output does not imply label accuracy.")


if __name__=="__main__":
    main()
