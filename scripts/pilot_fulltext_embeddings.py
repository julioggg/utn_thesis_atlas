#!/usr/bin/env python3
"""Small, checkpoint-free E5 full-text GPU pilot; NO automatic whole-corpus run.

Requires PyTorch with CUDA, transformers, pandas, pyarrow and numpy.
This script never modifies the old atlas and never publishes row-level output.
Only a few stratified documents are read. Vectors stay in ignored data/ on HPC.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path


def windows(token_ids, capacity, overlap, prefix_ids, tokenizer, model_limit=512):
    """Yield tokenized E5 windows plus unique-token weighting for document pooling."""
    if capacity <= 0 or overlap < 0 or overlap >= capacity:
        raise ValueError("Invalid window capacity/overlap")
    if not token_ids:
        return
    step = capacity - overlap
    covered = 0
    for start in range(0, len(token_ids), step):
        body = token_ids[start : start + capacity]
        if not body:
            break
        end = start + len(body)
        unique = max(0, end - covered)
        if not unique:
            break
        seq = tokenizer.build_inputs_with_special_tokens(prefix_ids + body)
        if len(seq) > model_limit:
            raise AssertionError(f"E5 model limit exceeded: {len(seq)} > {model_limit}")
        yield seq, unique
        covered = end
        if end >= len(token_ids):
            break
    if covered != len(token_ids):
        raise AssertionError("Chunking did not cover all thesis tokens")


def choose_indices(lengths, n):
    """Return diverse length-quantile rows; does not use student/author data."""
    import numpy as np
    a = np.asarray(lengths, dtype="float64")
    eligible = np.flatnonzero(np.isfinite(a) & (a > 0))
    if len(eligible) < n or n < 1:
        raise ValueError("Not enough eligible records for representative pilot")
    sorted_rows = eligible[np.argsort(a[eligible], kind="stable")]
    qs = np.linspace(0.10, 0.90, n)
    choices = []
    for q in qs:
        pos = int(round(q * (len(sorted_rows) - 1)))
        ix = int(sorted_rows[pos])
        if ix not in choices:
            choices.append(ix)
    for ix in sorted_rows:
        if len(choices) == n:
            break
        if int(ix) not in choices:
            choices.append(int(ix))
    return choices


def extract_rows(parquet_file, indices):
    """Stream only full_text; avoid loading the whole 600MB corpus in RAM."""
    import pyarrow.parquet as pq
    src = pq.ParquetFile(parquet_file)
    if "full_text" not in src.schema_arrow.names:
        raise KeyError("Original clean corpus must contain full_text")
    targets = set(indices)
    texts = {}
    row = 0
    for batch in src.iter_batches(batch_size=64, columns=["full_text"]):
        for item in batch.column(0):
            if row in targets:
                texts[row] = item.as_py() or ""
            row += 1
        if len(texts) == len(targets):
            break
    if len(texts) != len(targets):
        raise RuntimeError("Pilot thesis selection is incomplete")
    return texts


def encode_document(text, tokenizer, model, torch, chunk_tokens, overlap,
                    batch_size, prefix_ids, max_chunks):
    import numpy as np
    content_ids = tokenizer.encode(text, truncation=False, add_special_tokens=False)
    if not content_ids:
        return None
    special = tokenizer.num_special_tokens_to_add(pair=False)
    if chunk_tokens + special + len(prefix_ids) > 512:
        raise ValueError("512-token limit exceeded after prefix/special tokens")
    estimated = 1 if len(content_ids) <= chunk_tokens else 1 + math.ceil(
        (len(content_ids) - chunk_tokens) / (chunk_tokens - overlap))
    if max_chunks > 0 and estimated > max_chunks:
        return {"skipped": True, "tokens": len(content_ids), "chunks": estimated}
    vec_sum = None
    total_weight = 0
    chunks = 0
    seq_batch = []
    weight_batch = []

    def process_batch():
        nonlocal vec_sum, total_weight, chunks
        if not seq_batch:
            return
        packed = tokenizer.pad({"input_ids": seq_batch}, padding=True,
                               return_attention_mask=True, return_tensors="pt")
        packed = {key: value.to(model.device) for key, value in packed.items()}
        with torch.inference_mode():
            output = model(**packed)
            hidden = output.last_hidden_state.float()
            mask = packed["attention_mask"].unsqueeze(-1).float()
            pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
            pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
        vectors = pooled.cpu().numpy().astype(np.float32)
        for embedding, weight in zip(vectors, weight_batch):
            if vec_sum is None:
                vec_sum = np.zeros_like(embedding, dtype=np.float64)
            vec_sum += embedding.astype(np.float64) * weight
            total_weight += weight
            chunks += 1
        seq_batch.clear()
        weight_batch.clear()

    for seq, weight in windows(content_ids, chunk_tokens, overlap, prefix_ids, tokenizer):
        seq_batch.append(seq)
        weight_batch.append(weight)
        if len(seq_batch) >= batch_size:
            process_batch()
    process_batch()
    if total_weight != len(content_ids):
        raise AssertionError(f"Weighted coverage mismatch: {total_weight} != {len(content_ids)}")
    if vec_sum is None:
        raise RuntimeError("Failed to produce embeddings")
    doc = vec_sum / total_weight
    magnitude = np.linalg.norm(doc)
    if magnitude < 1e-12:
        raise RuntimeError("Document embedding has zero norm")
    doc = (doc / magnitude).astype(np.float32)
    return {"skipped": False, "vector": doc, "tokens": len(content_ids),
            "chunks": chunks, "norm": float(np.linalg.norm(doc))}


def pilot(args):
    import numpy as np
    import pandas as pd
    import torch
    import transformers
    from transformers import AutoModel, AutoTokenizer

    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA not available in this Python environment. Obtain a GPU allocation and CUDA PyTorch first.")
    if args.device == "cpu" and not args.allow_cpu:
        raise RuntimeError("CPU mode requires --allow-cpu; E5-large can be very slow without GPU.")
    device = torch.device(args.device)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
    root = args.project_root.expanduser().resolve()
    workspace = Path(args.workspace).expanduser().resolve()
    private_dir = Path(args.private_output_dir).expanduser().resolve()
    if not args.unsafe_private_path and not private_dir.is_relative_to(workspace / "data"):
        raise ValueError("Private vectors must be saved in the revision clone's ignored data/ directory")
    if args.output.expanduser().resolve().is_relative_to(workspace / "data"):
        raise ValueError("Aggregate report should not be mixed with private embeddings")
    corpus = root / "data/processed/04_clean_corpus.parquet"
    if not corpus.is_file():
        raise FileNotFoundError("Missing original clean corpus at expected location")

    # Only metadata lengths are loaded for selection.
    lengths = pd.read_parquet(corpus, columns=["fulltext_chars"])["fulltext_chars"]
    indices = choose_indices(lengths, args.documents)
    texts = extract_rows(corpus, indices)
    tokenizer = AutoTokenizer.from_pretrained(args.model, use_fast=True,
                                              local_files_only=args.local_files_only)
    tokenizer.model_max_length = max(tokenizer.model_max_length, 10**9)  # token counting only; per-window check stays 512
    prefix_ids = tokenizer.encode("passage: ", add_special_tokens=False)
    model_dtype = torch.float16 if device.type == "cuda" and args.precision == "fp16" else torch.float32
    model = AutoModel.from_pretrained(args.model, dtype=model_dtype,
                                     local_files_only=args.local_files_only).to(device)
    model.eval()
    visible_gpu_gib = (float(torch.cuda.get_device_properties(device).total_memory) / 1024**3
                       if device.type == "cuda" else None)
    model_max = 512
    if args.chunk_tokens + tokenizer.num_special_tokens_to_add(pair=False) + len(prefix_ids) > model_max:
        raise ValueError("Window exceeds the model's 512-token limit")
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats()
    t0 = time.perf_counter()
    docs = []
    vectors = []
    rows = []
    for index in indices:
        res = encode_document(texts[index], tokenizer, model, torch, args.chunk_tokens,
                              args.overlap, args.batch_size, prefix_ids, args.max_chunks)
        if res is None:
            docs.append({"processed": False, "reason": "empty_fulltext"})
        elif res["skipped"]:
            docs.append({"processed": False, "reason": "max_chunks_safety_limit",
                         "estimated_chunks": int(res["chunks"])})
        else:
            vector = res.pop("vector")
            if vector.shape != (1024,):
                raise AssertionError(f"Unexpected E5 dimension: {vector.shape}")
            vectors.append(vector)
            rows.append(index)
            docs.append({"processed": True, "tokens": int(res["tokens"]),
                         "chunks": int(res["chunks"]), "unit_norm": res["norm"]})
    elapsed = time.perf_counter() - t0
    peak_gib = (float(torch.cuda.max_memory_allocated()) / 1024**3
                if device.type == "cuda" else None)
    # PRIVATE HPC artifacts only. The destination was validated BEFORE model inference.
    private_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(private_dir / "gpu_pilot_vectors.npz",
                        row_indices=np.asarray(rows, dtype=np.int64),
                        vectors=np.stack(vectors) if vectors else np.empty((0, 1024), dtype=np.float32))
    processed = [r for r in docs if r["processed"]]
    total_chunks = sum(x["chunks"] for x in processed)
    report = {
        "schema_version": 1, "status": "pilot_only", "model": args.model,
        "hardware": {"device": args.device, "gpu_model":
                     torch.cuda.get_device_name(0) if device.type == "cuda" else None,
                     "peak_allocated_gib": None if peak_gib is None else round(peak_gib, 3),
                     "visible_gpu_memory_gib": None if visible_gpu_gib is None else round(visible_gpu_gib, 2)},
        "software": {"torch": torch.__version__, "transformers": transformers.__version__,
                     "precision": args.precision if device.type == "cuda" else "fp32"},
        "method": {
            "model_limit": model_max, "content_tokens_per_window": args.chunk_tokens,
            "overlap_tokens": args.overlap, "prefix": "passage: ",
            "special_tokens": tokenizer.num_special_tokens_to_add(pair=False),
            "pooling": "length-weighted mean of unit-normalized chunk embeddings, then unit normalize document",
            "selection": "fixed quantiles of extracted full-text character lengths",
        },
        "documents_requested": args.documents, "documents_processed": len(processed),
        "documents_skipped": args.documents - len(processed),
        "skipped_reasons": {key: sum(x.get("reason") == key for x in docs)
                            for key in ("empty_fulltext", "max_chunks_safety_limit")},
        "processed_tokens": sum(x["tokens"] for x in processed),
        "processed_chunks": int(total_chunks),
        "elapsed_seconds_including_tokenization": round(elapsed, 3),
        "chunks_per_second": round(total_chunks / max(elapsed, 1e-9), 3),
        "mean_chunks_per_processed_document": round(total_chunks / max(len(processed), 1), 3),
        "notes": [
            "No expert label validation, classifier evaluation, or legacy-vs-new comparison performed.",
            "This is a small pilot, not a representative full-corpus throughput benchmark.",
            "Private row indices and embedding vectors remain under ignored data/ on CEDIA.",
            "No source document, handle, advisor or full text is exported in this aggregate JSON.",
        ],
    }
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root", type=Path, required=True)
    p.add_argument("--workspace", type=Path, default=Path.cwd())
    p.add_argument("--model", default="intfloat/multilingual-e5-large")
    p.add_argument("--documents", type=int, default=3)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--chunk-tokens", type=int, default=384)
    p.add_argument("--overlap", type=int, default=48)
    p.add_argument("--batch-size", type=int, default=1)
    p.add_argument("--max-chunks", type=int, default=400)
    p.add_argument("--precision", choices=("fp16", "fp32"), default="fp16")
    p.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    p.add_argument("--allow-cpu", action="store_true")
    p.add_argument("--local-files-only", action="store_true")
    p.add_argument("--private-output-dir", type=Path,
                   default=Path("data/revision_private/gpu_pilot"))
    p.add_argument("--unsafe-private-path", action="store_true",
                   help="Opt out of protective local data/ directory restriction")
    p.add_argument("--output", type=Path, default=Path("docs/audits/gpu_pilot_report.json"))
    args = p.parse_args()
    if args.documents < 1 or args.batch_size < 1 or args.max_chunks < 1:
        p.error("Require positive --documents, --batch-size, --max-chunks")
    if args.overlap < 0 or args.overlap >= args.chunk_tokens:
        p.error("Require chunk_tokens > overlap >= 0")
    report = pilot(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(f"Pilot complete: {report['documents_processed']} documents, "
          f"{report['processed_chunks']} chunks, "
          f"{report['elapsed_seconds_including_tokenization']} s.")
    print(f"Aggregate-only pilot report: {args.output}")
    print("Private vectors stored ONLY in the ignored local data/ directory.")


if __name__ == "__main__":
    main()
