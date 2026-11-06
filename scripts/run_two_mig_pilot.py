#!/usr/bin/env python3
"""Run a SMALL E5 full-text pilot concurrently on two distinct NVIDIA MIG instances.

This is NOT a full-corpus job, and no public output contains individual
thesis identifiers, vectors, texts, GPU UUIDs, hostnames or private file paths.
Two child processes each use an independent CUDA_VISIBLE_DEVICES=MIG-UUID.
Requires the working PyTorch + transformers GPU environment on CEDIA.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def discover_mig_slots():
    """Return ordered private UUIDs; never add their values to published JSON."""
    from probe_mig_instances import detect_mig_uuids
    completed = subprocess.run(["nvidia-smi", "-L"], capture_output=True,
                               text=True, timeout=30, check=True)
    slots = detect_mig_uuids(completed.stdout)
    if len(slots) != 2:
        raise RuntimeError(
            "Expected exactly two visible MIG compute instances for this two-worker pilot; "
            f"nvidia-smi listed {len(slots)}."
        )
    return slots


def run(args):
    workspace = Path(__file__).resolve().parent.parent
    root = args.project_root.expanduser().resolve()
    if not (root / "data/processed/04_clean_corpus.parquet").is_file():
        raise FileNotFoundError("Original 04_clean_corpus.parquet was not found on HPC")
    slots = discover_mig_slots()
    private = workspace / "data/revision_private/dual_mig_pilot"
    private.mkdir(parents=True, exist_ok=True)
    audit = workspace / "docs/audits"
    audit.mkdir(parents=True, exist_ok=True)
    processes = []
    logs = []
    t0 = time.perf_counter()
    try:
        for slot, uuid in enumerate(slots):
            logfile = private / f"{args.run_id}_slot{slot}.log"
            handle = logfile.open("w", encoding="utf-8")
            logs.append(handle)
            output = audit / f"{args.run_id}_slot{slot}.json"
            private_out = private / f"{args.run_id}_slot{slot}"
            cmd = [
                sys.executable, str(workspace / "scripts/pilot_fulltext_embeddings.py"),
                "--workspace", str(workspace),
                "--project-root", str(root),
                "--documents", str(args.documents),
                "--shard-count", "2", "--shard-index", str(slot),
                "--batch-size", str(args.batch_size),
                "--chunk-tokens", str(args.chunk_tokens),
                "--overlap", str(args.overlap),
                "--max-chunks", str(args.max_chunks),
                "--precision", "fp16", "--device", "cuda",
                "--private-output-dir", str(private_out),
                "--output", str(output),
            ]
            if args.local_files_only:
                cmd.append("--local-files-only")
            child_env = dict(os.environ)
            child_env["CUDA_VISIBLE_DEVICES"] = uuid
            child = subprocess.Popen(cmd, cwd=workspace, env=child_env,
                                     stdout=handle, stderr=subprocess.STDOUT)
            processes.append((slot, child, output))
        failure = False
        for slot, process, _ in processes:
            try:
                status = process.wait(timeout=args.timeout_seconds)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                status = -1
            if status != 0:
                failure = True
                print(f"GPU slot {slot}: FAILED (code {status}). Private log at "
                      f"data/revision_private/dual_mig_pilot/{args.run_id}_slot{slot}.log")
        for handle in logs:
            handle.close()
        if failure:
            raise RuntimeError("Pilot failed on at least one MIG instance. Do not publish incomplete reports.")
        children = []
        for slot, _, output in processes:
            if not output.is_file():
                raise FileNotFoundError(f"Missing aggregate output for MIG slot {slot}")
            report = json.loads(output.read_text(encoding="utf-8"))
            if report.get("shard_index") != slot or report.get("shard_count") != 2:
                raise RuntimeError(f"Unexpected shard metadata for slot {slot}")
            children.append(report)
        if sum(report["documents_requested"] for report in children) != args.documents:
            raise RuntimeError("Pilot shard selection counts do not reconcile")
        wall = time.perf_counter() - t0
        total_chunks = sum(report["processed_chunks"] for report in children)
        total_tokens = sum(report["processed_tokens"] for report in children)
        result = {
            "schema_version": 1,
            "status": "completed_two_mig_pilot",
            "run_id": args.run_id,
            "model": "intfloat/multilingual-e5-large",
            "selection_total_documents": args.documents,
            "documents_processed": sum(report["documents_processed"] for report in children),
            "documents_skipped": sum(report["documents_skipped"] for report in children),
            "total_processed_chunks": total_chunks,
            "total_processed_tokens": total_tokens,
            "wall_time_including_model_loading_seconds": round(wall, 3),
            "combined_chunks_per_wall_second_including_load": round(total_chunks / max(wall, 1e-9), 3),
            "per_mig": [
                {
                    "mig_slot": i,  # index only; no MIG UUIDs
                    "documents_requested": x["documents_requested"],
                    "documents_processed": x["documents_processed"],
                    "documents_skipped": x["documents_skipped"],
                    "processed_chunks": x["processed_chunks"],
                    "elapsed_seconds_excluding_model_load": x["elapsed_seconds_including_tokenization"],
                    "chunks_per_second_excluding_model_load": x["chunks_per_second"],
                    "peak_torch_allocated_gib": x["hardware"]["peak_allocated_gib"],
                    "visible_gpu_memory_gib": x["hardware"]["visible_gpu_memory_gib"],
                }
                for i, x in enumerate(children)
            ],
            "method": {
                "sharding": "one common length-quantile sample split into two disjoint subsets",
                "chunk_tokens": args.chunk_tokens, "overlap": args.overlap,
                "batch_size": args.batch_size, "max_chunks_per_document": args.max_chunks,
                "per_process_model": "separate E5 instance, one CUDA-visible MIG",
                "precision": "fp16",
            },
            "limitations": [
                "Performance on this small pilot is not proof of full-dataset throughput or classification quality.",
                "Wall-time includes two model loads; per-worker execution excludes model loading.",
                "PyTorch peak allocated excludes CUDA driver/context and other processes' GPU memory.",
                "No original thesis text, row-level vectors or MIG UUIDs are written to public reports.",
                "Human expert evaluation is required to validate SDG/PDOT classifications.",
            ],
        }
        path = audit / f"{args.run_id}_summary.json"
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return path, result
    finally:
        for _, proc, _ in processes:
            if proc.poll() is None:
                proc.terminate()
        for handle in logs:
            if not handle.closed:
                handle.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root", type=Path, required=True)
    p.add_argument("--run-id", default="two_mig_pilot_v1")
    p.add_argument("--documents", type=int, default=12)
    p.add_argument("--batch-size", type=int, default=1)
    p.add_argument("--chunk-tokens", type=int, default=384)
    p.add_argument("--overlap", type=int, default=48)
    p.add_argument("--max-chunks", type=int, default=400)
    p.add_argument("--timeout-seconds", type=int, default=1200)
    p.add_argument("--local-files-only", action="store_true")
    args = p.parse_args()
    if not args.run_id or len(args.run_id) > 48 or any(
        c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in args.run_id
    ):
        p.error("--run-id must contain only letters, digits, hyphens, or underscores (max 48)")
    if args.documents < 2 or args.documents > 40:
        p.error("--documents must be between 2 and 40 for a safe pilot")
    if args.batch_size < 1 or args.batch_size > 4:
        p.error("Batch size must be 1 to 4 for this limited VRAM pilot")
    if args.overlap < 0 or args.overlap >= args.chunk_tokens or args.chunk_tokens > 508:
        p.error("Invalid E5 token window")
    if args.max_chunks < 1 or args.timeout_seconds < 1:
        p.error("Invalid safety limit")
    path, report = run(args)
    print(f"Both MIG pilot shards completed; total chunks={report['total_processed_chunks']}")
    print(f"Wall time including model startup={report['wall_time_including_model_loading_seconds']} s")
    print(f"Combined measured throughput={report['combined_chunks_per_wall_second_including_load']} chunks/s")
    print(f"Aggregate report: {path}")
    print("Private logs and per-document vectors remain under ignored data/.")


if __name__ == "__main__":
    main()
