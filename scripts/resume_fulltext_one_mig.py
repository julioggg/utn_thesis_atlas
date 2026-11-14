#!/usr/bin/env python3
"""Safely resume a frozen TWO-SHARD E5 atlas run using ONE visible MIG.

This deliberately DOES NOT change reviewer_full_corpus_two_mig.py or its
checkpointed SHA256 fingerprint: the old 134 checkpoints remain reusable.

--verify-only is CPU-only, read-only and checks every existing checkpoint.
Without that flag, shard 0 and then shard 1 are computed sequentially
on the SAME visible MIG; checkpoints are preserved on interruption.
After both shards complete, reconstructs the private 7830x1024 matrix
and publishes an aggregate-only local report (never does a git push).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path

from audit_embedding_comparison import check_row_alignment
from reviewer_shared import sha256_file, write_public
from reviewer_full_corpus_two_mig import (
    EXPECTED_CHUNKS, EXPECTED_ROWS, EXPECTED_TOKENS, MODEL,
    checkpoint_indices, count_worker_documents, load_verified_checkpoint,
    reconstruct,
)


def read_frozen_run(workspace: Path, project_root: Path, run_dir: Path):
    """Reject unrelated or modified source/models/encoder before any GPU work."""
    manifest_path = run_dir / "run_parameters_PRIVATE.json"
    if not manifest_path.is_file():
        raise FileNotFoundError("Frozen run_parameters_PRIVATE.json is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    required = {
        "schema_version": 1,
        "original_root": str(project_root),
        "population_rows": EXPECTED_ROWS,
        "model": MODEL,
        "chunk_tokens": 384,
        "overlap_tokens": 48,
        "batch_size": 1,
        "documents_per_checkpoint": 16,
    }
    for key, value in required.items():
        if manifest.get(key) != value:
            raise ValueError(
                f"Frozen manifest differs at {key}; do not mix checkpoints"
            )
    if manifest.get("max_chunks_per_document", 0) < 1240:
        raise ValueError("Maximum windows would exclude long theses")
    revision = manifest.get("model_hf_revision_sha", "")
    if not isinstance(revision, str) or len(revision) < 7:
        raise ValueError("Frozen model revision is missing")
    expected_hashes = {
        "full_corpus_script": sha256_file(
            workspace / "scripts/reviewer_full_corpus_two_mig.py"
        ),
        "e5_window_encoder_script": sha256_file(
            workspace / "scripts/pilot_fulltext_embeddings.py"
        ),
    }
    if manifest.get("code_fingerprints") != expected_hashes:
        raise ValueError(
            "Original script/encoder SHA256 differs from frozen run. "
            "Do not overwrite or recompute old checkpoints."
        )
    corpus = project_root / "data/processed/04_clean_corpus.parquet"
    if sha256_file(corpus) != manifest.get("original_04_parquet_sha256"):
        raise ValueError("Original 04 parquet SHA256 changed: stop")
    fingerprint = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return manifest, manifest_path, fingerprint


def verify_existing_shards(run_dir, manifest, fingerprint):
    """Verify every checkpoint's metadata, row positions, norms and run ID."""
    all_stats = []
    for slot in (0, 1):
        nslot = count_worker_documents(slot, EXPECTED_ROWS)
        block_size = manifest["documents_per_checkpoint"]
        nblocks = math.ceil(nslot / block_size)
        shard_dir = run_dir / f"mig_slot{slot}"
        names = {p.name for p in shard_dir.glob("batch_*.npz")}
        allowed = {f"batch_{i:04d}.npz" for i in range(nblocks)}
        if names - allowed:
            raise ValueError(f"Unexpected checkpoint filenames on MIG slot {slot}")
        docs = 0
        blocks = 0
        tokens = 0
        windows = 0
        for i in range(nblocks):
            path = shard_dir / f"batch_{i:04d}.npz"
            if not path.is_file():
                continue
            chk = load_verified_checkpoint(
                path, checkpoint_indices(slot, i, block_size, EXPECTED_ROWS),
                fingerprint
            )
            docs += chk["rows"]
            tokens += chk["tokens"]
            windows += chk["chunks"]
            blocks += 1
        all_stats.append({
            "slot": slot, "valid_checkpoint_blocks": blocks,
            "completed_documents": docs, "remaining_documents": nslot - docs,
            "completed_content_tokens": tokens,
            "completed_windows": windows,
            "total_expected_blocks": nblocks,
        })
    return all_stats


