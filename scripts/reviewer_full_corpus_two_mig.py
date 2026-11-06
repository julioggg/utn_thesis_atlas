#!/usr/bin/env python3
"""RESUMABLE full-corpus multilingual E5-large 2-MIG embedding candidate.

EXPLICIT OPT-IN ONLY. Do not run from the short computational suite.

Each MIG independently processes its disjoint thesis row indices (even/odd),
checkpoints every 16 documents as PRIVATE .npz, validates existing checkpoint
integrity before resuming and never modifies the original atlas. Final private
N x 1024 .npy is row-aligned to 04/05/06/07 only after auditing 7,830 rows,
286,050,084 content tokens and 854,145 E5 windows.

All raw texts, row IDs and embeddings remain under git-ignored revision/data/.
Only the aggregate report is a candidate for public GitHub after inspection.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from audit_embedding_comparison import check_row_alignment
from reviewer_shared import private_output, sha256_file, write_public
from pilot_fulltext_embeddings import encode_document
from run_two_mig_pilot import discover_mig_slots

EXPECTED_ROWS=7830
EXPECTED_CHUNKS=854145
EXPECTED_TOKENS=286050084
MODEL="intfloat/multilingual-e5-large"


def count_worker_documents(slot,n,workers=2):
    if workers!=2 or slot not in (0,1):
        raise ValueError("This workflow requires exactly two MIG worker slots")
    return len(range(slot,n,workers))


def checkpoint_indices(slot,batch_id,batch_size,n):
    total=count_worker_documents(slot,n)
    lo=batch_id*batch_size
    hi=min((batch_id+1)*batch_size,total)
    return np.arange(lo,hi,dtype=np.int64)*2+slot


def load_verified_checkpoint(path,expected_indices,fingerprint,embedding_dim=1024):
    with np.load(path,allow_pickle=False) as z:
        rows=z["row_indices"]
        vectors=z["vectors"]
        tokens=z["content_token_counts"]
        chunks=z["window_counts"]
        identity=z["manifest_sha256"].item()
    if identity!=fingerprint or not np.array_equal(rows,expected_indices):
        raise ValueError("Checkpoint belongs to different parameters, corpus or row indices")
    if vectors.shape!=(len(expected_indices),embedding_dim):
        raise ValueError("Checkpoint vector shape mismatch")
    if tokens.shape!=(len(expected_indices),) or chunks.shape!=(len(expected_indices),):
        raise ValueError("Checkpoint count shapes mismatch")
    if not np.isfinite(vectors).all() or np.any(tokens<=0) or np.any(chunks<=0):
        raise ValueError("Non-finite vectors or impossible checkpoint counts")
    if np.max(np.abs(np.linalg.norm(vectors,axis=1)-1))>1e-3:
        raise ValueError("Checkpoint vectors are not L2-normalized")
    return {
        "rows":len(expected_indices),
        "tokens":int(np.sum(tokens)),
        "chunks":int(np.sum(chunks)),
    }


def atomic_checkpoint(path,rows,vectors,tokens,chunks,fingerprint):
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=".pending_",suffix=".npz",dir=path.parent,delete=False
    ) as fd:
        tmp=Path(fd.name)
    try:
        np.savez_compressed(
            tmp,row_indices=np.asarray(rows,dtype=np.int64),
            vectors=np.stack(vectors).astype(np.float32),
            content_token_counts=np.asarray(tokens,dtype=np.int64),
            window_counts=np.asarray(chunks,dtype=np.int64),
            manifest_sha256=np.asarray(fingerprint)
        )
        expected=np.asarray(rows,dtype=np.int64)
        load_verified_checkpoint(tmp,expected,fingerprint)
        os.replace(tmp,path)
    finally:
        tmp.unlink(missing_ok=True)


def worker(args):
    import pyarrow.parquet as pq
    import torch
    from transformers import AutoTokenizer,AutoModel

    if not torch.cuda.is_available() or torch.cuda.device_count()!=1:
        raise RuntimeError("Each R535 MIG worker must see exactly one CUDA device")
    workspace=Path(__file__).resolve().parent.parent
    manifest=json.loads(args.manifest.read_text(encoding="utf-8"))
    fingerprint=hashlib.sha256(
        json.dumps(manifest,sort_keys=True).encode("utf-8")
    ).hexdigest()
    source=Path(manifest["original_root"])/"data/processed/04_clean_corpus.parquet"
    parquet=pq.ParquetFile(source)
    n=parquet.metadata.num_rows
    if n!=EXPECTED_ROWS or manifest["population_rows"]!=n:
        raise ValueError("Corpus changed after snapshot; do not resume")
    slot=args.worker_slot
    if slot not in (0,1):
        raise ValueError("Invalid worker slot")
    model_id=manifest["model"]
    tokenizer=AutoTokenizer.from_pretrained(model_id,use_fast=True,
                                            local_files_only=True)
    tokenizer.model_max_length=10**9
    model=AutoModel.from_pretrained(model_id,dtype=torch.float16,
                                   local_files_only=True,use_safetensors=True).to("cuda")
    model.eval()
    torch.cuda.reset_peak_memory_stats()
    out=Path(args.private_run_dir)/f"mig_slot{slot}"
    out.mkdir(parents=True,exist_ok=True)
    block_size=manifest["documents_per_checkpoint"]
    ntotal=count_worker_documents(slot,n)
    block_count=math.ceil(ntotal/block_size)
    expected_paths=[out/f"batch_{i:04d}.npz" for i in range(block_count)]
    existing={p for p in out.glob("batch_*.npz")}
    if existing-set(expected_paths):
        raise ValueError("Unexpected checkpoint filename in directory: stop and inspect")
    counters={"docs_processed_now":0,"docs_resumed":0,"chunk_new":0,"token_new":0}
    start=time.perf_counter()
    record_index=0
    active_id=None
    current_rows=[]
    current_vec=[]
    current_tokens=[]
    current_chunks=[]
    def flush(batch_id):
        if not current_rows:
            return
        expected=checkpoint_indices(slot,batch_id,block_size,n)
        if not np.array_equal(np.asarray(current_rows,dtype=np.int64),expected):
            raise ValueError("Non-contiguous or missing rows before writing checkpoint")
        target=out/f"batch_{batch_id:04d}.npz"
        if target.exists():
            raise FileExistsError("Checkpoint appeared while worker was processing")
        atomic_checkpoint(target,current_rows,current_vec,current_tokens,
                          current_chunks,fingerprint)
        current_rows.clear()
        current_vec.clear()
        current_tokens.clear()
        current_chunks.clear()

    # Validate all already-complete checkpoints BEFORE new inference.
    prevalidated={}
    for batch_id,path in enumerate(expected_paths):
        if path.is_file():
            prevalidated[batch_id]=load_verified_checkpoint(
                path,checkpoint_indices(slot,batch_id,block_size,n),
                fingerprint
            )
            counters["docs_resumed"]+=prevalidated[batch_id]["rows"]

    for batch in parquet.iter_batches(batch_size=32,columns=["full_text"]):
        for item in batch.column(0):
            idx=record_index
            record_index+=1
            if idx%2!=slot:
                continue
            shard_pos=idx//2
            block_id=shard_pos//block_size
            if block_id in prevalidated:
                continue
            if active_id is None:
                active_id=block_id
            if block_id!=active_id:
                flush(active_id)
                active_id=block_id
            text=item.as_py() or ""
            result=encode_document(
                text,tokenizer,model,torch,
                manifest["chunk_tokens"],manifest["overlap_tokens"],
                manifest["batch_size"],
                tokenizer.encode("passage: ",add_special_tokens=False),
                manifest["max_chunks_per_document"]
            )
            if result is None or result.get("skipped"):
                raise ValueError("Fulltext corpus contains unencodable/over-cap thesis; STOP, never silently skip")
            current_rows.append(idx)
            current_vec.append(result["vector"])
            current_tokens.append(int(result["tokens"]))
            current_chunks.append(int(result["chunks"]))
            counters["docs_processed_now"]+=1
            counters["token_new"]+=result["tokens"]
            counters["chunk_new"]+=result["chunks"]
    if active_id is not None:
        flush(active_id)
    if record_index!=n:
        raise ValueError("Parquet scan did not cover entire original corpus")
    if counters["docs_processed_now"]+counters["docs_resumed"]!=ntotal:
        raise ValueError("Worker ended before all shard documents were checkpointed")
    all_summaries=[
        load_verified_checkpoint(
            p,checkpoint_indices(slot,i,block_size,n),fingerprint
        ) for i,p in enumerate(expected_paths)
    ]
    aggregate={
        "schema_version":1,"status":"complete_private_fulltext_shard",
        "slot":slot,"n_documents":ntotal,
        "total_content_tokens":sum(x["tokens"] for x in all_summaries),
        "total_e5_windows":sum(x["chunks"] for x in all_summaries),
        "private_checkpoint_blocks":len(expected_paths),
        "newly_processed_documents":counters["docs_processed_now"],
        "resumed_existing_documents":counters["docs_resumed"],
        "elapsed_seconds_including_model_load_excluded":round(
            time.perf_counter()-start,3
        ),
        "peak_torch_allocated_gib":round(
            float(torch.cuda.max_memory_allocated())/1024**3,3),
        "model_cached_revision":getattr(model.config,"_commit_hash",None),
        "software":{"torch":torch.__version__,
                    "transformers":__import__("transformers").__version__}
    }
    (out/"worker_aggregate_private.json").write_text(
        json.dumps(aggregate,indent=2)+"\n",encoding="utf-8"
    )
    print("MIG slot",slot,"done:",ntotal,"documents;",aggregate["total_e5_windows"],"windows")
    return aggregate


def reconstruct(private_run_dir,n,block_size,fingerprint):
    """Build a single row-ordered private N x 1024 .npy after both shards pass."""
    target=private_run_dir/"fulltext_e5_large_7830_PRIVATE.npy"
    if target.is_file():
        raise FileExistsError("Private result matrix already exists. Refusing to overwrite.")
    tmp=private_run_dir/"fulltext_e5_large_7830.pending.npy"
    if tmp.exists():
        raise FileExistsError("Unfinished assembly exists; inspect before restart")
    matrix=np.lib.format.open_memmap(tmp,mode="w+",dtype=np.float32,shape=(n,1024))
    seen=np.zeros(n,dtype=bool)
    tokens=0
    chunks=0
    blocks=0
    try:
        for slot in (0,1):
            number=count_worker_documents(slot,n)
            for i in range(math.ceil(number/block_size)):
                path=private_run_dir/f"mig_slot{slot}"/f"batch_{i:04d}.npz"
                expected=checkpoint_indices(slot,i,block_size,n)
                verified=load_verified_checkpoint(path,expected,fingerprint)
                with np.load(path,allow_pickle=False) as data:
                    rows=data["row_indices"]
                    vec=data["vectors"]
                if np.any(seen[rows]):
                    raise ValueError("Duplicate row in multi-GPU checkpoint assembly")
                matrix[rows]=vec
                seen[rows]=True
                tokens+=verified["tokens"]
                chunks+=verified["chunks"]
                blocks+=1
        if not np.all(seen) or tokens!=EXPECTED_TOKENS or chunks!=EXPECTED_CHUNKS:
            raise RuntimeError(
                "Exact census mismatch or missing row: STOP. "
                f"rows={seen.sum()} tokens={tokens} chunks={chunks}"
            )
        matrix.flush()
        del matrix
        os.replace(tmp,target)
    finally:
        if 'matrix' in locals():
            del matrix
        tmp.unlink(missing_ok=True)
    return {"documents":int(seen.sum()),"content_tokens":tokens,"windows":chunks,
            "checkpoint_blocks":blocks,"private_matrix_rows":n,
            "private_vector_dimension":1024,"private_matrix_dtype":"float32"}


def orchestrate(args):
    workspace=Path(__file__).resolve().parent.parent
    root=args.project_root.expanduser().resolve()
    n,alignment=check_row_alignment(root)
    if n!=EXPECTED_ROWS:
        raise ValueError("Unexpected original aligned corpus size")
    original=root/"data/processed/04_clean_corpus.parquet"
    private=private_output(args.private_run_dir,workspace)
    final_path=private/"fulltext_e5_large_7830_PRIVATE.npy"
    if final_path.exists():
        raise FileExistsError("Final private 7830-row matrix already exists; do not rerun with same ID")
    manifest={
        "schema_version":1,"original_root":str(root),
        "original_04_parquet_sha256":sha256_file(original),
        "code_git_commit":subprocess.run(
            ["git","rev-parse","HEAD"],cwd=workspace,capture_output=True,
            text=True,check=True).stdout.strip(),
        "population_rows":n,
        "model":MODEL,
        "chunk_tokens":args.chunk_tokens,
        "overlap_tokens":args.overlap,
        "batch_size":args.batch_size,
        "max_chunks_per_document":args.max_chunks,
        "documents_per_checkpoint":args.checkpoint_docs,
        "precision":"fp16",
        "pooling":"length-weighted chunk mean of normalized embeddings, L2 document norm",
    }
    mf=private/"run_parameters_PRIVATE.json"
    if mf.exists():
        earlier=json.loads(mf.read_text(encoding="utf-8"))
        if earlier!=manifest:
            raise ValueError("Run parameters/corpus fingerprint changed. Never mix checkpoints.")
    else:
        mf.write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    fingerprint=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()
    slots=discover_mig_slots()
    logs=[]
    children=[]
    t0=time.perf_counter()
    try:
        for i,uuid in enumerate(slots):
            log=(private/f"mig_slot{i}.log").open("w",encoding="utf-8")
            logs.append(log)
            environment=dict(os.environ)
            environment["CUDA_VISIBLE_DEVICES"]=uuid
            cmd=[sys.executable,str(Path(__file__).resolve()),
                 "--worker-slot",str(i),
                 "--manifest",str(mf),
                 "--private-run-dir",str(private)]
            p=subprocess.Popen(cmd,cwd=workspace,env=environment,
                               stdout=log,stderr=subprocess.STDOUT)
            children.append((i,p))
        failures=[]
        for i,p in children:
            status=p.wait()
            if status!=0:
                failures.append({"slot":i,"exit_code":status})
        for log in logs:
            log.close()
        if failures:
            raise RuntimeError(
                "GPU worker(s) failed, checkpoints are preserved for resume; "
                "read ignored private MIG logs: "+str(failures)
            )
        result=reconstruct(private,n,args.checkpoint_docs,fingerprint)
        worker_summary=[]
        for i in (0,1):
            path=private/f"mig_slot{i}"/"worker_aggregate_private.json"
            summary=json.loads(path.read_text(encoding="utf-8"))
            worker_summary.append({
                "slot":i,"documents":summary["n_documents"],
                "windows":summary["total_e5_windows"],
                "tokens":summary["total_content_tokens"],
                "peak_torch_allocated_gib":summary["peak_torch_allocated_gib"],
                "model_cached_revision":summary["model_cached_revision"],
                "software":summary["software"],
            })
        revisions=[item["model_cached_revision"] for item in worker_summary]
        if revisions[0]!=revisions[1]:
            raise RuntimeError("MIG workers resolved DIFFERENT model revisions; do not publish results")
        return {
            "schema_version":1,
            "status":"complete_full_corpus_fulltext_E5_aggregated_candidate",
            "population":n,
            "source_corpus_sha256":manifest["original_04_parquet_sha256"],
            "analysis_code_git_commit":manifest["code_git_commit"],
            "model_revision_from_cache":revisions[0],
            "alignment":alignment,
            "model":MODEL,
            "model_input_prefix":"passage: ",
            "chunk_tokens":args.chunk_tokens,
            "overlap_tokens":args.overlap,
            "batch_size":args.batch_size,
            "max_chunks_per_document":args.max_chunks,
            "precision":"fp16",
            "full_corpus_counts":result,
            "per_mig":worker_summary,
            "wall_seconds_including_model_load_and_assembly":round(time.perf_counter()-t0,3),
            "validity_warning":"Recomputed fulltext vectors are a candidate representation, NOT validated SDG/PDOT accuracy.",
            "privacy_warning":"Matrix, checkpoints, handles and source texts remain under ignored private CEDIA data/.",
            "limitations":[
                "Does not apply an unvalidated section-trimming heuristic.",
                "Does not produce or calibrate SDG/PDOT assignments.",
                "Model consistency is checked by parameters and source sha256; check weight revision and environment for full reproducibility.",
                "Original 05 embeddings and original 07 alignment parquet remain unchanged.",
                "Human-coded F1 and descriptor validation are still required before paper claims.",
            ]
        }
    finally:
        for _,p in children:
            if p.poll() is None:
                p.terminate()
        for handle in logs:
            if not handle.closed:
                handle.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root",type=Path)
    parser.add_argument("--run-id",default="fulltext_e5_large_v1")
    parser.add_argument("--private-run-dir",type=Path)
    parser.add_argument("--output",type=Path,
                        default=Path("docs/audits/fulltext_e5_large_full_corpus_v1.json"))
    parser.add_argument("--chunk-tokens",type=int,default=384)
    parser.add_argument("--overlap",type=int,default=48)
    parser.add_argument("--batch-size",type=int,default=1)
    parser.add_argument("--max-chunks",type=int,default=1500)
    parser.add_argument("--checkpoint-docs",type=int,default=16)
    parser.add_argument("--worker-slot",type=int,choices=(0,1))
    parser.add_argument("--manifest",type=Path)
    args=parser.parse_args()
    workspace=Path(__file__).resolve().parent.parent
    if args.worker_slot is not None:
        if not args.manifest or not args.private_run_dir:
            parser.error("Worker requires manifest and private run directory")
        worker(args)
        return
    if not args.project_root:
        parser.error("The orchestrator requires --project-root")
    if not args.private_run_dir:
        args.private_run_dir=workspace/"data/revision_private"/args.run_id
    if (args.chunk_tokens,args.overlap,args.batch_size)!=(384,48,1):
        parser.error("Census verification requires EXACT pilot E5 parameters 384/48/batch1")
    if args.max_chunks<1240 or args.max_chunks>10000 or args.checkpoint_docs<1:
        parser.error("max-chunks must cover census maximum 1240; checkpoint-docs must be positive")
    if not args.private_run_dir.expanduser().resolve().is_relative_to((workspace/"data").resolve()):
        parser.error("Private output must reside in ignored revision/data/")
    if not all(c.isalnum() or c in "_-" for c in args.run_id):
        parser.error("Invalid run ID")
    result=orchestrate(args)
    path=write_public(result,args.output,workspace)
    print("FULL CORPUS candidate complete; verified 7830 rows, 854145 windows.")
    print("Aggregate-only report:",path)
    print("Review results before any public GitHub commit; no human validity is claimed.")


if __name__=="__main__":
    main()
