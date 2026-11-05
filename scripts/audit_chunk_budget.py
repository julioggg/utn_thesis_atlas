#!/usr/bin/env python3
"""Read-only CPU audit: estimate E5 chunks needed to encode full original theses.

Streams original full_text; samples documents and saves aggregate stats only.
No student names, handles, PDF text or embeddings are exported.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path


def chunk_count(n_tokens: int, chunk_tokens: int, overlap: int) -> int:
    if chunk_tokens <= 0 or overlap < 0 or overlap >= chunk_tokens:
        raise ValueError("Require chunk_tokens > overlap >= 0")
    if n_tokens <= 0:
        return 0
    if n_tokens <= chunk_tokens:
        return 1
    stride = chunk_tokens - overlap
    return 1 + (n_tokens - chunk_tokens + stride - 1) // stride


def summary(values) -> dict:
    import numpy as np
    x = np.asarray(values, dtype="float64")
    if not x.size:
        return {"n": 0}
    return {"n": int(len(x)), "min": float(x.min()),
            "p05": float(np.quantile(x, .05)), "median": float(np.median(x)),
            "p95": float(np.quantile(x, .95)), "max": float(x.max()),
            "mean": float(x.mean())}


def select_fulltexts(parquet: Path, sample_size: int, seed: int):
    """Stream Parquet batches; retain only randomly selected thesis texts in memory."""
    import numpy as np
    import pyarrow.parquet as pq
    dataset = pq.ParquetFile(parquet)
    n = dataset.metadata.num_rows
    if "full_text" not in dataset.schema_arrow.names:
        raise KeyError("Source corpus has no full_text; specify original 04_clean_corpus")
    if sample_size <= 0 or n <= 0:
        raise ValueError("Empty corpus or invalid sample size")
    indices = np.sort(np.random.default_rng(seed).choice(n, min(sample_size, n), replace=False))
    sampled = []
    pointer = 0
    offset = 0
    for batch in dataset.iter_batches(batch_size=64, columns=["full_text"]):
        length = batch.num_rows
        while pointer < len(indices) and int(indices[pointer]) < offset + length:
            local = int(indices[pointer]) - offset
            sampled.append(batch.column(0)[local].as_py() or "")
            pointer += 1
        offset += length
        if pointer == len(indices):
            break
    if len(sampled) != len(indices):
        raise RuntimeError("Incomplete sample retrieval")
    return n, sampled


def audit(project, corpus, tokenizer_name, sample_size, seed, max_tokens,
          chunk_tokens, overlap, local_only):
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(
        tokenizer_name, use_fast=True, local_files_only=local_only)
    prefix_tokens = len(tokenizer.encode("passage: ", add_special_tokens=False))
    special_tokens = tokenizer.num_special_tokens_to_add(pair=False)
    capacity = max_tokens - prefix_tokens - special_tokens
    if capacity < 1 or chunk_tokens > capacity:
        raise ValueError(f"Chunk too large: content={chunk_tokens}, available={capacity}")
    src = corpus if corpus.is_absolute() else project / corpus
    population, texts = select_fulltexts(src, sample_size, seed)
    # Suppress warnings from >512 tokens; no inference is performed.
    tokenizer.model_max_length = max(tokenizer.model_max_length, 10**9)
    full_tokens, chunks = [], []
    for txt in texts:
        count = len(tokenizer.encode(txt, truncation=False, add_special_tokens=False))
        full_tokens.append(count)
        chunks.append(chunk_count(count, chunk_tokens, overlap))
    ts = summary(full_tokens)
    cs = summary(chunks)
    return {
        "schema_version": 1, "tokenizer": tokenizer_name,
        "input_source": "04_clean_corpus.parquet:full_text",
        "population_rows": int(population), "sampled_rows": len(texts), "random_seed": seed,
        "fulltext_token_distribution": ts, "chunk_count_distribution": cs,
        "max_model_tokens": max_tokens, "prefix_tokens": prefix_tokens,
        "special_tokens": special_tokens, "content_capacity": capacity,
        "planned_content_tokens": chunk_tokens, "overlap_tokens": overlap,
        "approx_whole_corpus_chunk_count": int(round(cs["mean"] * population)),
        "empty_fulltexts_sampled": sum(not str(v).strip() for v in texts),
        "limitations": [
            "Extrapolated whole-corpus count, NOT an exact number; sampling error is unquantified.",
            "No embedding inference or throughput measurements have been run.",
            "Retokenized model inputs need an independent <=512 token assertion.",
            "Raw thesis text and per-thesis records remain private on HPC.",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root", required=True, type=Path)
    p.add_argument("--corpus", type=Path,
                   default=Path("data/processed/04_clean_corpus.parquet"))
    p.add_argument("--model", default="intfloat/multilingual-e5-large")
    p.add_argument("--sample-size", type=int, default=48)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--max-tokens", type=int, default=512)
    p.add_argument("--chunk-tokens", type=int, default=384)
    p.add_argument("--overlap", type=int, default=48)
    p.add_argument("--local-files-only", action="store_true")
    p.add_argument("--output", type=Path,
                   default=Path("reports/public/chunk_budget_audit.json"))
    a = p.parse_args()
    report = audit(a.project_root.expanduser().resolve(), a.corpus, a.model,
                   a.sample_size, a.seed, a.max_tokens,
                   a.chunk_tokens, a.overlap, a.local_files_only)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Aggregate full-thesis budget saved to {a.output}, sampled={report['sampled_rows']}")
    print("The original HPC corpus was not modified or exported.")


if __name__ == "__main__":
    main()
