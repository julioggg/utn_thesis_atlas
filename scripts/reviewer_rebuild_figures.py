#!/usr/bin/env python3
"""Rebuild canonical legacy descriptive tables and distinct figures.

Legacy (unvalidated forced top1) outputs, NOT the final journal results.
All figures and tables are kept in git-ignored data/revision_private.
One aggregate reconciliation JSON is candidate for public documentation.
Do not propagate the disputed coverage index without verifying its
original intended formula and the policy domain definition.
"""
from __future__ import annotations
import argparse
import time
from pathlib import Path
import numpy as np
import pandas as pd
from reviewer_shared import normalize_codes, private_output, write_public


def canonical_tables(frame):
    if len(frame) != 7830:
        raise ValueError("Original analytical corpus must have 7830 rows")
    if frame["handle_id"].isna().any() or frame["handle_id"].duplicated().any():
        raise ValueError("Duplicated or empty source IDs")
    sdg = np.asarray(normalize_codes(frame["ods_top1"]))
    if "[invalid]" in sdg:
        raise ValueError("Invalid ODS code")
    sdg_counts = pd.Series(sdg).value_counts().reindex(
        [f"ODS {i}" for i in range(1,18)],fill_value=0
    )
    pdot_counts = frame["pdot_top1"].value_counts(dropna=False).sort_values(ascending=False)
    need_group = frame.groupby("need_top1",dropna=False).agg(
        n=("need_top1","size"),
        mean_cosine=("need_top1_score","mean")
    ).sort_values("n",ascending=False)
    need_group["share"] = need_group["n"]/len(frame)
    need_group["coverage_candidate"] = need_group["share"]*need_group["mean_cosine"]
    if sum(sdg_counts) != len(frame) or pdot_counts.sum() != len(frame) or need_group["n"].sum() != len(frame):
        raise AssertionError("Aggregations do not sum to exact analytical corpus")
    counts = frame["advisor"].astype("string").fillna("").str.strip()
    records = counts.ne("").sum()
    unique = counts.loc[counts.ne("")].nunique()
    return sdg_counts, pdot_counts, need_group, int(records), int(unique)


def render_figures(sdg, pdot, needs, outdir):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        raise RuntimeError("Matplotlib is required for figure generation: python -m pip install matplotlib") from None

    def bar(labels,values,title,xlabel,file,width=11,height=7):
        fig,ax=plt.subplots(figsize=(width,height))
        y=np.arange(len(labels))
        ax.barh(y,values)
        ax.set_yticks(y,labels=labels)
        ax.invert_yaxis()
        ax.set_xlabel(xlabel)
        ax.set_title(title)
        ax.grid(axis="x",alpha=.18)
        ax.spines[["top","right"]].set_visible(False)
        fig.tight_layout()
        fig.savefig(outdir/(file+".png"),dpi=260,bbox_inches="tight")
        fig.savefig(outdir/(file+".svg"),bbox_inches="tight")
        plt.close(fig)

    bar([x.replace("ODS ","SDG ") for x in sdg.index],
        [int(v) for v in sdg.values],
        "Original model: SDG thematic assignment (unvalidated)", "Number of theses",
        "figure3_canonical_sdg_legacy",width=9,height=7)
    bar([str(x) for x in pdot.index],[int(x) for x in pdot.values],
        "Original model: PDOT thematic assignment (unvalidated)", "Number of theses",
        "figure4_pdot_legacy",width=13,height=6)
    bar([str(x) for x in needs.index],[float(v) for v in needs["share"]],
        "Original model: ten local needs (unvalidated)", "Share of theses",
        "figure5_ten_local_needs_share_legacy",width=14,height=7)
    bar([str(x) for x in needs.index],[float(v) for v in needs["coverage_candidate"]],
        "Candidate coverage: share × mean similarity (NOT verified manuscript index)",
        "Candidate index (unitless)", "candidate_coverage_index_needs",
        width=14,height=7)


def make(args):
    root=args.project_root.expanduser().resolve()
    workspace=Path(__file__).resolve().parent.parent
    df=pd.read_parquet(root/"data/processed/07_alignment_pdot_ods_needs.parquet",
                       columns=["handle_id","ods_top1","pdot_top1","need_top1",
                                "need_top1_score","advisor"])
    sdg,pdot,need,with_advisor,unique_advisors=canonical_tables(df)
    directory=private_output(args.private_dir, workspace)
    sdg.rename_axis("ODS").rename("n").to_csv(directory/"table2_sdg_counts.csv")
    pdot.rename_axis("PDOT_axis").rename("n").to_csv(directory/"pdot_axis_counts.csv")
    need.rename_axis("local_need").to_csv(directory/"table3_need_candidate_coverage.csv")
    if args.render_figures:
        render_figures(sdg,pdot,need,directory)
    report={
        "schema_version":1,
        "status":"original_legacy_tables_reconciled_not_new_validated_analysis",
        "population_rows":len(df),
        "table2_ods_totals_sum":int(sdg.sum()),
        "table2_sdg4_count":int(sdg["ODS 4"]),
        "manuscript_table2_sdg4_stated":2649,
        "manuscript_figure3_sdg4_stated":2668,
        "manuscript_figure3_sum_stated":7568,
        "manuscript_difference_sdg4_bar_minus_table":19,
        "legacy_counts_match_reported_table2_sdg4":bool(sdg["ODS 4"]==2649),
        "pdot_axis_sum":int(pdot.sum()),
        "ten_needs_sum":int(need["n"].sum()),
        "local_needs_count":len(need),
        "advisor_records_with_nonempty_value":with_advisor,
        "unique_nonempty_advisor_values":unique_advisors,
        "figure5_generated_from_distinct_local_need_data": bool(args.render_figures),
        "coverage_index_candidate_only": True,
        "figures_generated_in_private_data":bool(args.render_figures),
        "notes":[
            "Each figure/table is generated from one canonical legacy 07 parquet dataset.",
            "SDG 4 original assignment count agrees with Table 2, not the erroneous Figure 3 count.",
            "Figure 5 local-needs figure is distinct from Figure 4 PDOT figure.",
            "An apparent coverage index formula is not established by numerical resemblance.",
            "Original 2026 is incomplete; figure counts do not imply complete-year trends.",
            "Advisor nonmissing records and distinct unstandardized advisor values measure different quantities.",
            "Figures and tables are exploratory legacy baselines and should not replace final results before the method is frozen.",
            "No document-level texts, authors, source IDs or embeddings were exported.",
        ],
    }
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root",type=Path,required=True)
    p.add_argument("--private-dir",type=Path,
                   default=Path("data/revision_private/reviewer_publication_figures"))
    p.add_argument("--render-figures",action="store_true")
    p.add_argument("--output",type=Path,
                   default=Path("docs/audits/reviewer_figure_reconciliation.json"))
    a=p.parse_args()
    t0=time.perf_counter()
    report=make(a)
    report["elapsed_seconds"]=round(time.perf_counter()-t0,3)
    path=write_public(report,a.output,Path(__file__).resolve().parent.parent)
    print("Reconciled legacy table and figure sources:",path)
    print("Legacy SDG4:",report["table2_sdg4_count"],
          "advisor records:",report["advisor_records_with_nonempty_value"],
          "unique unstandardized advisor values:",report["unique_nonempty_advisor_values"])
    print("All figures and detailed tables remain PRIVATE in ignored data/.")


if __name__=="__main__":
    main()
