#!/usr/bin/env python3
"""Exploratory paired comparison: historical-source TF-IDF vs frozen E5 pipelines.

Reads previously computed TF-IDF and E5 score matrices on CEDIA only. Exactly
120 frozen probability-sampled theses; source-identity, descriptor taxonomy,
and published aggregate accuracy rechecked before any new aggregate report.

No human annotation, model scores, or private adjudication is modified.
All output is aggregate (delta accuracy, paired bootstrap CI, unadjusted exact
McNemar, macro F1); no handles/predictions are exported publicly.

No prospective holdout claim: these 120 theses have already been evaluated
across E5 alternatives; lexical comparison is retrospective and exploratory.
The TF-IDF pipeline uses historical analysis_text; fulltext E5 uses whole
theses, so differences are BETWEEN PIPELINES, not isolated encoder effects.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from reviewer_four_e5_paired_random_uncertainty import paired_stats
from reviewer_human_validation_metrics import PDOT_ID, NONE, labels_from_coder, metrics
from reviewer_shared import normalize_codes, sha256_file, write_public

DOMAINS=("ods","pdot")
CODERS=("A","B")
CANDIDATES=("legacy_raw","fulltext_centered")
N=7830


def key_labels(source_names,domain):
    original=list(source_names)
    if domain=="ods":
        labels=list(normalize_codes(original))
        expected={f"ODS {i}" for i in range(1,18)}
    elif domain=="pdot":
        expected={f"PDOT {i}" for i in range(1,7)}
        # The historical TF-IDF writer stores CANONICAL codes ("PDOT 1"
        # ... "PDOT 6") in pdot_source_names, not original source-text
        # names ("Sistema Físico Ambiental", etc.). In contrast, E5 report
        # dictionaries preserve original names. Both forms are valid, but
        # ambiguous mixed-format taxonomies must be rejected.
        if set(original)==expected:
            labels=list(original)
        elif set(original)==set(PDOT_ID):
            labels=[PDOT_ID[x] for x in original]
        else:
            raise ValueError("Descriptor list does not match human codebook")
    else:
        raise ValueError("Unknown domain")
    if len(labels)!=len(expected) or set(labels)!=expected:
        raise ValueError("Descriptor list does not match human codebook")
    return labels


def paired_summary(truth, lexical_pred, candidate_pred, domain, n_boot, seed):
    a=np.asarray(truth,dtype=str)
    l=np.asarray(lexical_pred,dtype=str)
    c=np.asarray(candidate_pred,dtype=str)
    if a.shape!=(120,) or l.shape!=(120,) or c.shape!=(120,):
        raise ValueError("Paired comparisons require 120 identical cases")
    classes=([f"ODS {i}" for i in range(1,18)] if domain=="ods"
             else [f"PDOT {i}" for i in range(1,7)])+[NONE]
    baseline=metrics(a,l,classes)
    candidate=metrics(a,c,classes)
    paired=paired_stats(l==a,c==a,seed=seed,n_boot=n_boot)
    return {
        "lexical_accuracy":baseline["accuracy"],
        "candidate_accuracy":candidate["accuracy"],
        "lexical_macro_f1_present_or_predicted":baseline[
            "macro_f1_present_or_predicted_classes"],
        "candidate_macro_f1_present_or_predicted":candidate[
            "macro_f1_present_or_predicted_classes"],
        "lexical_no_match_predicted":baseline["no_match_predicted_n"],
        "candidate_no_match_predicted":candidate["no_match_predicted_n"],
        "reference_no_match":baseline["no_match_reference_n"],
        "paired_candidate_minus_lexical":paired,
    }


def analyze(args):
    workspace=Path(__file__).resolve().parent.parent
    privacy=(workspace/"data/revision_private").resolve()
    for path in (args.lexical_scores,args.e5_scores,args.private_dir):
        resolved=path.expanduser().resolve()
        if not resolved.is_relative_to(privacy):
            raise ValueError("Source arrays and annotations must remain private")
        if not resolved.exists():
            raise FileNotFoundError(str(resolved))
    target=args.output.expanduser().resolve()
    if target.exists():
        raise FileExistsError("Aggregate comparison already exists: do not overwrite")

    lexical_report_path=args.lexical_report.expanduser().resolve()
    e5_report_path=args.e5_report.expanduser().resolve()
    taxonomy_path=args.e5_source_report.expanduser().resolve()
    lexical=json.loads(lexical_report_path.read_text(encoding="utf-8"))
    e5=json.loads(e5_report_path.read_text(encoding="utf-8"))
    taxonomy=json.loads(taxonomy_path.read_text(encoding="utf-8"))
    if lexical.get("status")!="historical_source_lexical_TFIDF_ODS_PDOT_AB_validation_exploratory":
        raise ValueError("Wrong lexical baseline")
    if e5.get("status")!="four_frozen_E5_representations_vs_two_independent_coders_not_adjudicated":
        raise ValueError("Wrong four-E5 report")
    if lexical.get("descriptor_source_sha256")!=e5.get("descriptor_source_sha256") or (
        taxonomy.get("descriptor_source_sha256")!=e5.get("descriptor_source_sha256")
    ):
        raise ValueError("Different historical descriptor sources: not comparable")
    if sha256_file(args.e5_scores.expanduser().resolve())!=e5.get("score_matrix_sha256"):
        raise ValueError("Frozen E5 score matrix has different checksum")
    if lexical.get("n_source_theses",lexical.get("original_n"))!=N:
        raise ValueError("TF-IDF corpus count differs")
    if e5.get("population_n")!=N:
        raise ValueError("E5 corpus count differs")

    root=args.project_root.expanduser().resolve()
    archive=pd.read_parquet(root/"data/processed/07_alignment_pdot_ods_needs.parquet",
                            columns=["handle_id","ods_top1","pdot_top1"])
    private=args.private_dir.expanduser().resolve()
    master=pd.read_csv(private/"sample_master_private.csv",dtype=str,keep_default_na=False)
    if len(archive)!=N or len(master)!=450 or master["study_id"].duplicated().any():
        raise ValueError("Invalid frozen corpus or 450-case roster")
    idx=master["source_row_index"].astype(int).to_numpy()
    if idx.min()<0 or idx.max()>=N or len(set(idx.tolist()))!=450:
        raise ValueError("Invalid frozen source indices")
    if not np.array_equal(archive["handle_id"].iloc[idx].astype(str).to_numpy(),
                          master["handle_id"].to_numpy()):
        raise ValueError("Frozen original corpus/document handles differ")
    groups=master["selection_stratum"].to_numpy(dtype=str)
    random=groups=="population_random"
    if int(random.sum())!=120 or int((groups=="targeted_enrichment").sum())!=330:
        raise ValueError("Wrong frozen random/enriched split")
    test_idx=idx[random]
    coders={}
    for coder in CODERS:
        df=pd.read_csv(private/f"coder_{coder}_private.csv",
                       dtype=str,keep_default_na=False)
        if df["study_id"].duplicated().any() or set(df["study_id"])!=set(master["study_id"]):
            raise ValueError("Human A/B roster differs")
        df=df.set_index("study_id").reindex(master["study_id"]).reset_index()
        if not np.array_equal(df["private_source_handle"].str.lstrip("'").to_numpy(),
                              master["handle_id"].to_numpy()):
            raise ValueError("Human A/B handles differ")
        coders[coder]=df

    result={
        "schema_version":1,
        "status":"exploratory_paired_TFIDF_vs_frozen_E5_on_120_random",
        "random_sample_n":120,
        "enriched_n_not_used":330,
        "lexical_report_sha256":sha256_file(lexical_report_path),
        "e5_report_sha256":sha256_file(e5_report_path),
        "lexical_scores_sha256":sha256_file(args.lexical_scores),
        "e5_scores_sha256":sha256_file(args.e5_scores),
        "historical_descriptor_source_sha256":lexical["descriptor_source_sha256"],
        "paired_comparisons_are_retrospective":True,
        "human_references":"A and B separately (not adjudicated consensus)",
        "comparisons":{}
    }
    with np.load(args.lexical_scores,allow_pickle=False) as lfile, np.load(
        args.e5_scores,allow_pickle=False
    ) as efile:
        for domain in DOMAINS:
            lkey=f"{domain}_scores"
            namekey=f"{domain}_source_names"
            if lkey not in lfile or namekey not in lfile:
                raise ValueError("Missing lexical score matrix and original source taxonomy")
            lexical_names=key_labels(lfile[namekey],domain)
            lexical_scores=lfile[lkey]
            if lexical_scores.shape!=(N,len(lexical_names)) or (
                not np.isfinite(lexical_scores).all()
            ):
                raise ValueError("Invalid lexical score matrix")
            lpred=np.asarray(lexical_names)[
                np.argmax(lexical_scores[test_idx],axis=1)
            ]
            e5_names=key_labels(list(taxonomy["domains"][domain]["representations"]
                ["legacy_raw"]["top1_category_counts_candidate_unvalidated"]),domain)
            if lexical_names!=e5_names:
                raise ValueError("Lexical/E5 historical descriptor order differs")
            predictions={}
            for variant in CANDIDATES:
                key=f"{domain}_{variant}_scores"
                if key not in efile:
                    raise ValueError("Missing E5 score matrix "+key)
                matrix=efile[key]
                if matrix.shape!=(N,len(e5_names)) or not np.isfinite(matrix).all():
                    raise ValueError("Invalid frozen E5 score matrix")
                predictions[variant]=np.asarray(e5_names)[
                    np.argmax(matrix[test_idx],axis=1)
                ]
            result["comparisons"][domain]={}
            for coder in CODERS:
                truth=labels_from_coder(coders[coder],domain)[random]
                observed_lexical=metrics(truth,lpred,lexical_names+[NONE])
                baseline_json=lexical["comparisons"][domain]["human_coders"][coder]["random_120"]
                if observed_lexical["accuracy"]!=baseline_json["accuracy"]:
                    raise ValueError("Reproduced lexical accuracy differs from original TF-IDF validation")
                expected_old=e5["comparisons"][domain]["legacy_raw"][coder]["random_120"]["accuracy"]
                expected_centered=e5["comparisons"][domain]["fulltext_centered"][coder]["random_120"]["accuracy"]
                computed_old=metrics(truth,predictions["legacy_raw"],lexical_names+[NONE])
                computed_centered=metrics(truth,predictions["fulltext_centered"],lexical_names+[NONE])
                if computed_old["accuracy"]!=expected_old or (
                    computed_centered["accuracy"]!=expected_centered
                ):
                    raise ValueError("Reproduced E5 accuracy differs from frozen v2 report")
                result["comparisons"][domain][coder]={
                    variant:paired_summary(truth,lpred,predictions[variant],
                                            domain,args.bootstrap,args.seed)
                    for variant in CANDIDATES
                }

    result["limitations"]=[
        "Same 120 theses used for all comparison pairs, not independent replications.",
        "The 120 cases were examined in earlier model analyses; comparisons and McNemar p values are exploratory, unadjusted for multiplicity.",
        "A/B are separately coded imperfect human references; no adjudicated reference was used.",
        "TF-IDF uses original analysis_text while fulltext-centered E5 uses full document: differences cannot be attributed to encoder alone.",
        "The lexicon was derived from historical source dictionaries, not validated as the official Imbabura PDOT taxonomy.",
        "Rare-class recall/precision cannot be estimated reliably from sparse 120-case supports.",
        "Both methods are forced top1 here; no-match performance is not established.",
        "Results concern thematic similarity only, not actual UN SDG or territorial-policy impact.",
        "This report includes aggregate statistics only; no identifiers or document-level predictions are published.",
    ]
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root",type=Path,required=True)
    p.add_argument("--private-dir",type=Path,default=Path(
        "data/revision_private/validation"))
    p.add_argument("--lexical-scores",type=Path,default=Path(
        "data/revision_private/reviewer_historical_tfidf_human_metrics_v1/"
        "historical_source_tfidf_scores_PRIVATE.npz"))
    p.add_argument("--e5-scores",type=Path,default=Path(
        "data/revision_private/reviewer_fulltext_reclassification/"
        "reclassification_all_7830_PRIVATE.npz"))
    p.add_argument("--lexical-report",type=Path,default=Path(
        "docs/audits/reviewer_historical_tfidf_human_metrics_v1.json"))
    p.add_argument("--e5-report",type=Path,default=Path(
        "docs/audits/reviewer_four_e5_variant_dual_coder_metrics_v2.json"))
    p.add_argument("--e5-source-report",type=Path,default=Path(
        "docs/audits/reviewer_fulltext_reclassification_v1.json"))
    p.add_argument("--output",type=Path,default=Path(
        "docs/audits/reviewer_tfidf_vs_e5_paired_random_v1.json"))
    p.add_argument("--bootstrap",type=int,default=5000)
    p.add_argument("--seed",type=int,default=5142)
    a=p.parse_args()
    if a.bootstrap<1000 or a.bootstrap>20000:
        p.error("Bootstrap must be between 1000 and 20000")
    report=analyze(a)
    out=write_public(report,a.output,Path(__file__).resolve().parent.parent)
    print("PAIRED TF-IDF vs frozen E5 comparison on 120 random cases:",out)
    for domain in DOMAINS:
        print(domain.upper())
        for coder in CODERS:
            for variant in CANDIDATES:
                entry=report["comparisons"][domain][coder][variant]
                pair=entry["paired_candidate_minus_lexical"]
                print(coder,variant,
                      "TFIDF:",entry["lexical_accuracy"],
                      "E5:",entry["candidate_accuracy"],
                      "delta E5 minus TFIDF (pp):",pair["accuracy_delta_points"],
                      "CI95:",pair["delta_bootstrap95_points"],
                      "gains/losses:",pair["candidate_correct_baseline_wrong_n"],
                      pair["baseline_correct_candidate_wrong_n"],
                      "unadjusted McNemar p:",pair["mcnemar_exact_two_sided_p_unadjusted"])
    print("Retrospective/exploratory only. No claims of PDOT policy impact or prospective model superiority.")


if __name__=="__main__":
    main()
