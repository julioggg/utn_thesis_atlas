#!/usr/bin/env python3
"""Descriptive A/B validation of four ALREADY FROZEN E5 score representations.

The original 120 random theses are reserved for descriptive held-out
assessment, NOT for selecting a winning classifier or its thresholds.
The 330 targeted-enrichment cases support class-conditional diagnostics.
The 450 pooled estimate is not representative of population proportions.

This does NOT create a human consensus, tune abstention, assert impact,
or re-encode embeddings. All per-class results remain private in CEDIA.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd

from audit_annotation_progress import inspect_files
from reviewer_fulltext_reclassification import VARIANTS
from reviewer_human_validation_metrics import (
    PDOT_ID, NONE, labels_from_coder, metrics, output_metrics
)
from reviewer_shared import (
    normalize_codes, private_output, sha256_file, write_public
)

DOMAINS=("ods","pdot")
CLASSES={
    "ods":[f"ODS {i}" for i in range(1,18)]+[NONE],
    "pdot":[f"PDOT {i}" for i in range(1,7)]+[NONE],
}
SOURCE_KEY={
    "ods":"ods",
    "pdot":"pdot",
}


def validate_fulltext_source(report):
    if report.get("status") != (
        "fulltext_and_centered_ods_pdot_needs_reclassification_"
        "exploratory_not_human_validated"
    ):
        raise ValueError("Unexpected original/fulltext reclassification report status")
    if report.get("n_theses")!=7830 or set(report.get("variants",[]))!=set(VARIANTS):
        raise ValueError("Reclassification census/variant roster mismatch")
    if report.get("source_alignment_verified",{})!={} and not all(
        report["source_alignment_verified"].values()
    ):
        raise ValueError("Historical source alignment not verified")
    if not report.get("descriptor_source_sha256"):
        raise ValueError("Historical descriptor provenance unavailable")
    return True


def evaluate_scores_for_coder(scores,source_names,annotation,indices,strata):
    """Return per-stratum metrics without selecting models by held-out F1."""
    if scores.shape[0]!=7830 or len(set(source_names))!=scores.shape[1]:
        raise ValueError("Invalid frozen 7830-case score matrix/category count")
    if not np.isfinite(scores).all():
        raise ValueError("Nonfinite score matrix")
    if len(indices)!=450 or len(set(indices.tolist()))!=450:
        raise ValueError("Expected 450 frozen sample indices")
    names=np.asarray(source_names,dtype=str)
    prediction=names[np.argmax(scores[indices],axis=1)]
    truth=labels_from_coder(annotation,"ods" if names[0].startswith("ODS ") else "pdot")
    if len(truth)!=450:
        raise ValueError("Wrong truth roster length")
    masks={
        "random_120":strata=="population_random",
        "enriched_330":strata=="targeted_enrichment",
        "pooled_450_descriptive_only":np.ones(450,dtype=bool),
    }
    if int(masks["random_120"].sum())!=120 or int(masks["enriched_330"].sum())!=330:
        raise ValueError("Unexpected 120/330 frozen split")
    return {group:metrics(truth[mask],prediction[mask],list(names)+[NONE])
            for group,mask in masks.items()}


def analyze(args):
    workspace=Path(__file__).resolve().parent.parent
    private=args.private_dir.expanduser().resolve()
    if not private.is_relative_to((workspace/"data/revision_private").resolve()):
        raise ValueError("A/B coding must reside in ignored private data")
    progress=inspect_files(private)
    if not progress["all_annotations_finished"]:
        raise ValueError("A/B annotation roster is incomplete")
    report_path=args.reclassification_report.expanduser().resolve()
    npz_path=args.reclassification_scores.expanduser().resolve()
    if not npz_path.is_relative_to((workspace/"data/revision_private").resolve()):
        raise ValueError("Reclassification scores must stay in private data")
    if not npz_path.is_file() or not report_path.is_file():
        raise FileNotFoundError("Frozen 7830 original/fulltext reclassification must exist first")
    source=json.loads(report_path.read_text(encoding="utf-8"))
    validate_fulltext_source(source)

    root=args.project_root.expanduser().resolve()
    corpus=pd.read_parquet(root/"data/processed/07_alignment_pdot_ods_needs.parquet",
                           columns=["handle_id","ods_top1","pdot_top1"])
    if len(corpus)!=7830:
        raise ValueError("Historical corpus size changed")
    master=pd.read_csv(private/"sample_master_private.csv",dtype=str,keep_default_na=False)
    if len(master)!=450 or master["study_id"].duplicated().any():
        raise ValueError("Invalid frozen 450 study roster")
    indices=master["source_row_index"].astype(int).to_numpy()
    if indices.min()<0 or indices.max()>=7830 or len(set(indices.tolist()))!=450:
        raise ValueError("Frozen indices invalid")
    if not np.array_equal(
        corpus["handle_id"].iloc[indices].astype(str).to_numpy(),
        master["handle_id"].to_numpy()
    ):
        raise ValueError("Original corpus and 450 human sample handle alignment failed")
    strata=master["selection_stratum"].astype(str).to_numpy()
    annot={}
    for coder in ("A","B"):
        rows=pd.read_csv(private/f"coder_{coder}_private.csv",dtype=str,
                         keep_default_na=False)
        if rows["study_id"].duplicated().any() or set(rows["study_id"])!=set(master["study_id"]):
            raise ValueError("Coder study IDs do not match frozen master")
        rows=rows.set_index("study_id").reindex(master["study_id"]).reset_index()
        if not np.array_equal(
            rows["private_source_handle"].str.lstrip("'").to_numpy(),
            master["handle_id"].to_numpy()
        ):
            raise ValueError("Coder handles do not match frozen master")
        annot[coder]=rows

    target=args.private_metrics_dir.expanduser().resolve()
    if not target.is_relative_to((workspace/"data/revision_private").resolve()):
        raise ValueError("Per-class outputs must remain private")
    expected=[target/f"{domain}_{variant}_vs_{coder}_{split}_perclass_PRIVATE.csv"
              for domain in DOMAINS for variant in VARIANTS
              for coder in ("A","B")
              for split in ("random_120","enriched_330","pooled_450_descriptive_only")]
    if any(x.exists() for x in expected):
        raise FileExistsError("Private per-class metrics already exist; no silent overwrite")
    aggregate=args.output.expanduser().resolve()
    if aggregate.exists():
        raise FileExistsError("Aggregate result exists; refuse overwrite")

    result={
        "schema_version":1,
        "status":"four_frozen_E5_representations_vs_two_independent_coders_not_adjudicated",
        "population_n":7830,"human_roster_n":450,
        "random_heldout_n":120,"enriched_n":330,
        "score_matrix_sha256":sha256_file(npz_path),
        "reclassification_report_sha256":sha256_file(report_path),
        "descriptor_source_sha256":source["descriptor_source_sha256"],
        "same_frozen_cases_across_variants":True,
        "not_preferentially_selected_by_heldout_performance":True,
        "ground_truth_status":"human_A_B_separate_no_adjudicated_consensus",
        "comparisons":{}
    }
    with np.load(npz_path,allow_pickle=False) as matrices:
        keys=set(matrices.files)
        if any(f"{domain}_{variant}_scores" not in keys
               for domain in DOMAINS for variant in VARIANTS):
            raise ValueError("One or more frozen representation matrices missing")
        for domain in DOMAINS:
            per_domain={}
            source_labels=(
                normalize_codes(corpus["ods_top1"])
                if domain=="ods" else
                [PDOT_ID.get(v,"[invalid]") for v in corpus["pdot_top1"]]
            )
            allowed=set(CLASSES[domain])-{NONE}
            if any(x not in allowed for x in source_labels):
                raise ValueError("Unrecognized archived ODS/PDOT category")
            for variant in VARIANTS:
                scores=np.asarray(matrices[f"{domain}_{variant}_scores"],
                                  dtype=np.float32)
                if scores.shape!=(7830,len(allowed)) or not np.isfinite(scores).all():
                    raise ValueError("Bad frozen ODS/PDOT score matrix")
                # Descriptors follow the exact archived source-dictionary order.
                # ODS primary IDs are read from taxonomy source labels, NOT
                # derived by reordering class counts.
                names=list(source["domains"][domain]["representations"]
                           ["legacy_raw"]["top1_category_counts_candidate_unvalidated"].keys())
                if domain=="ods":
                    canonical=list(normalize_codes(names))
                else:
                    canonical=[PDOT_ID.get(k,"[invalid]") for k in names]
                if len(canonical)!=len(allowed) or set(canonical)!=allowed:
                    raise ValueError("Frozen descriptor category IDs do not match human codebook")
                top=[canonical[i] for i in np.argmax(scores,axis=1)]
                if variant=="legacy_raw":
                    if top!=source_labels:
                        raise ValueError(
                            "Legacy raw source order does not reproduce original "
                            "ODS/PDOT top1; refuse to score potentially misaligned labels"
                        )
                class_matrix=scores
                items={}
                for coder in ("A","B"):
                    values=evaluate_scores_for_coder(
                        class_matrix,canonical,annot[coder],indices,strata
                    )
                    for split,metric in values.items():
                        save_name=f"{domain}_{variant}_vs_{coder}_{split}"
                        items.setdefault(coder,{})[split]=output_metrics(
                            metric,private_output(target,workspace),save_name
                        )
                per_domain[variant]=items
            result["comparisons"][domain]=per_domain
    result["limitations"]=[
        "A/B are two reference coders, not a committee-adjudicated truth.",
        "The 120 random theses are too few for precise estimates of rare SDG and PDOT classes; report per-class supports.",
        "The 330 targeted cases do not support unbiased population-level accuracy estimates.",
        "These four analyses are planned descriptive sensitivity tests. Do not pick a winner on 120 held-out labels.",
        "Forced top-1 cannot predict no-alignment and is not calibrated for abstention.",
        "No use of committee attribution workbook until signed provenance and PDOT codebook are approved.",
        "Descriptor provenance is historical source-code lineage; official PDOT axes may differ from analytic labels.",
        "No positive SDG impact follows from embedding thematic proximity."
    ]
    # Validate the exact nested schema BEFORE saving any report.
    for domain in DOMAINS:
        if set(result["comparisons"].get(domain, {})) != set(VARIANTS):
            raise ValueError("Four-variant result has invalid domain keys")
        for variant in VARIANTS:
            by_coder = result["comparisons"][domain][variant]
            if set(by_coder) != {"A", "B"}:
                raise ValueError("Expected independent A and B results per variant")
            for coder in ("A", "B"):
                if set(by_coder[coder]) != {
                    "random_120", "enriched_330", "pooled_450_descriptive_only"
                }:
                    raise ValueError("Expected frozen 120/330/450 reports per coder")
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root",type=Path,required=True)
    parser.add_argument("--private-dir",type=Path,default=Path(
        "data/revision_private/validation"))
    parser.add_argument("--reclassification-scores",type=Path,default=Path(
        "data/revision_private/reviewer_fulltext_reclassification/reclassification_all_7830_PRIVATE.npz"))
    parser.add_argument("--reclassification-report",type=Path,default=Path(
        "docs/audits/reviewer_fulltext_reclassification_v1.json"))
    parser.add_argument("--private-metrics-dir",type=Path,default=Path(
        "data/revision_private/four_e5_variant_coder_metrics_v2"))
    parser.add_argument("--output",type=Path,default=Path(
        "docs/audits/reviewer_four_e5_variant_dual_coder_metrics_v2.json"))
    args=parser.parse_args()
    report=analyze(args)
    out=write_public(report,args.output,Path(__file__).resolve().parent.parent)
    print("FOUR E5 VARIANTS vs A/B independently:",out)
    for domain,variants in report["comparisons"].items():
        print("\n",domain.upper())
        for variant,by_coder in variants.items():
            cells=[]
            for coder in ("A","B"):
                r=by_coder[coder]["random_120"]
                cells.append(f"{coder}: acc={r['accuracy']:.4f}, macroF1={r['macro_f1_present_or_predicted_classes']:.4f}")
            print(variant," | ".join(cells))
    print("No committee ground truth and no model selection inferred.")
    print("Private per-class supports, confusions and F1:",args.private_metrics_dir)


if __name__=="__main__":
    main()
