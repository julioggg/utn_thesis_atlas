#!/usr/bin/env python3
"""Count ALL E5 full-text token windows in the 7,830-record original corpus.

Read-only, CPU-only, streaming. Writes aggregate statistics and counts ONLY,
never raw thesis text, student identifiers, handles, titles, or per-row output.
This is a compute census, not an instruction to run the full GPU pipeline.
"""
from __future__ import annotations
import argparse
import json
import time
from pathlib import Path
from audit_chunk_budget import chunk_count, summary


def compute_census(project, tokenizer_name, chunk_tokens, overlap, local_only=False):
    import pyarrow.parquet as pq
    from transformers import AutoTokenizer
    source = project / "data/processed/04_clean_corpus.parquet"
    if not source.is_file():
        raise FileNotFoundError("04_clean_corpus.parquet not found")
    parquet = pq.ParquetFile(source)
    if "full_text" not in parquet.schema_arrow.names:
        raise ValueError("Clean corpus does not contain full_text")
    tokenizer = AutoTokenizer.from_pretrained(
        tokenizer_name, use_fast=True, local_files_only=local_only
    )
    prefix_tokens = len(tokenizer.encode("passage: ", add_special_tokens=False))
    special_tokens = tokenizer.num_special_tokens_to_add(pair=False)
    if chunk_tokens > 512 - prefix_tokens - special_tokens:
        raise ValueError("Configured chunk size exceeds 512-token E5 input capacity")
    tokenizer.model_max_length = 10**9  # Count full length: never send sequence to model.
    window_counts = []
    token_counts = []
    empty = 0
    start = time.perf_counter()
    for batch in parquet.iter_batches(batch_size=32, columns=["full_text"]):
        for text in batch.column(0).to_pylist():
            if not text or not str(text).strip():
                empty += 1
                count = 0
            else:
                count = len(tokenizer.encode(text, add_special_tokens=False, truncation=False))
            token_counts.append(count)
            window_counts.append(chunk_count(count, chunk_tokens, overlap))
    n = len(token_counts)
    if n != parquet.metadata.num_rows:
        raise AssertionError("Streaming row count does not equal Parquet metadata count")
    def histogram(counts):
        bins = ((0, 0), (1, 100), (101, 200), (201, 400),
                (401, 800), (801, 1200), (1201, 2400), (2401, None))
        out = {}
        for lower, upper in bins:
            label = f"{lower}-{upper}" if upper is not None else f"{lower}+"
            out[label] = sum(lower <= x <= upper for x in counts) if upper is not None else sum(
                x >= lower for x in counts)
        return out
    return {
        "schema_version": 1,
        "status": "complete_fulltext_token_window_census",
        "population_rows": n,
        "fulltext_source": "data/processed/04_clean_corpus.parquet:full_text",
        "model_tokenizer": tokenizer_name,
        "window_configuration": {
            "content_tokens": chunk_tokens, "overlap_tokens": overlap,
            "prefix_tokens": prefix_tokens, "special_tokens": special_tokens,
            "maximum_input_tokens": 512,
        },
        "empty_fulltexts": int(empty),
        "total_fulltext_tokens": int(sum(token_counts)),
        "total_nonempty_windows": int(sum(window_counts)),
        "fulltext_token_counts": summary(token_counts),
        "window_counts_per_thesis": summary(window_counts),
        "windows_per_thesis_bins": histogram(window_counts),
        "theses_over_400_windows": int(sum(x > 400 for x in window_counts)),
        "theses_over_800_windows": int(sum(x > 800 for x in window_counts)),
        "theses_over_1200_windows": int(sum(x > 1200 for x in window_counts)),
        "elapsed_cpu_seconds": round(time.perf_counter() - start, 3),
        "limitations": [
            "This is exact window arithmetic over extracted full_text, not a GPU throughput estimate.",
            "No model inference, deduplication, boilerplate removal, semantic validity check or expert validation was performed.",
            "Full-text quality and inclusion of bibliography, appendices, OCR artifacts and duplicates require separate study.",
            "All texts and record-level numbers remain in CEDIA. Only aggregate counts are exported.",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root", type=Path, required=True)
    p.add_argument("--model", default="intfloat/multilingual-e5-large")
    p.add_argument("--chunk-tokens", type=int, default=384)
    p.add_argument("--overlap", type=int, default=48)
    p.add_argument("--local-files-only", action="store_true")
    p.add_argument("--output", type=Path,
                   default=Path("docs/audits/fulltext_chunk_census.json"))
    a = p.parse_args()
    report = compute_census(a.project_root.expanduser().resolve(), a.model,
                            a.chunk_tokens, a.overlap, a.local_files_only)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(f"Finished {report['population_rows']} theses; exact windows: {report['total_nonempty_windows']}")
    print(f"Above 400 windows: {report['theses_over_400_windows']}")
    print(f"Aggregate report: {a.output}")


if __name__ == "__main__":
    main()
