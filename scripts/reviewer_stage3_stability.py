#!/usr/bin/env python3
"""Controlled KMeans/UMAP seed and k sensitivity on aligned legacy E5 vectors.

Requires scikit-learn and umap-learn on CEDIA. Produces aggregate scores ONLY.
This is a NEW diagnostic comparison, not reproduction of the original
75-topic pipeline or accuracy of individual SDG labels. A frozen stratified
sample is used for budget control; full-data runs require a separate design.
"""
from __future__ import annotations
import argparse
import itertools
import time
from pathlib import Path

import numpy as np
import pandas as pd
from reviewer_shared import FIVE_FACULTIES, read_original_embeddings, write_public
from reviewer_stage1_stats import clean_faculties


def deterministic_sample(frame, n, seed):
    from numpy.random import default_rng
    rng = default_rng(seed)
    if n > len(frame) or n < 200:
        raise ValueError("Invalid stability sample size")
    # Distinct sample, approximately proportional to known faculty sizes,
    # retaining missing/other as a separate sampling stratum (not in tests).
    groups = frame["faculty5"].fillna("[unassigned]").astype(str)
    quota = (groups.value_counts(normalize=True) * n).to_dict()
    base = {k: min(int(v), int((groups == k).sum())) for k,v in quota.items()}
    while sum(base.values()) < n:
        available = [k for k in base if base[k] < np.sum(groups == k)]
        if not available:
            raise ValueError("No sample quota available")
        chosen = max(available, key=lambda k: (quota[k] - base[k],k))
        base[chosen] += 1
    selected = np.concatenate([
        rng.choice(np.flatnonzero(groups.to_numpy() == k), size=base[k], replace=False)
        for k in sorted(base)
        if base[k]
    ])
    return rng.permutation(selected).astype(int), base


def cluster_stability(x, ks, seeds, sample_size=600):
    from sklearn.cluster import MiniBatchKMeans
    from sklearn.metrics import adjusted_rand_score, silhouette_score
    scores = []
    groupings = {}
    for k in ks:
        groupings[k] = []
        for seed in seeds:
            model = MiniBatchKMeans(n_clusters=k, random_state=seed,
                                    batch_size=min(256, len(x)), n_init=3,
                                    max_iter=150, reassignment_ratio=.01)
            lab = model.fit_predict(x)
            nonempty = len(np.unique(lab))
            if nonempty < 2:
                score = None
            else:
                score = float(silhouette_score(
                    x, lab, metric="cosine", sample_size=min(sample_size,len(x)),
                    random_state=seed
                ))
            groupings[k].append(lab)
            scores.append({
                "k":k, "seed":seed, "clusters_nonempty": nonempty,
                "cosine_silhouette_sample": None if score is None else round(score,6),
                "inertia_euclidean": round(float(model.inertia_),4),
            })
    stability = {}
    for k, labels in groupings.items():
        if len(labels)<2:
            continue
        pairwise = [
            adjusted_rand_score(a,b)
            for a,b in itertools.combinations(labels,2)
        ]
        stability[str(k)] = {
            "adjusted_rand_index_pairwise_seeds":
                [round(float(v),6) for v in pairwise],
            "mean_ARI": round(float(np.mean(pairwise)),6),
            "minimum_ARI": round(float(np.min(pairwise)),6),
        }
    return {
        "model": "MiniBatchKMeans exploratory re-clustering in legacy 1024D E5 space",
        "not_a_reproduction_of_original_topic_pipeline": True,
        "candidate_k": list(ks),
        "seeds": list(seeds),
        "silhouette_sample_size": sample_size,
        "by_run": scores,
        "seed_stability_by_k": stability,
    }


def neighbor_indices(emb, k=15):
    n = len(emb)
    if n <= k:
        raise ValueError("Too few points for 2D neighbors")
    neighbors = np.empty((n,k), dtype=int)
    for start in range(0,n,128):
        end = min(n,start+128)
        dist = np.sum((emb[start:end,None,:]-emb[None,:,:])**2,axis=2)
        dist[np.arange(end-start), np.arange(start,end)] = np.inf
        best = np.argpartition(dist,kth=k-1,axis=1)[:,:k]
        neighbors[start:end] = best
    return neighbors


