#!/usr/bin/env python3
"""Recompute SDG, PDOT and local-need descriptor similarity matrices on CEDIA.

REQUIRES a PRIVATE, SOURCE-VERIFIED manifest of exact original descriptors
and two frozen paraphrases per label. No fabricated taxonomies. Evaluates
original legacy E5 embeddings, descriptor rewording, mean-centering, relative
top-2 ambiguity and abstention CANDIDATES. Does not claim human validation
or exact reproduction of legacy scores unless explicitly verified.
"""
from __future__ import annotations
import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from reviewer_shared import (normalize_codes, private_output, read_original_embeddings,
                             sha256_file, summary, write_public)
from reviewer_stage1_stats import clean_faculties


DOMAINS={"ods":17,"pdot":6,"need":10}
PARAPHRASES=("descriptor","paraphrase_1","paraphrase_2")


def load_verified_manifest(path):
    doc=json.loads(path.read_text(encoding="utf-8"))
    if doc.get("verified") is not True:
        raise ValueError("Descriptor manifest has not been source-verified: STOP, do not invent entries")
    taxonomy=doc.get("taxonomies",{})
    if any(len(taxonomy.get(t,[]))!=n for t,n in DOMAINS.items()):
        raise ValueError("Missing ODS/PDOT/local-need categories or incorrect taxonomy sizes")
    for domain in DOMAINS:
        group=taxonomy[domain]
        ids=[x.get("id","").strip() for x in group]
        if len(set(ids))!=len(group) or any(not x for x in ids):
            raise ValueError("Missing or repeated taxonomy IDs")
        if domain=="ods" and set(ids)!={f"ODS {i}" for i in range(1,18)}:
            raise ValueError("17 SDG category IDs are not exact")
        for row in group:
            for field in (*PARAPHRASES,"source_document","source_location","verified_by"):
                if not isinstance(row.get(field),str) or not row[field].strip():
                    raise ValueError(f"Missing verified {field} in {domain}")
    if not doc.get("official_pdot_edition") or not doc.get("needs_definition_source"):
        raise ValueError("PDOT edition and local-needs documentary provenance are mandatory")
    if doc.get("model_query_prefix") not in ("query: ","passage: "):
        raise ValueError("Manifest must declare query or passage prefix")
    return doc


def normalized(x):
    y=np.asarray(x,dtype=np.float32)
    r=np.linalg.norm(y,axis=1,keepdims=True)
    if not np.isfinite(y).all() or (r<1e-10).any():
        raise ValueError("Invalid embedding matrix")
    return y/r


def encode_descriptions(texts, model, tokenizer, torch, prefix, batch_size):
    vecs=[]
    for i in range(0,len(texts),batch_size):
        tagged=[prefix+t for t in texts[i:i+batch_size]]
        packed=tokenizer(tagged,return_attention_mask=True,
                         padding=True,truncation=False,return_tensors="pt")
        if packed["input_ids"].shape[1]>512:
            raise ValueError("Descriptor exceeds 512-token model limit")
        batch={k:v.to(model.device) for k,v in packed.items()}
        with torch.inference_mode():
            emb=model(**batch).last_hidden_state.float()
            mask=batch["attention_mask"].unsqueeze(-1)
            mean=(emb*mask).sum(dim=1)/mask.sum(dim=1).clamp(min=1)
            vectors=torch.nn.functional.normalize(mean,dim=1,p=2)
        vecs.extend(vectors.cpu().numpy().astype("float32"))
    return np.stack(vecs)


