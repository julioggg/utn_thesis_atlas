#!/usr/bin/env python3
"""Paired E5-large/E5-base full-text representation pilot on SAME theses.

Two models are run SEQUENTIALLY on one available 10-GiB MIG. Keeps the
text input/chunking identical; compares 1024D vs 768D representations using
dimension-free pairwise ranks and neighbor overlap, NOT direct cross-model
cosine and NOT classification quality. Private vectors stay on CEDIA.
"""
from __future__ import annotations
import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd

from pilot_fulltext_embeddings import choose_indices,extract_rows,windows
from audit_embedding_comparison import check_row_alignment
from reviewer_shared import private_output, summary, write_public


MODEL_VARIANTS=(
    ("E5-large","intfloat/multilingual-e5-large"),
    ("E5-base","intfloat/multilingual-e5-base"),
)


def encode_doc(text,tokenizer,model,torch,max_chunks=500,window=384,overlap=48):
    tokens=tokenizer.encode(text,add_special_tokens=False,truncation=False)
    if len(tokens)==0:
        raise ValueError("Empty input text")
    prefix=tokenizer.encode("passage: ",add_special_tokens=False)
    if len(prefix)+window+tokenizer.num_special_tokens_to_add(pair=False)>512:
        raise ValueError("E5 model context window exceeded")
    expected=1 if len(tokens)<=window else 1+math.ceil(
        (len(tokens)-window)/(window-overlap)
    )
    if expected>max_chunks:
        raise ValueError("Selected thesis exceeds cap; STOP, do not silently omit")
    weighted=None
    covered=0
    chunks=0
    for sequence,weight in windows(tokens,window,overlap,prefix,tokenizer):
        batch=tokenizer.pad({"input_ids":[sequence]},padding=True,
                            return_attention_mask=True,return_tensors="pt")
        batch={k:v.to(model.device) for k,v in batch.items()}
        with torch.inference_mode():
            hidden=model(**batch).last_hidden_state.float()
            mask=batch["attention_mask"].unsqueeze(-1).float()
            pooled=(hidden*mask).sum(dim=1)/mask.sum(dim=1).clamp(min=1)
            v=torch.nn.functional.normalize(pooled,dim=1,p=2)[0].cpu().numpy().astype(np.float64)
        if weighted is None:
            weighted=np.zeros_like(v,dtype=np.float64)
        weighted+=v*weight
        covered+=weight
        chunks+=1
    if covered!=len(tokens) or chunks!=expected:
        raise AssertionError("Document not covered by all windows")
    z=weighted/covered
    norm=np.linalg.norm(z)
    if norm<1e-8 or not np.isfinite(norm):
        raise ValueError("Degenerate aggregate vector")
    return (z/norm).astype(np.float32),len(tokens),chunks


def geometry_compare(a,b,k=10):
    """Cross-model comparisons are dimension-free, within-model geometry only."""
    if len(a)!=len(b) or len(a)<=k or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError("Matched finite document matrices and n > k required")
    A=a @ a.T
    B=b @ b.T
    ia=np.triu_indices(len(a),k=1)
    ranks=pd.Series(A[ia]).rank().corr(pd.Series(B[ia]).rank(),method="pearson")
    np.fill_diagonal(A,-np.inf)
    np.fill_diagonal(B,-np.inf)
    ka=np.argpartition(-A,kth=k-1,axis=1)[:,:k]
    kb=np.argpartition(-B,kth=k-1,axis=1)[:,:k]
    recalls=[len(set(x)&set(y))/k for x,y in zip(ka,kb)]
    return {
        "n_documents":len(a),"n_unique_pairs":int(len(ia[0])),
        "pairwise_similarity_spearman":round(float(ranks),6),
        "mean_topk_neighbor_overlap":round(float(np.mean(recalls)),6),
        "topk":k,
        "warning":"No direct cosine across embeddings of different dimensions; geometry agreement is not ODS accuracy."
    }


