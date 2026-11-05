#!/usr/bin/env python3
"""Aggregate-only, read-only audit of the original Parquet results (pandas/pyarrow).

No row-level thesis, author, advisor, handle or text is saved to the report.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

CANDIDATES = [
    "data/processed/07_alignment_pdot_ods_needs.parquet",
    "data/processed/06_corpus_with_topics.parquet",
    "data/processed/04_clean_corpus.parquet",
    "data/metadata/01_items_metadata_full_v2.parquet",
    "data/metadata/01_items_metadata.parquet",
]
COLUMNS = [
    "handle_id", "year", "faculty", "career", "title", "authors", "advisor",
    "fulltext_chars", "analysis_text", "text_hash", "n_pdfs", "topic",
    "ods_top", "ods_top1", "ods_score", "ods_top1_score",
    "pdot_top", "pdot_top1", "pdot_score", "pdot_top1_score",
    "need_top", "need_top1", "need_score", "need_top1_score",
]

def stats(series):
    import pandas as pd
    x = pd.to_numeric(series, errors="coerce").dropna()
    if x.empty:
        return {"n": 0}
    return {k: round(float(v), 6) for k, v in {
        "min": x.min(), "q05": x.quantile(.05), "median": x.median(),
        "q95": x.quantile(.95), "max": x.max(), "mean": x.mean(),
    }.items()} | {"n": int(len(x))}

def nonempty(series):
    return int(series.astype("string").fillna("").str.strip().ne("").sum())

def run(root: Path, corpus: Path | None = None) -> dict:
    import pandas as pd
    import pyarrow.parquet as pq
    source = (corpus if corpus.is_absolute() else root / corpus) if corpus else next(
        (root / x for x in CANDIDATES if (root / x).is_file()), None
    )
    if source is None or not source.is_file():
        raise FileNotFoundError("No expected Parquet file found; specify --corpus")
    metadata = pq.ParquetFile(str(source))
    available = set(metadata.schema_arrow.names)
    selected = [x for x in COLUMNS if x in available]
    if not selected:
        raise ValueError("No known schema columns found")
    df = pd.read_parquet(source, columns=selected)
    n = len(df)
    try:
        source_name = str(source.relative_to(root))
    except ValueError:
        source_name = "[external parquet location]"
    report = {
        "schema_version": 1,
        "source_file": source_name, "row_count": int(n),
        "parquet_metadata_row_count": int(metadata.metadata.num_rows),
        "present_columns": selected, "missing_expected_columns": sorted(set(COLUMNS) - available),
        "difference_from_manuscript_count_7830": int(n - 7830),
        "warnings": ["This is not model validation; independent expert labels are still necessary.",
                     "Different pipeline stages may contain different populations."],
    }
    if "handle_id" in df:
        report["duplicate_handles"] = int(df["handle_id"].dropna().duplicated().sum())
        report["null_handles"] = int(df["handle_id"].isna().sum())
    if "text_hash" in df:
        report["duplicate_text_hashes"] = int(df["text_hash"].dropna().duplicated().sum())
    if "year" in df:
        years = pd.to_numeric(df["year"], errors="coerce")
        report["year_counts"] = {str(int(k)): int(v) for k, v in
                                 years.value_counts().sort_index().items()}
        if (years == 2026).any():
            report["warnings"].append("2026 is possibly a partial year; do not compare trends without exposure correction.")
    if "faculty" in df:
        faculties = df["faculty"].astype("string").fillna("").str.strip()
        report["faculty_metadata"] = {
            "empty": int(faculties.eq("").sum()),
            "misc_or_unassigned": int(faculties.str.contains(
                "unassigned|no faculty|misc", case=False, regex=True, na=False).sum()),
            "distinct_nonempty": int(faculties.loc[faculties.ne("")].nunique()),
            "counts": {str(k): int(v) for k, v in faculties.value_counts().items()
                       if v >= 5 and str(k)},
        }
    for field in ["title", "authors", "advisor", "career"]:
        if field in df:
            report[field + "_nonempty_records"] = nonempty(df[field])
    if "advisor" in df:
        advisors = df["advisor"].astype("string").str.strip().replace("", pd.NA).dropna()
        report["unique_nonempty_advisor_values"] = int(advisors.nunique())
    if "fulltext_chars" in df:
        report["fulltext_length_characters"] = stats(df["fulltext_chars"])
    if "analysis_text" in df:
        lengths = df["analysis_text"].fillna("").astype(str).str.len()
        report["original_analysis_input_characters"] = stats(lengths)
        report["inputs_over_2000_characters"] = int((lengths > 2000).sum())
        report["warnings"].append("Character count is not a token count; run a tokenizer-specific truncation audit.")
    if "topic" in df:
        report["distinct_topic_labels"] = int(df["topic"].dropna().nunique())
    for taxonomy in ["ods", "pdot", "need"]:
        label_col = next((x for x in [taxonomy + "_top1", taxonomy + "_top"] if x in df), None)
        score_col = next((x for x in [taxonomy + "_top1_score", taxonomy + "_score"] if x in df), None)
        if label_col:
            labels = df[label_col].astype("string").fillna("").str.strip()
            report[taxonomy + "_assigned"] = int(labels.ne("").sum())
            report[taxonomy + "_counts"] = {str(k): int(v) for k, v in
                                            labels.value_counts().items() if v >= 5 and str(k)}
            if labels.ne("").sum() == n:
                report["warnings"].append(taxonomy + ": all rows assigned; evaluate abstention threshold.")
        if score_col:
            report[taxonomy + "_score_distribution"] = stats(df[score_col])
    return report

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root", required=True, type=Path)
    p.add_argument("--corpus", default=None, type=Path)
    p.add_argument("--output", default=Path("reports/public/corpus_audit.json"), type=Path)
    a = p.parse_args()
    result = run(a.project_root.expanduser().resolve(), a.corpus)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Aggregate audit written to {a.output}; rows={result['row_count']}.")
    print("Review all aggregate categories before sharing to the public repository.")

if __name__ == "__main__":
    main()
