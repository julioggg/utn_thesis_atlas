#!/usr/bin/env python3
"""Read-only provenance audit of the original HPC thesis atlas. Aggregates only.

Does not export student names, advisor names, handles, full texts, individual scores,
absolute HPC paths, PDFs or embeddings. Requires pandas, numpy and pyarrow.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

STAGES = {
    "metadata": ("data/metadata/01_items_metadata.parquet",
                 ["handle_id", "year", "ok", "title", "authors", "advisor", "faculty", "career", "n_pdfs"]),
    "downloads": ("data/metadata/02_pdf_downloads.parquet",
                  ["handle_id", "download_ok", "size"]),
    "extraction": ("data/metadata/03_text_extraction.parquet",
                   ["handle_id", "extract_ok", "chars", "pages"]),
    "clean": ("data/processed/04_clean_corpus.parquet",
              ["handle_id", "text_hash", "fulltext_chars", "analysis_text"]),
    "topics": ("data/processed/06_corpus_with_topics.parquet",
               ["handle_id", "topic"]),
    "alignment": ("data/processed/07_alignment_pdot_ods_needs.parquet",
                  ["handle_id", "faculty", "ods_top1", "ods_top1_score", "ods_top2_score",
                   "pdot_top1_score", "pdot_top2_score", "need_top1_score", "need_top2_score"]),
}

def dist(x):
    import pandas as pd
    x = pd.to_numeric(x, errors="coerce").dropna()
    if x.empty:
        return {"n": 0}
    return {"n": int(len(x)), "min": float(x.min()), "median": float(x.median()),
            "p05": float(x.quantile(.05)), "p95": float(x.quantile(.95)),
            "max": float(x.max()), "mean": float(x.mean())}

def main_audit(root):
    import numpy as np
    import pandas as pd
    import pyarrow.parquet as pq
    results = {
        "schema_version": 1, "stages": {}, "classification": {}, "embeddings": {}, "k_selection": {},
        "privacy": "Only aggregate statistics are included. Review before public release.",
    }
    for stage, (relative, expected) in STAGES.items():
        source = root / relative
        if not source.is_file():
            results["stages"][stage] = {"available": False}
            continue
        available = set(pq.ParquetFile(source).schema_arrow.names)
        cols = [col for col in expected if col in available]
        df = pd.read_parquet(source, columns=cols)
        out = {"available": True, "rows": int(len(df)),
               "present_columns": cols, "missing_columns": sorted(set(expected) - available)}
        if "handle_id" in df:
            ids = df["handle_id"].astype("string")
            out["unique_handles"] = int(ids.nunique(dropna=True))
            out["repeated_handle_rows"] = int(ids.dropna().duplicated().sum())
        if stage == "metadata":
            for col in ("title", "authors", "advisor", "faculty", "career"):
                if col in df:
                    out[col + "_nonempty"] = int(df[col].astype("string").fillna("").str.strip().ne("").sum())
            if "ok" in df:
                out["harvest_success_rows"] = int(df["ok"].eq(True).sum())
            if "n_pdfs" in df:
                out["records_with_pdf_links"] = int((pd.to_numeric(df["n_pdfs"], errors="coerce") > 0).sum())
        if stage == "downloads" and "download_ok" in df:
            success = df["download_ok"].eq(True)
            out["download_success_rows"] = int(success.sum())
            out["download_failed_rows"] = int((~success).sum())
            if "handle_id" in df:
                out["handles_with_successful_pdf"] = int(df.loc[success, "handle_id"].nunique())
        if stage == "extraction":
            if "extract_ok" in df:
                success = df["extract_ok"].eq(True)
                out["extraction_success_rows"] = int(success.sum())
                out["extraction_failed_rows"] = int((~success).sum())
                if "handle_id" in df:
                    out["handles_with_successful_extraction"] = int(df.loc[success, "handle_id"].nunique())
            if "chars" in df:
                out["extracted_character_counts"] = dist(df["chars"])
                out["extractions_over_1000_chars"] = int(
                    (pd.to_numeric(df["chars"], errors="coerce") > 1000).sum())
        if stage == "clean":
            if "text_hash" in df:
                out["repeated_text_prefix_hash_rows"] = int(df["text_hash"].dropna().duplicated().sum())
                out["hash_caution"] = "Legacy MD5 hashes only first 200000 text characters, not complete thesis."
            if "fulltext_chars" in df:
                out["fulltext_length_characters"] = dist(df["fulltext_chars"])
            if "analysis_text" in df:
                out["analysis_text_length_characters"] = dist(df["analysis_text"].fillna("").astype(str).str.len())
        if stage == "topics" and "topic" in df:
            out["distinct_topics"] = int(df["topic"].nunique(dropna=True))
        if stage == "alignment":
            for tax in ("ods", "pdot", "need"):
                a = tax + "_top1_score"
                b = tax + "_top2_score"
                if a in df and b in df:
                    margins = pd.to_numeric(df[a], errors="coerce") - pd.to_numeric(df[b], errors="coerce")
                    results["classification"][tax + "_margin_top1_top2"] = dist(margins)
                    results["classification"][tax + "_fraction_margin_under_0_01"] = float((margins < .01).mean())
                    results["classification"][tax + "_fraction_margin_under_0_02"] = float((margins < .02).mean())
            if "ods_top1" in df and "faculty" in df:
                hit = df["ods_top1"].astype("string").fillna("").str.match(r"(?i)^ods\s*4\b")
                faculty = df["faculty"].astype("string").fillna("").str.strip().replace("", "[unassigned]")
                pairs = pd.DataFrame({"faculty": faculty, "is_sdg4": hit.fillna(False)})
                summaries = pairs.groupby("faculty")["is_sdg4"].agg(["sum", "size"])
                results["classification"]["sdg4_by_faculty"] = [
                    {"faculty": str(key), "n": int(v["size"]), "sdg4_n": int(v["sum"]),
                     "sdg4_share": round(float(v["sum"]) / float(v["size"]), 5)}
                    for key, v in summaries.iterrows() if int(v["size"]) >= 5
                ]
        results["stages"][stage] = out
    embeddings = root / "data/processed/05_embeddings.npy"
    if embeddings.is_file():
        emb = np.load(embeddings, mmap_mode="r", allow_pickle=False)
        results["embeddings"] = {"available": True, "shape": list(emb.shape), "dtype": str(emb.dtype)}
        if emb.ndim == 2 and emb.shape[0] > 0:
            sample = np.asarray(emb[::max(1, emb.shape[0] // 1000)], dtype=np.float32)
            results["embeddings"]["sampled_norms"] = dist(np.linalg.norm(sample, axis=1))
    else:
        results["embeddings"] = {"available": False}
    kfile = root / "reports/06_k_optimization.csv"
    if kfile.is_file():
        km = pd.read_csv(kfile)
        results["k_selection"] = {"available": True, "row_count": int(len(km)), "column_names": km.columns.tolist()}
        if {"k", "silhouette_cosine_sample"}.issubset(km.columns):
            trials = [{"k": int(v["k"]), "cosine_silhouette": round(float(v["silhouette_cosine_sample"]), 6)}
                      for _, v in km.iterrows() if pd.notna(v["k"]) and pd.notna(v["silhouette_cosine_sample"])]
            results["k_selection"]["trials"] = trials
            if trials:
                results["k_selection"]["best_k"] = max(trials, key=lambda d: d["cosine_silhouette"])["k"]
    else:
        results["k_selection"] = {"available": False}
    return results

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("reports/public/provenance_audit.json"))
    args = p.parse_args()
    report = main_audit(args.project_root.expanduser().resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved read-only pipeline provenance audit to {args.output}")
    print("No individual thesis text, handle, advisor name or embedding was exported.")

if __name__ == "__main__":
    main()
