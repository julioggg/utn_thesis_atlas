#!/usr/bin/env python3
"""Controlled E5 window-pooling sensitivity study on SAME 12 pilot documents.

One CUDA GPU only. Re-encodes a small bounded sample, comparing document
pooling strategies WITHOUT any automatic claim of superior SDG/PDOT accuracy.
Only aggregate diagnostics leave CEDIA; no row-level text, IDs, vectors,
scores or study identifiers are written to the public report.

Inference and the original private pilot both encode 384 E5 content tokens
with a 48-token overlap, token-exact E5 prefix and model special tokens.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

from pilot_fulltext_embeddings import choose_indices, extract_rows, windows
from audit_embedding_comparison import check_row_alignment, descriptive, load_pilot_vectors


def unit(vec):
    import numpy as np
    v = np.asarray(vec, dtype=np.float64)
    norm = np.linalg.norm(v)
    if not np.isfinite(norm) or norm < 1e-12:
        raise ValueError("Invalid pooled document norm")
    return (v / norm).astype(np.float32)


def pool_strategies(chunk_vectors, unique_weights):
    """All approaches use the same normalized chunk vectors and token coverage."""
    import numpy as np
    z = np.asarray(chunk_vectors, dtype=np.float32)
    w = np.asarray(unique_weights, dtype=np.float64)
    if z.ndim != 2 or z.shape[1] != 1024 or len(z) != len(w) or len(z) < 1:
        raise ValueError("Expected N x 1024 chunk vectors with N positive weights")
    if not np.isfinite(z).all() or not np.isfinite(w).all() or np.any(w <= 0):
        raise ValueError("Invalid chunk embedding or coverage weights")
    n = len(z)
    def combine(indices):
        idx = np.asarray(indices, dtype=np.int64)
        if len(idx) == 0:
            raise ValueError("Empty pooling region")
        return unit(np.average(z[idx], axis=0, weights=w[idx]))
    entire = combine(np.arange(n))
    trim = int(math.floor(n * .1))
    middle = combine(np.arange(trim, n - trim)) if n - 2 * trim >= 1 else entire.copy()
    front = combine(np.arange(max(1, math.ceil(n * .25))))
    thirds = [idx for idx in np.array_split(np.arange(n), 3) if len(idx)]
    regional = unit(np.mean([combine(idx) for idx in thirds], axis=0))
    return {
        "all_weighted": entire,
        "middle_80pct": middle,
        "first_25pct": front,
        "equal_three_regions": regional,
    }


def compute_chunks(txt, tokenizer, model, torch, batch_size, content_tokens, overlap, max_chunks):
    import numpy as np
    ids = tokenizer.encode(txt, truncation=False, add_special_tokens=False)
    if not ids:
        raise ValueError("Selected full text is empty")
    prefix = tokenizer.encode("passage: ", add_special_tokens=False)
    if content_tokens + len(prefix) + tokenizer.num_special_tokens_to_add(pair=False) > 512:
        raise ValueError("Content chunk leaves insufficient room for prefix/specials")
    expected = 1 if len(ids) <= content_tokens else 1 + math.ceil(
        (len(ids) - content_tokens) / (content_tokens - overlap))
    if expected > max_chunks:
        raise ValueError("Selected thesis exceeds safety limit. Do not silently omit it.")
    sequences = []
    weights = []
    vectors = []
    lengths = []
    def flush():
        if not sequences:
            return
        packed = tokenizer.pad({"input_ids": sequences}, padding=True,
                               return_attention_mask=True, return_tensors="pt")
        packed = {k: v.to(model.device) for k, v in packed.items()}
        with torch.inference_mode():
            hidden = model(**packed).last_hidden_state.float()
            mask = packed["attention_mask"].unsqueeze(-1).float()
            mean = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
            vecs = torch.nn.functional.normalize(mean, dim=1, p=2)
        vectors.extend(vecs.cpu().numpy().astype(np.float32))
        sequences.clear()
    for seq, weight in windows(ids, content_tokens, overlap, prefix, tokenizer):
        sequences.append(seq)
        weights.append(weight)
        lengths.append(len(seq))
        if len(sequences) == batch_size:
            flush()
    flush()
    if sum(weights) != len(ids) or len(weights) != expected or len(vectors) != expected:
        raise RuntimeError("Full thesis coverage or chunk count mismatch")
    return np.stack(vectors), np.asarray(weights), len(ids), max(lengths)


def comparisons(legacy, candidates):
    import numpy as np
    import pandas as pd
    all_indices = np.triu_indices(len(legacy), k=1)
    base_pairs = (legacy @ legacy.T)[all_indices]
    def rank_corr(pairs, control):
        a = pd.Series(pairs).rank()
        b = pd.Series(control).rank()
        corr = a.corr(b, method="pearson")
        return round(float(corr), 6) if np.isfinite(corr) else None

    report = {}
    for name, arr in candidates.items():
        same = np.sum(legacy * arr, axis=1)
        pair = (arr @ arr.T)[all_indices]
        report[name] = {
            "same_thesis_cosine_vs_legacy": descriptive(same),
            "cross_thesis_pairwise_cosine": descriptive(pair),
            "pairwise_rank_spearman_vs_legacy": rank_corr(pair, base_pairs),
            "pairwise_rank_spearman_vs_all_weighted": rank_corr(
                pair, (candidates["all_weighted"] @ candidates["all_weighted"].T)[all_indices]
            ),
        }
    return report


def study(args):
    import numpy as np
    import pandas as pd
    import torch
    from transformers import AutoModel, AutoTokenizer
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable; run inside an assigned MIG instance")
    if args.documents != 12:
        raise ValueError("This study reproduces the established 12-document pilot; use 12")
    root = args.project_root.expanduser().resolve()
    workspace = Path(__file__).resolve().parent.parent
    population, aligned = check_row_alignment(root)
    corpus = root / "data/processed/04_clean_corpus.parquet"
    length = pd.read_parquet(corpus, columns=["fulltext_chars"])["fulltext_chars"]
    selected = choose_indices(length, args.documents)
    prior_ids, prior_vectors, _ = load_pilot_vectors(
        workspace / "data/revision_private/dual_mig_pilot", "two_mig_pilot_v1",
        [6, 6]
    )
    if sorted(selected) != sorted(prior_ids.tolist()):
        raise ValueError("Sample identities differ from previous pilot; stop")
    texts = extract_rows(corpus, selected)
    model_weights = np.load(
        root / "data/processed/05_embeddings.npy", mmap_mode="r", allow_pickle=False
    )
    if model_weights.shape != (population, 1024):
        raise ValueError("Original E5 embedding shape mismatch")

    tokenizer = AutoTokenizer.from_pretrained(
        args.model, use_fast=True, local_files_only=True
    )
    tokenizer.model_max_length = 10**9
    torch.manual_seed(42)
    model = AutoModel.from_pretrained(
        args.model, dtype=torch.float16, use_safetensors=True, local_files_only=True
    ).to("cuda")
    model.eval()
    torch.cuda.reset_peak_memory_stats()
    t0 = time.perf_counter()
    all_results = {k: [] for k in (
        "all_weighted", "middle_80pct", "first_25pct", "equal_three_regions"
    )}
    windows_count = 0
    full_tokens = 0
    for row in selected:
        v, unique, tokens, _ = compute_chunks(
            texts[row], tokenizer, model, torch, args.batch_size,
            args.chunk_tokens, args.overlap, args.max_chunks
        )
        outputs = pool_strategies(v, unique)
        for name, vector in outputs.items():
            all_results[name].append(vector)
        windows_count += len(v)
        full_tokens += tokens
    matrices = {name: np.stack(values) for name, values in all_results.items()}
    old = np.asarray(model_weights[selected], dtype=np.float32)
    old = old / np.linalg.norm(old, axis=1, keepdims=True)
    # Verify the all-weighted vector is a repeat of the original pilot encoding.
    prior_by_row = dict(zip(prior_ids.tolist(), prior_vectors))
    reproduced = np.asarray([
        float(np.dot(matrices["all_weighted"][i], prior_by_row[row]))
        for i, row in enumerate(selected)
    ])
    if reproduced.min() < 0.999:
        raise RuntimeError("Full-weighted baseline could not reproduce prior pilot within cosine 0.999")
    measured = time.perf_counter() - t0
    return {
        "schema_version": 1,
        "experiment": "E5_document_pooling_sensitivity",
        "status": "completed_small_gpu_geometry_study",
        "n_documents": args.documents,
        "population_rows": population,
        "row_alignment": aligned,
        "total_windows_processed": int(windows_count),
        "total_fulltext_tokens": int(full_tokens),
        "gpu_seconds_excluding_model_load": round(measured, 3),
        "peak_torch_allocated_gib": round(float(torch.cuda.max_memory_allocated()) / 1024**3, 3),
        "baseline_reproduction_cosine": descriptive(reproduced),
        "model": args.model,
        "chunk_content_tokens": args.chunk_tokens,
        "overlap_tokens": args.overlap,
        "pooling": {
            "all_weighted": "all normalized chunk vectors weighted by newly covered tokens",
            "middle_80pct": "exclude first/last 10% of window positions; exploratory content-trim proxy",
            "first_25pct": "first quarter of window positions; deliberately partial-content diagnostic",
            "equal_three_regions": "length-weighted unit mean within each of three document-position regions, equal region weights then L2 normalization",
        },
        "geometry": comparisons(old, matrices),
        "notes": [
            "Only aggregate statistics reported. No thesis IDs, texts, row indices, or private embeddings exported.",
            "Every variant shares identical first-stage E5 chunk embeddings.",
            "Cosine magnitude or separation does not establish scientific validity or higher classification accuracy.",
            "Small length-quantile pilot is not an independent population evaluation sample.",
            "The first-quarter proxy is NOT a complete-document semantic representation.",
            "Expert-coded SDG and PDOT reference labels are needed to compare classification metrics.",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root", type=Path, required=True)
    p.add_argument("--model", default="intfloat/multilingual-e5-large")
    p.add_argument("--documents", type=int, default=12)
    p.add_argument("--batch-size", type=int, default=1)
    p.add_argument("--chunk-tokens", type=int, default=384)
    p.add_argument("--overlap", type=int, default=48)
    p.add_argument("--max-chunks", type=int, default=400)
    p.add_argument("--output", type=Path,
                   default=Path("docs/audits/pooling_sensitivity_v1.json"))
    a = p.parse_args()
    if a.batch_size < 1 or a.batch_size > 4:
        p.error("Use batch sizes 1-4 on the 10-GiB MIG")
    if a.chunk_tokens > 508 or a.chunk_tokens < 1 or not 0 <= a.overlap < a.chunk_tokens:
        p.error("Invalid content window or overlap")
    result = study(a)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print("Pooling sensitivity pilot completed; documents:", result["n_documents"])
    print("Total chunks:", result["total_windows_processed"])
    print("Full weighted baseline reproduction minimum cosine:",
          result["baseline_reproduction_cosine"]["min"])
    print("Only aggregate geometry diagnostics saved:", a.output)


if __name__ == "__main__":
    main()