def summarise_domain(scores, categories, legacy_labels, domain, center_scores=None):
    if scores.ndim !=2 or scores.shape[1] != len(categories):
        raise ValueError("Wrong descriptor score matrix shape")
    n=len(scores)
    order=np.argsort(-scores,axis=1,kind="stable")
    rank1=order[:,0]
    rank2=order[:,1]
    best=np.take_along_axis(scores,rank1[:,None],axis=1).ravel()
    runner=np.take_along_axis(scores,rank2[:,None],axis=1).ravel()
    tops=np.asarray(categories)[rank1]
    original=np.asarray(legacy_labels).astype(str)
    acc=float(np.mean(tops==original))
    result={
        "n":n,"candidate_top1_agreement_with_legacy_forced_labels":round(acc,6),
        "top1_score":summary(best),
        "top1_top2_margin":summary(best-runner),
        "candidate_mean_centering_applied":center_scores is not None,
        "unvalidated_top1_category_counts":{
            label:int(np.sum(tops==label)) for label in categories
        },
        "relative_second_label_counts":{
            f"gap_le_{limit:.3f}":int(np.sum((best-runner)<=limit))
            for limit in (.002,.005,.01,.02)
        },
        "top1_absolute_score_abstention_candidates":{
            f"{threshold:.2f}":int(np.sum(best<threshold))
            for threshold in (.75,.78,.80,.82)
        },
        "warning":"Candidate coverage and label agreement are NOT accuracy, F1 or calibrated thresholds.",
    }
    if center_scores is not None:
        center_label=np.asarray(categories)[np.argmax(center_scores,axis=1)]
        result["top1_changed_after_mean_centering_n"]=int(np.sum(center_label!=tops))
        result["centered_unvalidated_top1_counts"]={
            label:int(np.sum(center_label==label)) for label in categories
        }
    if domain=="ods" and "ODS 4" in categories:
        result["sdg4_original_n"]=int(np.sum(original=="ODS 4"))
        result["sdg4_proposed_n"]=int(np.sum(tops=="ODS 4"))
        if center_scores is not None:
            result["sdg4_centered_n"]=int(np.sum(center_label=="ODS 4"))
    return result,tops


def sensitivity(x, df, descriptor_document, tokenizer, model, torch, args):
    source_labels={
        "ods":normalize_codes(df["ods_top1"]),
        "pdot":df["pdot_top1"].astype(str).tolist(),
        "need":df["need_top1"].astype(str).tolist(),
    }
    raw_vectors=normalized(x)
    population_mean=raw_vectors.astype("float64").mean(axis=0).astype("float32")
    centered_vectors=normalized(raw_vectors-population_mean)
    private_matrices={}
    report={}
    for domain in DOMAINS:
        entries=descriptor_document["taxonomies"][domain]
        names=[row["id"] for row in entries]
        if domain!="ods" and set(names)!=set(source_labels[domain]):
            raise ValueError(f"Original {domain} label IDs differ from verified descriptor manifest")
        variants={}
        for field in PARAPHRASES:
            sentences=[row[field] for row in entries]
            emb=encode_descriptions(sentences,model,tokenizer,torch,
                                    descriptor_document["model_query_prefix"],args.batch_size)
            if emb.shape[1]!=raw_vectors.shape[1]:
                raise ValueError("Descriptor and corpus encoder dimensions differ")
            score=raw_vectors@emb.T
            variants[field]=score
            private_matrices[f"{domain}_{field}"]=score.astype("float32")
            if field=="descriptor":
                centered_desc=normalized(emb-population_mean)
                centered_scores=centered_vectors@centered_desc.T
                private_matrices[f"{domain}_centered"]=centered_scores.astype("float32")
                report[domain],baseline_top=summarise_domain(
                    score,names,source_labels[domain],domain,centered_scores
                )
            else:
                alt_top=np.asarray(names)[np.argmax(score,axis=1)]
                report[domain]["paraphrase_agreement_vs_verified_descriptor_"+field]=round(
                    float(np.mean(alt_top==baseline_top)),6
                )
                report[domain]["paraphrase_label_flips_"+field]=int(np.sum(alt_top!=baseline_top))
        med=[float(np.median(np.max(score,axis=1))) for score in variants.values()]
        report[domain]["median_best_similarity_by_description_variant"]={
            key:round(value,6) for key,value in zip(PARAPHRASES,med)
        }
    return report,private_matrices


