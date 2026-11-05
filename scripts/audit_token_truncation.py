#!/usr/bin/env python3
"""Quantify actual E5 input truncation without exposing any thesis text.

Counts tokens for 'passage: ' + the original analysis_text field, as fed to
SentenceTransformer in the submitted legacy pipeline. No GPU required.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

def describe(values):
    import numpy as np
    x = np.asarray(values, dtype="float64")
    if not x.size:
        return {"n": 0}
    return {"n": int(x.size), "min": int(np.min(x)), "p05": float(np.percentile(x, 5)),
            "median": float(np.median(x)), "p95": float(np.percentile(x, 95)),
            "max": int(np.max(x)), "mean": float(np.mean(x))}

def audit(project: Path, corpus: Path, model: str, cutoff: int, limit: int,
          seed: int, local_only: bool) -> dict:
    import pandas as pd
    from transformers import AutoTokenizer
    import numpy as np
    src = corpus if corpus.is_absolute() else project / corpus
    if not src.is_file():
        raise FileNotFoundError(f"Input Parquet missing: {src.name}")
    frame = pd.read_parquet(src, columns=["analysis_text"])
    total = len(frame)
    if limit and limit < total:
        # Random sample prevents arbitrary original row order from driving the estimate.
        rng = np.random.default_rng(seed)
        indices = rng.choice(total, size=limit, replace=False)
        frame = frame.iloc[indices]
    tokenizer = AutoTokenizer.from_pretrained(model, local_files_only=local_only)
    lengths, chars = [], []
    for value in frame["analysis_text"].fillna("").astype(str):
        text = "passage: " + " ".join(value.split())
        lengths.append(len(tokenizer.encode(text, add_special_tokens=True, truncation=False)))
        chars.append(len(text))
    token_arr = np.asarray(lengths)
    kept = np.minimum(token_arr, cutoff)
    count_over = int(np.sum(token_arr > cutoff))
    return {
        "schema_version": 1, "model_tokenizer": model, "requested_cutoff": cutoff,
        "original_corpus_rows": total, "sampled_rows": len(frame), "random_seed": seed,
        "complete_corpus_audit": len(frame) == total,
        "input_construction": "passage: + normalized original analysis_text",
        "token_lengths": describe(lengths), "character_lengths": describe(chars),
        "rows_over_cutoff": count_over,
        "fraction_rows_over_cutoff": round(count_over / max(len(frame), 1), 6),
        "mean_fraction_of_tokens_kept": round(float(np.mean(kept / np.maximum(token_arr, 1))), 6),
        "note": "Reports original analysis_text truncation only. It cannot establish full-thesis coverage, because legacy analysis_text uses at most the start of each PDF.",
    }

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root", type=Path, required=True)
    p.add_argument("--corpus", type=Path, default=Path("data/processed/04_clean_corpus.parquet"))
    p.add_argument("--model", default="intfloat/multilingual-e5-large")
    p.add_argument("--max-tokens", type=int, default=512)
    p.add_argument("--limit", type=int, default=0, help="Random-sample limit; 0 means complete corpus")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--local-files-only", action="store_true")
    p.add_argument("--output", type=Path, default=Path("reports/public/token_length_audit.json"))
    a = p.parse_args()
    if a.max_tokens <= 0 or a.limit < 0:
        p.error("max-tokens must be positive and limit non-negative")
    payload = audit(a.project_root.expanduser().resolve(), a.corpus, a.model,
                    a.max_tokens, a.limit, a.seed, a.local_files_only)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(f"Token audit written to {a.output}; n={payload['sampled_rows']}")
    print("No original thesis text or record identifier has been exported.")

if __name__ == "__main__":
    main()