def pilot(args):
    import torch
    from transformers import AutoModel,AutoTokenizer
    if not torch.cuda.is_available():
        raise RuntimeError("Requires one CUDA MIG for paired inference")
    root=args.project_root.expanduser().resolve()
    workspace=Path(__file__).resolve().parent.parent
    n,align=check_row_alignment(root)
    lengths=pd.read_parquet(
        root/"data/processed/04_clean_corpus.parquet",
        columns=["fulltext_chars"])["fulltext_chars"]
    ix=choose_indices(lengths,args.documents)
    texts=extract_rows(root/"data/processed/04_clean_corpus.parquet",ix)
    outputs={}
    stats={}
    local_only=not args.allow_download
    dir=private_output(args.private_dir,workspace)
    for variant,model_name in MODEL_VARIANTS:
        tokenizer=AutoTokenizer.from_pretrained(model_name,use_fast=True,
                                                local_files_only=local_only)
        tokenizer.model_max_length=10**9
        model=AutoModel.from_pretrained(
            model_name,dtype=torch.float16,use_safetensors=True,
            local_files_only=local_only
        ).to("cuda")
        model.eval()
        torch.cuda.reset_peak_memory_stats()
        start=time.perf_counter()
        embeddings=[]
        counts=[]
        token_counts=[]
        for row in ix:
            vec,tokens,chunks=encode_doc(
                texts[row],tokenizer,model,torch,
                args.max_chunks,args.chunk_tokens,args.overlap
            )
            embeddings.append(vec)
            counts.append(chunks)
            token_counts.append(tokens)
        elapsed=time.perf_counter()-start
        arrays=np.stack(embeddings)
        np.savez_compressed(dir/(variant+"_vectors_PRIVATE.npz"),
                            row_indices=np.asarray(ix,dtype=np.int64),
                            embeddings=arrays)
        outputs[variant]=arrays
        stats[variant]={
            "model":model_name,"embedding_dimension":int(arrays.shape[1]),
            "documents_processed":len(ix),
            "chunks_encoded":int(sum(counts)),
            "tokens_encoded":int(sum(token_counts)),
            "elapsed_processing_seconds_excludes_model_load":round(elapsed,3),
            "chunks_per_second":round(sum(counts)/elapsed,3),
            "peak_torch_allocated_gib":round(float(torch.cuda.max_memory_allocated())/1024**3,3),
            "vector_norms":summary(np.linalg.norm(arrays,axis=1))
        }
        del model,tokenizer
        torch.cuda.empty_cache()
    return {
        "schema_version":1,
        "status":"paired_fulltext_two_encoder_geometry_pilot",
        "source_rows":n,"matched_documents":len(ix),
        "provenance":align,"fulltext_window":args.chunk_tokens,
        "overlap":args.overlap,"max_chunks_protection":args.max_chunks,
        "models":stats,
        "pairwise_fulltext_large_vs_base":geometry_compare(
            outputs["E5-large"],outputs["E5-base"],k=min(10,len(ix)-1)),
        "limitations":[
            "This is an unlabelled small length-quantile pilot, not evidence of SDG/PDOT classifier accuracy.",
            "Both models use the same full-text passage-token window and pooling.",
            "Model selection must use independent expert reference labels, not only geometry or semantic similarity.",
            "No thesis text, handle, row index, individual embedding or source path is exported.",
            "Model downloading may require an authorized internet connection and disk quota.",
        ]
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root",type=Path,required=True)
    p.add_argument("--documents",type=int,default=36)
    p.add_argument("--chunk-tokens",type=int,default=384)
    p.add_argument("--overlap",type=int,default=48)
    p.add_argument("--max-chunks",type=int,default=500)
    p.add_argument("--allow-download",action="store_true")
    p.add_argument("--private-dir",type=Path,
                   default=Path("data/revision_private/reviewer_alt_encoder"))
    p.add_argument("--output",type=Path,
                   default=Path("docs/audits/reviewer_alternate_encoder_pilot.json"))
    a=p.parse_args()
    if not 12<=a.documents<=64:
        p.error("This pilot permits 12-64 unique theses")
    if a.chunk_tokens<1 or a.chunk_tokens>508 or not 0<=a.overlap<a.chunk_tokens:
        p.error("Invalid E5 chunking")
    report=pilot(a)
    write_public(report,a.output,Path(__file__).resolve().parent.parent)
    print("Two encoder pilot completed:",a.output)
    print("All private embeddings under ignored data/. Human validation still required.")


if __name__=="__main__":
    main()