def analyze(args):
    import torch
    from transformers import AutoModel,AutoTokenizer
    workspace=Path(__file__).resolve().parent.parent
    root=args.project_root.expanduser().resolve()
    manifest_path=args.manifest.expanduser().resolve()
    if not manifest_path.is_relative_to((workspace/"data").resolve()):
        raise ValueError("Verified descriptor strings must remain under ignored data/")
    descriptor_document=load_verified_manifest(manifest_path)
    frame=pd.read_parquet(root/"data/processed/07_alignment_pdot_ods_needs.parquet",
                          columns=["handle_id","faculty","career",
                                   "ods_top1","pdot_top1","need_top1"])
    if frame["handle_id"].isna().any() or frame["handle_id"].duplicated().any():
        raise ValueError("Original corpus handles not unique/nonempty")
    old,align=read_original_embeddings(root,len(frame))
    device="cuda" if args.device=="cuda" else "cpu"
    if device=="cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA not available")
    tokenizer=AutoTokenizer.from_pretrained(args.model,use_fast=True,
                                            local_files_only=args.local_files_only)
    dtype=torch.float16 if device=="cuda" else torch.float32
    model=AutoModel.from_pretrained(args.model,dtype=dtype,use_safetensors=True,
                                    local_files_only=args.local_files_only).to(device)
    model.eval()
    start=time.perf_counter()
    report,matrices=sensitivity(np.asarray(old,dtype="float32"),frame,
                                 descriptor_document,tokenizer,model,torch,args)
    output=private_output(args.private_dir,workspace)
    np.savez_compressed(output/"descriptor_scores_PRIVATE.npz",**matrices)
    return {
        "schema_version":1,
        "status":"completed_descriptor_wording_mean_centered_sensitivity_unvalidated",
        "dataset_rows":len(frame),
        "model":args.model,"device":device,
        "model_query_prefix":descriptor_document["model_query_prefix"],
        "descriptor_manifest_sha256":sha256_file(manifest_path),
        "provenance_check":align,
        "seconds_excluding_model_load":round(time.perf_counter()-start,3),
        "domains":report,
        "limitations":[
            "This is a new descriptor scoring protocol; not an exact replay of legacy scores unless source encoder/prefix/pooling match.",
            "Descriptor paraphrase variants were separately source-reviewed and require frozen preregistration.",
            "Mean-centering changes cosine scales; old uncalibrated thresholds do NOT transfer.",
            "Top1 agreement with old forced labels is NOT expert label accuracy.",
            "Calibration of abstention, top-2/multi-label relevance, and any F1 require independent expert reference labels.",
            "All per-row similarity matrices and descriptor strings remain in ignored CEDIA data/.",
        ],
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root",type=Path,required=True)
    p.add_argument("--manifest",type=Path,
                   default=Path("data/revision_private/descriptor_inventory/verified_descriptors_PRIVATE.json"))
    p.add_argument("--model",default="intfloat/multilingual-e5-large")
    p.add_argument("--device",choices=("cuda","cpu"),default="cuda")
    p.add_argument("--batch-size",type=int,default=1)
    p.add_argument("--local-files-only",action="store_true")
    p.add_argument("--private-dir",type=Path,
                   default=Path("data/revision_private/reviewer_descriptors"))
    p.add_argument("--output",type=Path,
                   default=Path("docs/audits/reviewer_descriptor_sensitivity.json"))
    args=p.parse_args()
    if args.batch_size<1 or args.batch_size>8:
        p.error("Batch size must be 1..8 for 10 GiB MIG")
    report=analyze(args)
    write_public(report,args.output,Path(__file__).resolve().parent.parent)
    print("Descriptor sensitivity completed; aggregate report:",args.output)
    print("Private per-thesis scores never leave ignored data/.")


if __name__=="__main__":
    main()
