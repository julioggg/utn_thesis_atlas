#!/usr/bin/env python3
"""Reviewer 4: read-only aggregate comparisons for the frozen full-text E5 atlas.

Run on CEDIA in the revision clone. Requires private HPC source files and
never writes/commits source records. Displays only aggregate year/SDG counts
plus up to three PUBLIC REPOSITORY HANDLES per requested topic for manual
verification; never paste those handles into a public audit report.

This script reports observed classifications, not corrected SDG prevalence.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root", type=Path, required=True)
    args = p.parse_args()
    workspace = Path(__file__).resolve().parents[1]
    original = args.project_root.expanduser().resolve()
    sys.path.insert(0, str(workspace / "scripts"))
    from reviewer_stage1_stats import clean_faculties
    from reviewer_shared import normalize_codes
    from reviewer_legacy_alignment_replay import freeze_original_dicts

    frame = pd.read_parquet(
        original / "data/processed/07_alignment_pdot_ods_needs.parquet",
        columns=["handle_id", "year", "faculty", "career", "topic"],
    )
    if len(frame) != 7830 or frame["handle_id"].isna().any() or frame["handle_id"].duplicated().any():
        raise ValueError("Frozen census or row order invalid")
    frame, audit = clean_faculties(frame)
    if (audit["strict_known_five_faculty_rows"], audit["career_imputed_rows"], audit["unresolved_rows"]) != (6038,188,1604):
        raise ValueError("Faculty-mapping census differs from manuscript")
    inventory_path = workspace / "data/revision_private/descriptor_inventory/descriptor_source_candidates_PRIVATE.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    taxonomies, _ = freeze_original_dicts(inventory, original)
    ods_labels = list(taxonomies["ods"])

    pred_path = workspace / "data/revision_private/reviewer_fulltext_reclassification/reclassification_all_7830_PRIVATE.npz"
    with np.load(pred_path, allow_pickle=False) as z:
        indices = np.asarray(z["ods_fulltext_centered_top3_indices"][:, 0], dtype=int)
    if indices.shape != (7830,) or (indices < 0).any() or (indices >= len(ods_labels)).any():
        raise ValueError("Wrong frozen E5 score shape or class ordering")
    frame["sdg"] = normalize_codes([ods_labels[int(i)] for i in indices])
    counts = frame["sdg"].value_counts()
    if (int(counts.get("ODS 4", 0)),int(counts.get("ODS 3", 0)),int(counts.get("ODS 8", 0))) != (1520,1431,658):
        raise ValueError("Classification snapshot does not match manuscript Tables 2/3")
    frame["group"] = np.where(frame["faculty5"].notna(), "Resolved (6226)", "Unresolved (1604)")
    frame["year_int"] = pd.to_numeric(frame["year"], errors="coerce").astype("Int64")
    if frame["year_int"].isna().any():
        print("WARNING: missing or invalid years:",int(frame["year_int"].isna().sum()))

    print("\nYEAR DISTRIBUTION (counts and percentage within each faculty-resolution group)")
    print("Year | Resolved n | Resolved % | Unresolved n | Unresolved %")
    for year in range(2021, 2027):
        a=int(((frame["group"]=="Resolved (6226)") & (frame["year_int"]==year)).sum())
        b=int(((frame["group"]=="Unresolved (1604)") & (frame["year_int"]==year)).sum())
        print(f"{year} | {a} | {a/6226*100:.2f} | {b} | {b/1604*100:.2f}")
    print("\nSDG DISTRIBUTION (frozen E5 fulltext_centered; counts and within-group percentage)")
    print("SDG | Resolved n | Resolved % | Unresolved n | Unresolved %")
    for sdg in range(1,18):
        a=int(((frame["group"]=="Resolved (6226)") & (frame["sdg"]==f"ODS {sdg}")).sum())
        b=int(((frame["group"]=="Unresolved (1604)") & (frame["sdg"]==f"ODS {sdg}")).sum())
        print(f"SDG {sdg} | {a} | {a/6226*100:.2f} | {b} | {b/1604*100:.2f}")

    print("\nSOURCE-ORDER LOCAL THEMES — verify against actual NEEDS descriptor values")
    for i,(label,definition) in enumerate(taxonomies["need"].items(),1):
        print(f"LP{i:02d} | {label} | {definition[:120].replace(chr(10),' ')}")

    print("\nPOTENTIAL REPRESENTATIVE DOCUMENTS (HANDLE ONLY; verify title on public repository)")
    vectors = np.load(original / "data/processed/05_embeddings.npy", mmap_mode="r", allow_pickle=False)
    if vectors.shape != (7830,1024):
        raise ValueError("Historical topic vector matrix differs from expected dimensions")
    topics = pd.to_numeric(frame["topic"], errors="coerce")
    for topic in (54,16,43):
        pool=np.flatnonzero((topics == topic).to_numpy())
        if not len(pool):
            print("Topic",topic,": not found"); continue
        centroid=np.asarray(vectors[pool],dtype=np.float32).mean(axis=0)
        centroid/=max(float(np.linalg.norm(centroid)),1e-12)
        recent = pool[np.isin(frame["year_int"].fillna(-1).to_numpy()[pool],[2024,2025])]
        candidates=recent if len(recent) else pool
        x=np.asarray(vectors[candidates],dtype=np.float32)
        similarities=(x@centroid)/np.maximum(np.linalg.norm(x,axis=1),1e-12)
        best=candidates[np.argsort(-similarities)[:3]]
        print(f"Topic {topic}:", "; ".join(frame.iloc[best]["handle_id"].astype(str).tolist()))
    print("\nNO FILES WRITTEN. Do not publish any personal identifiers or thesis text.")

if __name__=="__main__":
    main()
