#!/usr/bin/env python3
"""Why did the 7830-thesis ODS/PDOT/needs labels move under whole-text E5?

Privacy-preserving, CPU-only diagnostic. Uses original source dictionary order,
frozen fulltext checkpoint content-token/window counts, and already generated
PRIVATE per-thesis reclassification score matrices. No PDF reads, no GPU.

Exports ONLY group statistics: top *nontrivial* class transitions (minimum
25 documents), prevalence/concentration, confidence margins and drift across
equal-sized quartiles of original document token count. No row IDs, text, raw
embeddings, per-thesis scores or sample identifiers.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from reviewer_full_corpus_two_mig import (
    EXPECTED_CHUNKS, EXPECTED_ROWS, EXPECTED_TOKENS,
    checkpoint_indices, count_worker_documents, load_verified_checkpoint,
)
from reviewer_legacy_alignment_replay import freeze_original_dicts
from reviewer_shared import sha256_file, write_public

N = EXPECTED_ROWS
DOMAINS = ("ods", "pdot", "need")
MIN_FLOW = 25


def load_verified_length_census(run_dir, source_root):
    """Recheck ALL frozen checkpoint fingerprints and lengths/positions."""
    manifest_file = run_dir / "run_parameters_PRIVATE.json"
    if not manifest_file.exists():
        raise FileNotFoundError("Frozen fulltext manifest missing")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    block_size = manifest["documents_per_checkpoint"]
    if manifest["population_rows"] != N or not 1 <= block_size <= 128:
        raise ValueError("Unexpected checkpoint manifest layout")
    original = source_root / "data/processed/04_corpus_clean.parquet"
    if sha256_file(original) != manifest["original_04_parquet_sha256"]:
        raise ValueError("Original source corpus fingerprint changed")
    fingerprint = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode()
    ).hexdigest()
    counts = np.zeros(N, dtype=np.int64)
    windows = np.zeros(N, dtype=np.int64)
    seen = np.zeros(N, dtype=bool)
    blocks = 0
    for slot in (0, 1):
        total = count_worker_documents(slot, N)
        for batch in range(math.ceil(total / block_size)):
            path = run_dir / f"mig_slot{slot}" / f"batch_{batch:04d}.npz"
            expected = checkpoint_indices(slot, batch, block_size, N)
            load_verified_checkpoint(path, expected, fingerprint)
            with np.load(path, allow_pickle=False) as z:
                positions = np.asarray(z["row_indices"], dtype=np.int64)
                token = np.asarray(z["content_token_counts"], dtype=np.int64)
                chunk = np.asarray(z["window_counts"], dtype=np.int64)
            if np.any(seen[positions]):
                raise ValueError("Duplicate thesis in verified checkpoint census")
            seen[positions] = True
            counts[positions] = token
            windows[positions] = chunk
            blocks += 1
    if (
        blocks != 490 or not np.all(seen) or
        counts.sum() != EXPECTED_TOKENS or
        windows.sum() != EXPECTED_CHUNKS or
        np.any(counts < 1) or np.any(windows < 1)
    ):
        raise ValueError("Fulltext token/window census or row coverage mismatch")
    return counts, windows, blocks, fingerprint


def concentrations(predictions, full_labels):
    values = np.asarray(predictions, dtype=str)
    counts = np.asarray([np.count_nonzero(values == k) for k in full_labels], dtype=np.int64)
    if counts.sum() != len(values) or len(values) == 0:
        raise ValueError("Unexpected class/category mismatch")
    fractions = counts / len(values)
    nonzero = fractions[fractions > 0]
    h = float(-(nonzero * np.log(nonzero)).sum())
    return {
        "largest_category": full_labels[int(np.argmax(counts))],
        "largest_category_n": int(counts.max()),
        "largest_category_share": round(float(fractions.max()), 6),
        "normalized_shannon_entropy": round(h / math.log(len(full_labels)), 6),
        "effective_number_categories_exp_entropy": round(float(np.exp(h)), 6),
        "herfindahl_concentration": round(float(np.sum(fractions ** 2)), 6),
    }


def js_divergence(p, q):
    """Jensen-Shannon divergence in bits; symmetric, bounded in [0,1]."""
    p, q = np.asarray(p, dtype=np.float64), np.asarray(q, dtype=np.float64)
    if p.shape != q.shape or p.ndim != 1 or p.sum() <= 0 or q.sum() <= 0:
        raise ValueError("Invalid class distributions")
    p /= p.sum()
    q /= q.sum()
    m = (p + q) / 2
    def kl(x):
        mask = x > 0
        return float(np.sum(x[mask] * np.log2(x[mask] / m[mask])))
    return round((kl(p) + kl(q)) / 2, 6)


def transitions(old, current, min_flow=MIN_FLOW, cap=15):
    """Privacy-controlled nontrivial flows; suppress any cell below threshold."""
    if len(old) != len(current):
        raise ValueError("Unaligned labels")
    counts = Counter(zip(old.tolist(), current.tolist()))
    changed = [
        (a, b, n) for (a, b), n in counts.items() if a != b
    ]
    shown = sorted(
        (a, b, n) for a, b, n in changed if n >= min_flow
    )
    shown.sort(key=lambda x: (-x[2], x[0], x[1]))
    shown = shown[:cap]
    included = sum(n for _, _, n in shown)
    changed_total = int(np.sum(old != current))
    return {
        "min_reportable_cell_n": min_flow,
        "top_changed_label_flows": [
            {"from_original": a, "to_fulltext_raw": b, "n": n}
            for a, b, n in shown
        ],
        "other_changed_label_flows_combined_n": changed_total - included,
        "total_changed_top1": changed_total,
        "interpretation": (
            "Transitions compare two UNSUPERVISED model predictions. "
            "No accuracy, precision or causal correction inferred."
        ),
    }


def length_quartiles(token_counts):
    """Four nearly equal-N cohorts, stable by content token count, no ID export."""
    token_counts = np.asarray(token_counts, dtype=np.int64)
    if token_counts.shape != (N,) or np.any(token_counts <= 0):
        raise ValueError("Unexpected full-corpus token counts")
    ranking = np.argsort(token_counts, kind="stable")
    groups = np.array_split(ranking, 4)
    return {f"Q{i+1}": np.asarray(group) for i, group in enumerate(groups)}


def diagnose(domain, names, original, variants, token_counts, windows, quartiles):
    """Aggregate statistics only; never write prediction arrays to public JSON."""
    labelset = set(names)
    if len(names) not in (6, 10, 17):
        raise ValueError("Unexpected taxonomy size")
    if original.shape != (N,) or not set(original).issubset(labelset):
        raise ValueError("Original classification not consistent with taxonomy")
    labels = {}
    metrics = {}
    for variant, scores in variants.items():
        s = np.asarray(scores, dtype=np.float32)
        if s.shape != (N, len(names)) or not np.isfinite(s).all():
            raise ValueError(f"{domain} {variant} invalid private score matrix")
        order = np.argsort(-s, axis=1, kind="stable")
        labels[variant] = np.asarray(names)[order[:, 0]]
        margins = s[np.arange(N), order[:, 0]] - s[np.arange(N), order[:, 1]]
        metrics[variant] = {
            "concentration": concentrations(labels[variant], names),
            "median_top1_top2_margin": round(float(np.median(margins)), 6),
            "margin_le_0p01_n": int(np.count_nonzero(margins <= .01)),
        }
        if variant == "fulltext_raw":
            metrics[variant]["margin_for_largest_category_only"] = {
                "n": int(np.count_nonzero(labels[variant] ==
                                          metrics[variant]["concentration"]["largest_category"])),
                "median": round(float(np.median(margins[
                    labels[variant] == metrics[variant]["concentration"]["largest_category"]
                ])), 6)
            }

    original_conc = concentrations(original, names)
    raw = labels["fulltext_raw"]
    cent = labels["fulltext_centered"]
    orgfreq = [int(np.count_nonzero(original == x)) for x in names]
    newfreq = [int(np.count_nonzero(raw == x)) for x in names]
    cohort_report = []
    for name, pos in quartiles.items():
        cohort_report.append({
            "length_group": name,
            "n": len(pos),
            "content_tokens_min": int(token_counts[pos].min()),
            "content_tokens_median": int(np.median(token_counts[pos])),
            "content_tokens_max": int(token_counts[pos].max()),
            "window_count_median": int(np.median(windows[pos])),
            "historical_to_fulltext_raw_changed_n": int(np.sum(original[pos] != raw[pos])),
            "historical_to_fulltext_raw_changed_share":
                round(float(np.mean(original[pos] != raw[pos])), 6),
            "fulltext_raw_to_centered_changed_share":
                round(float(np.mean(raw[pos] != cent[pos])), 6),
            "fulltext_raw_dominant_category_share":
                round(float(np.mean(raw[pos] == metrics["fulltext_raw"]["concentration"]["largest_category"])), 6),
        })
    return {
        "n": N,
        "historical_concentration": original_conc,
        "representations": metrics,
        "original_vs_fulltext_raw_jensen_shannon_divergence_bits":
            js_divergence(orgfreq, newfreq),
        "top_aggregate_transitions": transitions(original, raw),
        "by_original_document_token_quartile": cohort_report,
        "notes": [
            "Largest category is computed independently for each representation.",
            "Higher entropy is not a classification quality measure.",
            "Quartile differences are observational and may reflect discipline, formatting or lengths, not causal effects.",
            "A broad territorial label can dominate cosine ranking without implying actual policy alignment.",
            "No document-level scores, identifiers or texts are exported.",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root", type=Path, required=True)
    p.add_argument("--private-scores", type=Path, default=Path(
        "data/revision_private/reviewer_fulltext_reclassification/reclassification_all_7830_PRIVATE.npz"
    ))
    p.add_argument("--private-run", type=Path, default=Path(
        "data/revision_private/fulltext_e5_large_v1"
    ))
    p.add_argument("--source-inventory", type=Path, default=Path(
        "data/revision_private/descriptor_inventory/descriptor_source_candidates_PRIVATE.json"
    ))
    p.add_argument("--reclassification-report", type=Path, default=Path(
        "docs/audits/reviewer_fulltext_reclassification_v1.json"
    ))
    p.add_argument("--output", type=Path, default=Path(
        "docs/audits/reviewer_fulltext_drift_diagnostic.json"
    ))
    a = p.parse_args()
    workspace = Path(__file__).resolve().parent.parent
    private_root = (workspace / "data").resolve()
    for item in (a.private_scores, a.private_run, a.source_inventory):
        if not item.expanduser().resolve().is_relative_to(private_root):
            raise ValueError("All private inputs must be under ignored revision/data/")
    if a.output.expanduser().resolve().exists():
        raise FileExistsError("Existing aggregate output: do not overwrite")
    root = a.project_root.expanduser().resolve()
    source = json.loads(a.source_inventory.read_text(encoding="utf-8"))
    tax, src_sha = freeze_original_dicts(source, root)
    gate = json.loads(a.reclassification_report.read_text(encoding="utf-8"))
    if gate.get("status") != "fulltext_and_centered_ods_pdot_needs_reclassification_exploratory_not_human_validated":
        raise ValueError("Required fulltext reclassification has not completed")
    if gate.get("descriptor_source_sha256") != src_sha or gate.get("n_theses") != N:
        raise ValueError("Reclassification provenance mismatch")
    token_counts, window_counts, blocks, fingerprint = load_verified_length_census(
        a.private_run.resolve(), root
    )
    cohorts = length_quartiles(token_counts)
    data = pd.read_parquet(root / "data/processed/07_alignment_pdot_ods_needs.parquet",
                           columns=["handle_id"] + [f"{domain}_top1" for domain in DOMAINS])
    if len(data) != N or data["handle_id"].isna().any() or data["handle_id"].duplicated().any():
        raise ValueError("Original 07 source row alignment failed")
    outputs = {}
    with np.load(a.private_scores, allow_pickle=False) as frozen:
        for domain in DOMAINS:
            names = list(tax[domain])
            variant_scores = {}
            for version in ("legacy_raw", "legacy_centered", "fulltext_raw", "fulltext_centered"):
                key = f"{domain}_{version}_scores"
                if key not in frozen:
                    raise ValueError(f"Missing frozen private score {key}")
                variant_scores[version] = frozen[key]
            outputs[domain] = diagnose(
                domain, names, data[f"{domain}_top1"].astype(str).to_numpy(),
                variant_scores, token_counts, window_counts, cohorts
            )
            expected_changes = gate["domains"][domain]["representations"]["fulltext_raw"]["top1_changed_against_original_n"]
            if outputs[domain]["top_aggregate_transitions"]["total_changed_top1"] != expected_changes:
                raise ValueError(f"Population flip count mismatch for {domain}")
    result = {
        "schema_version": 1,
        "status": "fulltext_class_shift_length_and_concentration_diagnostic_unvalidated",
        "n_population": N,
        "fulltext_verified_checkpoint_blocks": blocks,
        "fulltext_frozen_checkpoint_manifest_fingerprint": fingerprint,
        "token_census": {"content_tokens": int(token_counts.sum()),
                         "windows": int(window_counts.sum())},
        "source_dictionary_sha256": src_sha,
        "private_scores_sha256": sha256_file(a.private_scores),
        "taxonomies": outputs,
        "expert_accuracy_evaluated": False,
        "caveats": [
            "Length and label shift association is descriptive, not causal.",
            "Long fulltexts may contain references, appendices, institutional templates and repeated academic prose; structural boundary quality is not yet independently validated.",
            "Scores and historical labels are unsupervised affinities, not demonstrated substantive SDG or PDOT impact.",
            "Transitions below the reporting threshold are combined; no per-thesis data are released.",
        ],
    }
    destination = write_public(result, a.output, workspace)
    print("Fulltext content-length drift and dominance audit:", destination)
    for domain, entry in outputs.items():
        raw = entry["representations"]["fulltext_raw"]["concentration"]
        print(domain, "largest category:", raw["largest_category"],
              "count:", raw["largest_category_n"],
              "normalized entropy:", raw["normalized_shannon_entropy"])
        print("  flip rates by token quartile:", [
            x["historical_to_fulltext_raw_changed_share"]
            for x in entry["by_original_document_token_quartile"]
        ])
    print("No GPU, no source text output, no private records exported.")


if __name__ == "__main__":
    main()