def resume(args):
    workspace = Path(__file__).resolve().parent.parent
    project_root = args.project_root.expanduser().resolve()
    run_dir = args.private_run_dir.expanduser().resolve()
    if not run_dir.is_relative_to((workspace / "data").resolve()):
        raise ValueError("Private run must be inside ignored revision/data")
    if not project_root.is_dir():
        raise FileNotFoundError("Original atlas directory unavailable")
    n, alignment = check_row_alignment(project_root)
    if n != EXPECTED_ROWS:
        raise ValueError("Original row alignment does not match 7830")
    manifest, manifest_path, fingerprint = read_frozen_run(
        workspace, project_root, run_dir
    )
    if (run_dir / "fulltext_e5_large_7830_PRIVATE.npy").is_file():
        raise FileExistsError("Completed private matrix already exists; no overwrite")
    previous = verify_existing_shards(run_dir, manifest, fingerprint)
    print("FROZEN RUN VERIFIED. Neither original script nor inputs modified.",
          flush=True)
    for stat in previous:
        print(
            f"MIG shard {stat['slot']}: {stat['completed_documents']} of "
            f"{count_worker_documents(stat['slot'], EXPECTED_ROWS)} theses "
            f"recoverable in {stat['valid_checkpoint_blocks']} blocks",
            flush=True,
        )
    if args.verify_only:
        print("Read-only verification completed; no GPU used.", flush=True)
        return

    import torch
    if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
        raise RuntimeError(
            "ONE CUDA device must be visible. "
            "Do not start if none or two CUDA instances are visible."
        )
    if args.output.expanduser().resolve().is_file():
        raise FileExistsError("Aggregate report exists; review it before proceeding")

    start = time.perf_counter()
    for slot in (0, 1):
        cmd = [
            sys.executable,
            str(workspace / "scripts/reviewer_full_corpus_two_mig.py"),
            "--worker-slot", str(slot),
            "--manifest", str(manifest_path),
            "--private-run-dir", str(run_dir),
        ]
        logfile = run_dir / f"single_mig_resume_slot{slot}.log"
        print(
            f"Starting shard {slot} on the one visible MIG; "
            "checkpoints are retained on interruption.",
            flush=True,
        )
        with logfile.open("a", encoding="utf-8") as stream:
            stream.write("\n===== ONE-MIG RESUME SHARD START =====\n")
            stream.flush()
            child = subprocess.run(
                cmd, cwd=workspace, stdout=stream,
                stderr=subprocess.STDOUT, check=False,
            )
        if child.returncode != 0:
            raise RuntimeError(
                f"MIG shard {slot} returned {child.returncode}. "
                f"Check ignored private log {logfile.name}; "
                "do not delete any checkpoint."
            )
        print(f"Shard {slot} finished. Checkpoints preserved.", flush=True)

    verified = verify_existing_shards(run_dir, manifest, fingerprint)
    if any(s["remaining_documents"] for s in verified):
        raise RuntimeError("Worker exited without complete coverage of both shards")

    assembly = reconstruct(
        run_dir, EXPECTED_ROWS,
        manifest["documents_per_checkpoint"], fingerprint
    )
    if (assembly["content_tokens"], assembly["windows"]) != (
        EXPECTED_TOKENS, EXPECTED_CHUNKS
    ):
        raise RuntimeError("Final assembly did not match fulltext token census")

    summaries = []
    for slot in (0, 1):
        file = run_dir / f"mig_slot{slot}" / "worker_aggregate_private.json"
        if not file.is_file():
            raise FileNotFoundError("Missing private worker aggregate")
        record = json.loads(file.read_text(encoding="utf-8"))
        if record["n_documents"] != count_worker_documents(slot, EXPECTED_ROWS):
            raise ValueError("Worker summary size differs from its shard")
        if record["model_cached_revision"] != manifest["model_hf_revision_sha"]:
            raise ValueError("Worker model revision differs from frozen model")
        summaries.append({
            "slot": slot,
            "documents": record["n_documents"],
            "windows": record["total_e5_windows"],
            "tokens": record["total_content_tokens"],
            "model_cached_revision": record["model_cached_revision"],
            "software": record["software"],
            "peak_torch_allocated_gib": record["peak_torch_allocated_gib"],
        })

    report = {
        "schema_version": 1,
        "status": "complete_full_corpus_fulltext_E5_aggregated_candidate",
        "run_layout": "two disjoint even/odd row shards, run sequentially on one MIG",
        "population": EXPECTED_ROWS,
        "source_corpus_sha256": manifest["original_04_parquet_sha256"],
        "analysis_code_fingerprints": manifest["code_fingerprints"],
        "model_revision_from_cache": manifest["model_hf_revision_sha"],
        "alignment": alignment,
        "model": MODEL,
        "model_input_prefix": "passage: ",
        "chunk_tokens": manifest["chunk_tokens"],
        "overlap_tokens": manifest["overlap_tokens"],
        "batch_size": manifest["batch_size"],
        "max_chunks_per_document": manifest["max_chunks_per_document"],
        "precision": "fp16",
        "full_corpus_counts": assembly,
        "per_mig": summaries,
        "initial_verified_checkpoint_documents": sum(
            x["completed_documents"] for x in previous
        ),
        "remaining_documents_at_resumption": EXPECTED_ROWS - sum(
            x["completed_documents"] for x in previous
        ),
        "resume_wall_seconds_including_model_load_and_assembly": round(
            time.perf_counter() - start, 3
        ),
        "validity_warning": (
            "Fulltext vectors are a candidate representation; this does "
            "not establish expert SDG/PDOT classification validity."
        ),
        "privacy_warning": (
            "Matrix, checkpoints and private logs remain under ignored "
            "CEDIA revision/data; no row-level data published."
        ),
        "limitations": [
            "Resumed existing frozen two-shard run without altering checkpoint provenance.",
            "No automatic section trimming or new SDG/PDOT classification was performed.",
            "Expert-labelled accuracy, recall and F1 remain pending.",
            "Run is sequential on one visible MIG; elapsed time excludes prior sessions.",
        ],
    }
    # write_public validates destination path before serialization.
    output_path = write_public(report, args.output, workspace)
    print("Full-corpus verified candidate complete:", output_path, flush=True)
    print("Only aggregate JSON is a public-release candidate.", flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root", type=Path, required=True)
    p.add_argument("--private-run-dir", type=Path,
                   default=Path("data/revision_private/fulltext_e5_large_v1"))
    p.add_argument("--output", type=Path,
                   default=Path("docs/audits/fulltext_e5_large_full_corpus_v1.json"))
    p.add_argument("--verify-only", action="store_true")
    args = p.parse_args()
    resume(args)


if __name__ == "__main__":
    main()
