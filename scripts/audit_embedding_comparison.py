#!/usr/bin/env python3
"""Read-only comparison of original E5 vectors against full-text pilot vectors.

All row-level data and embeddings remain on CEDIA. Report contains aggregate
statistics only. This is a representation-change diagnostic, NOT a quality
evaluation and NOT SDG/PDOT classification validation.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path


def descriptive(values):
    import numpy as np
    x = np.asarray(values, dtype=np.float64)
    if x.size == 0:
        return {"n": 0}
    if not np.isfinite(x).all():
        raise ValueError("Non-finite values in comparison")
    return {
        "n": int(x.size),
        "min": round(float(x.min()), 6),
        "p05": round(float(np.quantile(x, .05)), 6),
        "median": round(float(np.median(x)), 6),
        "p95": round(float(np.quantile(x, .95)), 6),
        "max": round(float(x.max()), 6),
        "mean": round(float(x.mean()), 6),
    }


def check_row_alignment(root):
    """Prove positional provenance across 04->06->07 (handles never exported)."""
    import pandas as pd
    stages = [
        "data/processed/04_clean_corpus.parquet",
        "data/processed/06_corpus_with_topics.parquet",
        "data/processed/07_alignment_pdot_ods_needs.parquet",
    ]
    handles = []
    for path in stages:
        x = pd.read_parquet(root / path, columns=["handle_id"])["handle_id"]
        if x.isna().any() or x.duplicated().any():
            raise ValueError("Stage contains null or repeated handles; cannot align by position")
        handles.append(x.astype(str).to_numpy())
    if len({len(x) for x in handles}) != 1:
        raise ValueError("Stage lengths differ; positional embedding comparison is unsafe")
    import numpy as np
    aligned_04_06 = bool(np.array_equal(handles[0], handles[1]))
    aligned_04_07 = bool(np.array_equal(handles[0], handles[2]))
    if not aligned_04_06 or not aligned_04_07:
        raise ValueError("Handle order differs between 04/06/07. Stop rather than compare wrong theses.")
    # The legacy embedding step writes this row-by-row manifest alongside the .npy file.
    embedding_index = root / "data/processed/05_embedding_index.csv"
    if not embedding_index.is_file():
        raise FileNotFoundError(
            "05_embedding_index.csv is unavailable; cannot verify the row order of 05_embeddings.npy"
        )
    original_index = pd.read_csv(
        embedding_index, usecols=["handle_id"], dtype={"handle_id": str},
        keep_default_na=False
    )["handle_id"].to_numpy()
    aligned_04_05 = bool(np.array_equal(handles[0], original_index))
    if not aligned_04_05:
        raise ValueError("Legacy 05_embedding_index row order does not match original clean corpus")
    return len(handles[0]), {
        "04_vs_05_embedding_index": aligned_04_05,
        "04_vs_06": aligned_04_06, "04_vs_07": aligned_04_07,
    }


def load_pilot_vectors(private_root, run_id, expected_per_slot):
    import numpy as np
    rows, vectors, counts = [], [], []
    for slot in range(2):
        src = private_root / f"{run_id}_slot{slot}" / "gpu_pilot_vectors.npz"
        if not src.is_file():
            raise FileNotFoundError("A private per-GPU pilot vector file is missing")
        with np.load(src, allow_pickle=False) as arr:
            ids = arr["row_indices"]
            vec = arr["vectors"]
        if ids.ndim != 1 or vec.ndim != 2 or len(ids) != len(vec):
            raise ValueError("Malformed GPU pilot array")
        if vec.shape[1] != 1024:
            raise ValueError("Unexpected E5 vector dimensionality")
        if not np.issubdtype(ids.dtype, np.integer):
            raise ValueError("Row indices must be integral")
        if len(ids) != expected_per_slot[slot]:
            raise ValueError("Private vector count differs from the published worker report")
        rows.append(ids)
        vectors.append(vec)
        counts.append(int(len(ids)))
    merged_rows = np.concatenate(rows)
    merged_vec = np.concatenate(vectors).astype(np.float32)
    if len(set(merged_rows.tolist())) != len(merged_rows):
        raise ValueError("Duplicate document indices across GPU workers")
    if not np.isfinite(merged_vec).all():
        raise ValueError("Non-finite full-text embeddings")
    return merged_rows, merged_vec, counts


def comparison(root, workspace, run_id):
    import numpy as np
    import pandas as pd
    population, stage_check = check_row_alignment(root)
    original_path = root / "data/processed/05_embeddings.npy"
    base = np.load(original_path, mmap_mode="r", allow_pickle=False)
    if base.shape != (population, 1024):
        raise ValueError("Original embeddings are not aligned to 04/06/07 dimensions")
    summaries = []
    for slot in range(2):
        p = workspace / "docs/audits" / f"{run_id}_slot{slot}.json"
        if not p.is_file():
            raise FileNotFoundError("Public aggregate pilot shard report missing")
        summaries.append(json.loads(p.read_text(encoding="utf-8")))
    expected = [int(x["documents_processed"]) for x in summaries]
    indices, current, counts = load_pilot_vectors(
        workspace / "data/revision_private/dual_mig_pilot", run_id, expected
    )
    if len(indices) < 3:
        raise ValueError("Need at least three successfully encoded documents for pairwise comparison")
    if int(indices.min()) < 0 or int(indices.max()) >= population:
        raise ValueError("Pilot index out of bounds")
    legacy = np.asarray(base[indices], dtype=np.float32)
    if not np.isfinite(legacy).all():
        raise ValueError("Non-finite original embeddings")
    old_norm = np.linalg.norm(legacy, axis=1)
    new_norm = np.linalg.norm(current, axis=1)
    if np.any(old_norm < 1e-8) or np.any(new_norm < 1e-8):
        raise ValueError("A document has a zero-norm embedding")
    old_unit = legacy / old_norm[:, None]
    new_unit = current / new_norm[:, None]
    cross_cosine = np.sum(old_unit * new_unit, axis=1)
    old_sim = old_unit @ old_unit.T
    new_sim = new_unit @ new_unit.T
    upper = np.triu_indices(len(indices), k=1)
    old_pairs = old_sim[upper]
    new_pairs = new_sim[upper]
    # Spearman is Pearson correlation of average ranks; avoid requiring SciPy on HPC.
    rank_spearman = float(pd.Series(old_pairs).rank().corr(\n        pd.Series(new_pairs).rank(), method="pearson"))
    return {
        "schema_version": 1,
        "experiment": "original_vs_fulltext_e5_representation_change",
        "source": "original 05_embeddings.npy and private disjoint two-MIG pilot vectors",
        "n_original_theses": population,
        "alignment_verified": stage_check,
        "n_pilot_theses": int(len(indices)),
        "per_worker_private_vector_counts": counts,
        "new_vector_norms": descriptive(new_norm),
        "original_vector_norms": descriptive(old_norm),
        "original_new_same_thesis_cosine": descriptive(cross_cosine),
        "pilot_pairwise_distances": {
            "n_unique_pairs": int(len(old_pairs)),
            "old_cosine": descriptive(old_pairs),
            "new_cosine": descriptive(new_pairs),
            "pairwise_spearman": round(rank_spearman, 6) if np.isfinite(rank_spearman) else None,
        },
        "notes": [
            "Cosine drift is a representation change, NOT evidence of improved accuracy.",
            "These 12 thesis embeddings are from the length-quantile pilot, NOT an independent evaluation sample.",
            "No thesis titles, author names, handles, indices, texts or vectors are exported.",
            "Row-position comparisons are permitted only after 04/06/07 handle-order equality checks.",
            "Human-adjudicated labels are still required for SDG and PDOT precision, recall and F1.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", default="two_mig_pilot_v1")
    parser.add_argument("--output", type=Path,
                        default=Path("docs/audits/embedding_comparison_v1.json"))
    args = parser.parse_args()
    root = args.project_root.expanduser().resolve()
    workspace = args.workspace.expanduser().resolve()
    result = comparison(root, workspace, args.run_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print("Comparison saved:", args.output)
    print("Positional handle alignment verified across 04/05-index/06/07.")
    print(f"Compared {result['n_pilot_theses']} embeddings, no row-level data exported.")


if __name__ == "__main__":
    main()