def umap_seed_stability(x, seeds, neighbors=15, min_dist=.1):
    import umap
    from sklearn.manifold import trustworthiness
    if len(seeds) < 2:
        raise ValueError("At least two UMAP seeds required")
    layouts = []
    trust = []
    for seed in seeds:
        algo = umap.UMAP(n_neighbors=neighbors, min_dist=min_dist,
                         n_components=2, random_state=seed,
                         metric="cosine", transform_seed=seed)
        y = algo.fit_transform(x)
        if y.shape != (len(x),2) or not np.isfinite(y).all():
            raise ValueError("Unexpected UMAP coordinates")
        layouts.append(y)
        trust.append(float(trustworthiness(x, y, n_neighbors=min(10,neighbors),
                                          metric="cosine")))
    indexes = [neighbor_indices(layout,k=min(15,neighbors))
               for layout in layouts]
    jaccard = []
    for a,b in itertools.combinations(indexes,2):
        overlaps = np.array([
            len(set(aa) & set(bb))/len(aa) for aa,bb in zip(a,b)
        ])
        jaccard.append(round(float(np.mean(overlaps)),6))
    return {
        "umap_version": getattr(umap,"__version__","unavailable"),
        "seeds": list(seeds), "n_neighbors":neighbors,"min_dist":min_dist,
        "trustworthiness_cosine_original_to_2d":
            [round(v,6) for v in trust],
        "mean_neighborhood_recall_at_k_between_umap_seeds": jaccard,
        "note": "Visualization stability only. UMAP area and convex hull overlap have no rigorous original-space area interpretation.",
    }


def analyze(args):
    original = args.project_root.expanduser().resolve()
    frame = pd.read_parquet(
        original / "data/processed/07_alignment_pdot_ods_needs.parquet",
        columns=["handle_id","faculty","career"]
    )
    if frame["handle_id"].isna().any() or frame["handle_id"].duplicated().any():
        raise ValueError("Original index integrity failure")
    aligned, _ = clean_faculties(frame)
    ix, strata = deterministic_sample(aligned,args.sample_size,args.seed)
    data, provenance = read_original_embeddings(original,len(frame))
    values = np.asarray(data[ix],dtype=np.float32)
    norm = np.linalg.norm(values,axis=1,keepdims=True)
    if np.any(norm < 1e-8):
        raise ValueError("Zero-norm embeddings")
    values /= norm
    k_candidates = sorted(set(int(k) for k in args.k_values.split(",")))
    seeds = list(dict.fromkeys(int(s) for s in args.seeds.split(",")))
    if len(seeds)<2 or not k_candidates or any(k<2 or k>=len(values) for k in k_candidates):
        raise ValueError("Invalid k grid or too few seeds")
    ks = cluster_stability(values,k_candidates,seeds,args.silhouette_sample)
    visual = umap_seed_stability(values,seeds[:2],args.umap_neighbors,args.umap_min_dist)
    return {
        "schema_version":1,
        "status":"completed_exploratory_kmeans_umap_stability",
        "n_original":len(frame),"sample_n":len(ix),
        "sample_seed":args.seed,
        "sample_stratum_sizes": {k:int(v) for k,v in strata.items()},
        "embedding_provenance":provenance,
        "stability":ks,
        "umap":visual,
        "limitations":[
            "The KMeans clustering here is an alternative sensitivity analysis, NOT a replay of the original topic-extraction algorithm.",
            "UMAP two-dimensional distances, hulls and areas must not be used as original-space overlap evidence.",
            "The chosen k still requires a scientifically meaningful topic interpretability analysis.",
            "The sampling/embedding scheme is the original 512-token limited E5; fulltext perturbations need a separate computation.",
            "No per-thesis coordinates, raw document data or classification labels are published.",
        ]
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root",type=Path,required=True)
    p.add_argument("--sample-size",type=int,default=1500)
    p.add_argument("--silhouette-sample",type=int,default=600)
    p.add_argument("--k-values",default="50,75,100")
    p.add_argument("--seeds",default="42,123,456")
    p.add_argument("--seed",type=int,default=42)
    p.add_argument("--umap-neighbors",type=int,default=15)
    p.add_argument("--umap-min-dist",type=float,default=.1)
    p.add_argument("--output",type=Path,
                   default=Path("docs/audits/reviewer_stage3_stability.json"))
    a = p.parse_args()
    if a.sample_size > 3500 or a.umap_neighbors < 5:
        p.error("This stage is deliberately limited to 3500 samples")
    start=time.perf_counter()
    result = analyze(a)
    result["elapsed_seconds"] = round(time.perf_counter()-start,3)
    dest = write_public(result,a.output,Path(__file__).resolve().parent.parent)
    print("Stability report:",dest)
    print("This is a model sensitivity analysis, not SDG/PDOT classification accuracy.")


if __name__ == "__main__":
    main()
