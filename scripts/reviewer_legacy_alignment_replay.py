#!/usr/bin/env python3
"""Source-grounded replay of the original thesis atlas ODS/PDOT/NEEDS alignment.

This reproduces the observed code in utn_atlas_pipeline.py:
  names = list(tax)
  desc = ["passage: " + n + ". " + tax[n] for n in names]
  t_emb = model.encode(desc, normalize_embeddings=True, ...)
  sims = old_document_vectors @ t_emb.T
  order = np.argsort(-sims, axis=1)
  store top-1, top-2, top-3 names and cosine scores

The original program used SentenceTransformer; this diagnostic uses a frozen
E5 transformer model + equivalent attention-mask mean pooling, and *measures*
whether it actually reproduces the archived classification. Any discrepancy
is reported; nothing is silently called 'verified'.

NO original model script execution, NO PDF re-encoding, NO modifications of
legacy data, NO public row-level export. Source descriptions and their 33
descriptor vectors are saved only in ignored revision/data/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from audit_embedding_comparison import check_row_alignment
from reviewer_compare_fulltext_legacy import check_fulltext_report
from reviewer_shared import private_output, read_original_embeddings, sha256_file, summary, write_public

TAXONOMY = {"pdot": ("PDOT", 6), "ods": ("ODS", 17), "need": ("NEEDS", 10)}
MODEL = "intfloat/multilingual-e5-large"
SCRIPT = "utn_atlas_pipeline.py"


def freeze_original_dicts(inventory, original_root):
    """Only select exact original source variable, not PDOT_MAP or V2 guesses."""
    if inventory.get("status") != "unverified_ast_descriptor_candidates":
        raise ValueError("Invalid frozen AST inventory")
    matches = [
        s for s in inventory["candidate_source_inventory"]
        if s["relative_path"] == SCRIPT
    ]
    if len(matches) != 1:
        raise ValueError("Original classification source hash absent/ambiguous")
    source = original_root / SCRIPT
    if sha256_file(source) != matches[0]["sha256"]:
        raise ValueError("Original classification source differs from inventory hash")
    extracted = {}
    for domain, (var, count) in TAXONOMY.items():
        c = [
            x for x in inventory["literal_candidates"]
            if x.get("relative_source_path") == SCRIPT
            and x.get("variable_name") == var
        ]
        if len(c) != 1 or not isinstance(c[0]["candidate_literal"], dict):
            raise ValueError(f"Cannot extract source {var} literal safely")
        descriptions = c[0]["candidate_literal"]
        if len(descriptions) != count:
            raise ValueError(f"Unexpected {var} category count")
        if any(not isinstance(k, str) or not isinstance(v, str)
               or not k.strip() or not v.strip()
               for k, v in descriptions.items()):
            raise ValueError(f"Empty or invalid {var} key/value")
        extracted[domain] = descriptions
    return extracted, matches[0]["sha256"]


def source_matches_archived_labels(frame, taxonomies):
    """All three archived ranks must be source-key members, not guessed labels."""
    results = {}
    for domain, values in taxonomies.items():
        keys = set(values)
        for rank in range(1, 4):
            col = f"{domain}_top{rank}"
            if col not in frame:
                raise ValueError(f"Original archive missing {col}")
            if frame[col].isna().any() or not set(frame[col].astype(str)).issubset(keys):
                raise ValueError(f"Original {col} contains values not in source {domain} dictionary")
            score = f"{col}_score"
            if score not in frame:
                raise ValueError(f"Original archive missing {score}")
            scores = frame[score].to_numpy(dtype=np.float64)
            if not np.isfinite(scores).all():
                raise ValueError(f"Non-finite historical score column: {score}")
        results[domain] = {
            "source_categories": len(keys),
            "archived_top1_categories": int(frame[f"{domain}_top1"].nunique()),
            "archived_top3_category_membership_valid": True,
        }
    return results


def prepare_sentences(taxonomy):
    names = list(taxonomy)
    descriptions = ["passage: " + n + ". " + taxonomy[n] for n in names]
    return names, descriptions


def encode_descriptors(sentences, model_revision, device, batch_size):
    import torch
    from transformers import AutoTokenizer, AutoModel
    use_cuda = device == "cuda" or (device == "auto" and torch.cuda.is_available())
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("Requested CUDA device not visible")
    actual = "cuda" if use_cuda else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL, revision=model_revision, local_files_only=True, use_fast=True
    )
    model = AutoModel.from_pretrained(
        MODEL, revision=model_revision, local_files_only=True,
        use_safetensors=True, torch_dtype=torch.float32,
    ).to(actual).eval()
    vectors = []
    for start in range(0, len(sentences), batch_size):
        chunk = sentences[start:start + batch_size]
        toks = tokenizer(
            chunk, padding=True, truncation=False, return_tensors="pt"
        )
        if toks["input_ids"].shape[1] > 512:
            raise ValueError("An original descriptor would exceed E5 512-token capacity")
        toks = {key: val.to(actual) for key, val in toks.items()}
        with torch.inference_mode():
            encoded = model(**toks).last_hidden_state.float()
            mask = toks["attention_mask"].unsqueeze(-1)
            means = (encoded * mask).sum(1) / mask.sum(1).clamp(min=1)
            units = torch.nn.functional.normalize(means, p=2, dim=1)
        vectors.append(units.cpu().numpy().astype(np.float32))
    return np.vstack(vectors), actual


def compare_replay(scores, names, archive, domain):
    """Positionally compare top-3 and stored scores for every archived row."""
    order = np.argsort(-scores, axis=1)
    pred = np.asarray(names)[order[:, :3]]
    n = len(archive)
    result = {"n": n, "top1_labels": {}, "ranking": {}}
    for r in range(1, 4):
        archived = archive[f"{domain}_top{r}"].astype(str).to_numpy()
        got = pred[:, r - 1]
        match = got == archived
        pos = scores[np.arange(n), order[:, r - 1]].astype(np.float64)
        expected = archive[f"{domain}_top{r}_score"].to_numpy(dtype=np.float64)
        errors = np.abs(pos - expected)
        result["ranking"][str(r)] = {
            "exact_label_agreement": round(float(np.mean(match)), 8),
            "mismatch_count": int((~match).sum()),
            "absolute_score_error": summary(errors),
            "absolute_score_error_q99": round(float(np.quantile(errors, .99)), 8),
        }
    original_top3 = archive[[f"{domain}_top{r}" for r in range(1, 4)]].astype(str).to_numpy()
    result["unordered_top3_set_agreement"] = round(
        float(np.mean([
            set(p) == set(o) for p, o in zip(pred, original_top3)
        ])), 8
    )
    result["historical_top1_counts_only"] = {
        x: int(np.sum(archive[f"{domain}_top1"].astype(str).to_numpy() == x))
        for x in names
    }
    # Conservative, explicit heuristic; only exact equality is 'exact'.
    # Floating point implementation can differ from the original
    # SentenceTransformer encode call and must be reported honestly.
    first = result["ranking"]["1"]
    result["all_top1_labels_identical"] = first["mismatch_count"] == 0
    result["all_three_ranks_identical"] = all(
        result["ranking"][str(r)]["mismatch_count"] == 0 for r in range(1, 4)
    )
    result["score_reconstruction_candidate_tolerance_1e_minus_3"] = (
        all(
            result["ranking"][str(r)]["absolute_score_error_q99"] < .001
            for r in range(1, 4)
        )
    )
    result["warning"] = (
        "Legacy self-reproduction agreement is NOT classification accuracy "
        "against human-annotated ODS/PDOT ground truth."
    )
    return result


def analyze(args):
    workspace = Path(__file__).resolve().parent.parent
    original = args.project_root.expanduser().resolve()
    private = private_output(args.private_dir, workspace)
    inventory = private.parent / "descriptor_inventory" / "descriptor_source_candidates_PRIVATE.json"
    if not inventory.is_file():
        raise FileNotFoundError("Frozen original AST inventory is required")
    provenance = json.loads(inventory.read_text(encoding="utf-8"))
    dictionaries, source_hash = freeze_original_dicts(provenance, original)
    n, alignment = check_row_alignment(original)
    if n != 7830:
        raise ValueError("Original atlas N != 7830")
    columns = ["handle_id"]
    for domain in TAXONOMY:
        columns.extend(f"{domain}_top{r}" for r in range(1, 4))
        columns.extend(f"{domain}_top{r}_score" for r in range(1, 4))
    frame = pd.read_parquet(
        original / "data/processed/07_alignment_pdot_ods_needs.parquet",
        columns=columns,
    )
    if len(frame) != n or frame["handle_id"].isna().any() or frame["handle_id"].duplicated().any():
        raise ValueError("Original 07 identifiers missing/duplicated")
    archived = source_matches_archived_labels(frame, dictionaries)
    old, old_alignment = read_original_embeddings(original, n)
    source_report = check_fulltext_report(args.fulltext_report.expanduser().resolve())
    if source_report["model"] != MODEL:
        raise ValueError("Fulltext model identity differs from source classification model")
    frozen_revision = source_report["model_revision_from_cache"]
    if not isinstance(frozen_revision, str) or len(frozen_revision) < 20:
        raise ValueError("Frozen E5 revision SHA absent")
    sentences = []
    slices = {}
    for domain, dictionary in dictionaries.items():
        keys, text = prepare_sentences(dictionary)
        low = len(sentences)
        sentences.extend(text)
        slices[domain] = (keys, slice(low, len(sentences)))
    desc, device = encode_descriptors(
        sentences, frozen_revision, args.device, args.batch_size
    )
    if desc.shape != (33, 1024):
        raise ValueError("Wrong descriptor embedding size")
    vectors = np.asarray(old, dtype=np.float32)
    if not np.isfinite(vectors).all():
        raise ValueError("Non-finite legacy document embedding")
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    if np.any(norms < 1e-8):
        raise ValueError("Zero-norm legacy embedding")
    vectors = vectors / norms
    domains = {}
    private_arrays = {}
    for domain, (names, positions) in slices.items():
        sub_desc = desc[positions]
        score = (vectors @ sub_desc.T).astype(np.float32)
        domains[domain] = compare_replay(score, names, frame, domain)
        domains[domain]["archived_taxonomy"] = archived[domain]
        private_arrays[f"{domain}_descriptor_embeddings"] = sub_desc
        private_arrays[f"{domain}_legacy_scores"] = score
    target = private / "historical_replay_descriptor_vectors_and_scores_PRIVATE.npz"
    if target.exists():
        raise FileExistsError("Replay private matrices already exist; do not overwrite")
    np.savez_compressed(target, **private_arrays)
    report = {
        "schema_version": 1,
        "status": "historical_original_alignment_replayed_candidate",
        "n_corpus_rows": n,
        "n_original_descriptor_sentences": len(sentences),
        "source_file": SCRIPT,
        "source_file_sha256": source_hash,
        "source_inventory_sha256": sha256_file(inventory),
        "original_07_handle_order_verified": alignment,
        "original_05_alignment_verified": old_alignment,
        "reference_fulltext_model_revision": frozen_revision,
        "model": MODEL,
        "descriptor_encoding": {
            "prefix": "passage: ",
            "sentence_construction": "passage: {original_dictionary_key}. {original_dictionary_value}",
            "method": "AutoModel last_hidden_state attention-mask mean pooling and L2 normalization",
            "original_method": "SentenceTransformer model.encode normalize_embeddings=True",
            "device": device, "dtype": "float32",
            "important": "Confirm replay empirically; frozen fulltext model revision does not alone prove legacy model revision matched.",
        },
        "domains": domains,
        "original_source_lineage": {
            "PDOT": "utn_atlas_pipeline.py step_alignment() uses PDOT at line 481",
            "ODS": "utn_atlas_pipeline.py step_alignment() uses ODS at line 482",
            "NEEDS": "utn_atlas_pipeline.py step_alignment() uses NEEDS at line 483",
            "PDOT_MAP": "utn_atlas_q1_extras.py references pdot_top for downstream mapping; not used in original step_alignment()",
        },
        "official_pdot_edition_verified": False,
        "local_needs_policy_provenance_verified": False,
        "human_gold_labels_available": False,
        "next_step": "Only if historical scores reproduce, use SAME descriptors for fulltext classification and mean-centering sensitivity; do not label as expert validation.",
        "privacy": "Only aggregate diagnostic is public-candidate; descriptor text, vectors, per-thesis scores and labels stay in ignored CEDIA data.",
    }
    output = write_public(report, args.output, workspace)
    print("Legacy classifier replay:", output)
    for domain, result in domains.items():
        print(domain, "top1 agreement:", result["ranking"]["1"]["exact_label_agreement"],
              "top3 set:", result["unordered_top3_set_agreement"],
              "p99 score error:", result["ranking"]["1"]["absolute_score_error_q99"])
    print("Private frozen descriptor vectors:", target)
    print("Archive fidelity does not establish human SDG/PDOT classifier accuracy")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root", type=Path, required=True)
    p.add_argument("--fulltext-report", type=Path, default=Path(
        "docs/audits/fulltext_e5_large_full_corpus_v1.json"
    ))
    p.add_argument("--private-dir", type=Path, default=Path(
        "data/revision_private/reviewer_alignment_replay"
    ))
    p.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--output", type=Path, default=Path(
        "docs/audits/reviewer_legacy_alignment_replay.json"
    ))
    args = p.parse_args()
    if not 1 <= args.batch_size <= 16:
        p.error("Batch size must be 1..16")
    analyze(args)


if __name__ == "__main__":
    main()
