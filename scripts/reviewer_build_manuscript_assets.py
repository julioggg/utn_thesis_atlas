#!/usr/bin/env python3
"""Generate English 600-DPI figures, vector PDFs, aggregate tables and numbers lock.

IMPORTANT: no private thesis row, raw text, handle, student/advisor identity,
embedding vector or source document is ever copied to docs/. Reproducible
aggregates are built only from a privately frozen descriptive snapshot.
If a source field or validation report is missing, FAIL rather than invent
a placeholder, constant similarity, generic prevalence or false claim.

Model: fulltext_centered sensitivity representation, chosen retrospectively.
Not a prospectively validated policy impact classifier.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from reviewer_human_validation_metrics import agreement,labels_from_coder
from reviewer_render_manuscript_figures import (
    FACULTY_SHORT,PDOT_NAMES,annual,centroid,heatmap,
    models,needs,topic_growth,workflow
)
from reviewer_shared import FIVE_FACULTIES,sha256_file
from reviewer_stage1_stats import contingency_and_tests

N=7830
DOMAINS=("ods","pdot","need")
MODELS=(
    ("legacy_raw","Legacy E5"),
    ("legacy_centered","Legacy E5 centered"),
    ("fulltext_raw","Fulltext E5"),
    ("fulltext_centered","Fulltext E5 centered"),
)

def load_json(path):
    p=Path(path)
    if not p.is_file():raise FileNotFoundError(str(p))
    return json.loads(p.read_text(encoding="utf-8"))

def table(outdir,name,columns,rows):
    df=pd.DataFrame(rows,columns=columns)
    if df.empty:raise ValueError("Empty table forbidden: "+name)
    outdir.mkdir(parents=True,exist_ok=True)
    p=outdir/(name+".csv")
    df.to_csv(p,index=False,encoding="utf-8")
    md=outdir/(name+".md")
    def cell(v):
        return str(v).replace("|","/").replace("\n"," ").replace("\r"," ")
    md.write_text(
        "| "+" | ".join(columns)+" |\n"+
        "| "+" | ".join(["---"]*len(columns))+" |\n"+
        "".join("| "+" | ".join(cell(x) for x in rec)+" |\n"
                for rec in df.itertuples(index=False,name=None)),
        encoding="utf-8"
    )
    return df

def verify_ledger(df,audit):
    if audit.get("status")!="frozen_descriptive_model_snapshot_exploratory":
        raise ValueError("Missing expected frozen snapshot audit")
    if audit.get("model_variant")!="fulltext_centered":
        raise ValueError("Manuscript assets require the documented fulltext_centered candidate")
    if len(df)!=N or df["handle_id"].isna().any() or df["handle_id"].duplicated().any():
        raise ValueError("Frozen 7830 source handles changed")
    if not np.array_equal(df["source_row_index"].to_numpy(),np.arange(N)):
        raise ValueError("Original row indexing was changed")
    for d in DOMAINS:
        if not {f"{d}_label",f"{d}_top1_score",f"{d}_margin"}.issubset(df.columns):
            raise ValueError("Missing frozen model scores for "+d)
        if df[f"{d}_label"].isna().any():
            raise ValueError("Missing selected label")
    if set(df["faculty5"].unique())-set(FIVE_FACULTIES)-{"Unassigned"}:
        raise ValueError("Unexpected faculty name in publication snapshot")
    observed=pd.to_numeric(df["year"],errors="coerce")
    if observed.dropna().empty:raise ValueError("No year information")
    for d in DOMAINS:
        keys=df[f"{d}_label"].value_counts().to_dict()
        expected=audit["label_totals"][d]
        # Historical local-need strings cannot be exported in public audits;
        # verify aggregate count multiset + category cardinality instead.
        if d=="need":
            if sorted(keys.values())!=sorted(expected.values()):
                raise ValueError("Local needs distribution inconsistent with locked audit")
        elif keys!=expected:
            raise ValueError("SDG/PDOT totals differ from locked audit")
    if df["advisor_reported"].sum()!=audit["adviser_records_with_nonempty_value"]:
        raise ValueError("Adviser-record census changed")
    return True

def coder_data(workspace):
    base=workspace/"data/revision_private/validation"
    master=pd.read_csv(base/"sample_master_private.csv",dtype=str,keep_default_na=False)
    if len(master)!=450 or master["study_id"].duplicated().any():
        raise ValueError("Human 450-case frozen master invalid")
    people={}
    for coder in ("A","B"):
        x=pd.read_csv(base/f"coder_{coder}_private.csv",dtype=str,keep_default_na=False)
        if set(x["study_id"])!=set(master["study_id"]) or x["study_id"].duplicated().any():
            raise ValueError("A/B coder roster changed")
        x=x.set_index("study_id").reindex(master["study_id"]).reset_index()
        if not np.array_equal(x["private_source_handle"].str.lstrip("'").to_numpy(),
                              master["handle_id"].to_numpy()):
            raise ValueError("A/B source handles changed")
        people[coder]=x
    return master,people

def model_validation(workspace,table_dir):
    v2=load_json(workspace/"docs/audits/reviewer_four_e5_variant_dual_coder_metrics_v2.json")
    lexical=load_json(workspace/"docs/audits/reviewer_historical_tfidf_human_metrics_v1.json")
    paired=load_json(workspace/"docs/audits/reviewer_tfidf_vs_e5_paired_random_v1.json")
    if v2.get("status")!="four_frozen_E5_representations_vs_two_independent_coders_not_adjudicated":
        raise ValueError("Wrong 4-E5 frozen comparison report")
    if lexical.get("status")!="historical_source_lexical_TFIDF_ODS_PDOT_AB_validation_exploratory":
        raise ValueError("Wrong lexical comparison report")
    if paired.get("status")!="exploratory_paired_TFIDF_vs_frozen_E5_on_120_random":
        raise ValueError("Wrong paired comparison report")
    rows=[]
    for domain in ("ods","pdot"):
        for who in ("A","B"):
            l=lexical["comparisons"][domain]["human_coders"][who]["random_120"]
            rows.append((domain.upper(),who,"TF-IDF","random_120", "accuracy",l["accuracy"]))
            rows.append((domain.upper(),who,"TF-IDF","random_120", "macro-F1",l["macro_f1_present_or_predicted_classes"]))
            for variant,title in MODELS:
                r=v2["comparisons"][domain][variant][who]["random_120"]
                if r["n"]!=120 or l["n"]!=120:raise ValueError("Model 120-case roster changed")
                rows.append((domain.upper(),who,title,"random_120","accuracy",r["accuracy"]))
                rows.append((domain.upper(),who,title,"random_120",
                             "macro-F1",r["macro_f1_present_or_predicted_classes"]))
    model=pd.DataFrame(rows,columns=["domain","coder","method","stratum","metric","value"])
    if len(model)!=40:raise ValueError("Expected 40 model metric rows")
    table(table_dir,"Table_06_Classifier_Accuracy_and_MacroF1",
          ["Domain","Human coder","Classifier","Sample","Metric","Value"],
          [(d,c,m,s,z,round(float(v),6)) for d,c,m,s,z,v in model.itertuples(index=False,name=None)])
    paired_rows=[]
    for domain in ("ods","pdot"):
        for who in ("A","B"):
            for cand in ("legacy_raw","fulltext_centered"):
                x=paired["comparisons"][domain][who][cand]
                p=x["paired_candidate_minus_lexical"]
                paired_rows.append((domain.upper(),who,cand,
                    p["n"],p["accuracy_delta_points"],p["delta_bootstrap95_points"][0],
                    p["delta_bootstrap95_points"][1],
                    p["candidate_correct_baseline_wrong_n"],
                    p["baseline_correct_candidate_wrong_n"],
                    p["mcnemar_exact_two_sided_p_unadjusted"]))
    table(table_dir,"Table_S02_Paired_TFIDF_E5",
        ["Domain","Coder","E5 variant","Paired n","Delta accuracy (pp)",
         "Bootstrap 95% lower (pp)","Bootstrap 95% upper (pp)",
         "Cases gained","Cases lost","Exact McNemar p (unadjusted)"],paired_rows)
    class_rows=[]
    for domain,n in (("ods",17),("pdot",6)):
        for who in ("A","B"):
            filename=(workspace/"data/revision_private/four_e5_variant_coder_metrics_v2"/
                f"{domain}_fulltext_centered_vs_{who}_random_120_perclass_PRIVATE.csv")
            x=pd.read_csv(filename)
            req={"class","reference_n","predicted_n","precision","recall","f1"}
            if not req.issubset(x.columns):raise ValueError("Missing F1 support details")
            if len(x)!=n+1 or sum(x["reference_n"])!=120:
                raise ValueError("Per-class 120-case validation support mismatched")
            for r in x.itertuples(index=False):
                # Use attribute-safe access through column labels, never include thesis handles.
                vals=r._asdict()
                class_rows.append((domain.upper(),who,vals["class"],
                   int(vals["reference_n"]),int(vals["predicted_n"]),
                   round(float(vals["precision"]),4),
                   round(float(vals["recall"]),4),round(float(vals["f1"]),4)))
    table(table_dir,"Table_S01_Per_Class_Human_Metrics",
        ["Domain","Human coder","Class","Reference support (n)","Predicted (n)",
         "Precision","Recall","F1"],class_rows)
    return model,{"n_class_metric_rows":len(class_rows),
       "human_reference":"A and B separately; consensus reference not frozen in this analysis",
       "tfidf_e5_paired_result_sha256":sha256_file(
            workspace/"docs/audits/reviewer_tfidf_vs_e5_paired_random_v1.json")}

def study_five_faculty(df,outdir):
    real=df["faculty5"].isin(FIVE_FACULTIES)
    fac=df.loc[real,"faculty5"].to_numpy(dtype=str)
    sdg=df.loc[real,"ods_label"].to_numpy(dtype=str)
    if len(fac)<1000:raise ValueError("Few valid real-faculty rows")
    c,expected,s=contingency_and_tests(fac,sdg,seed=42,permutations=999)
    if int(c.sum())!=len(fac):raise ValueError("Faculty x SDG population sums wrong")
    row=[("Faculty × SDG thematic alignment",len(fac),s["chi_squared"],
          s["df_nominal"],s["cramers_v"],s["permutation_p_value"],
          s["n_expected_below_5"],s["n_expected_below_1"])]
    table(outdir,"Table_05_Five_Faculty_Association",
          ["Test","N","Chi-square","Nominal df","Cramer's V",
           "Permutation p (999 shuffles)","Expected cells below 5","Expected cells below 1"],row)
    # Do not expose unrestricted row-level results. Aggregated residuals
    # are by faculty and SDG class; only cells with expected n>=5.
    residual_rows=[(
        FACULTY_SHORT[x["faculty"]],x["ods"].replace("ODS","SDG"),
        x["observed"],x["expected"],x["adjusted_residual_z"],x["q_bh"]
    ) for x in s["significant_adjusted_residual_cells"]]
    if residual_rows:
        table(outdir,"Table_S03_Adjusted_Standardized_Residuals",
              ["Faculty","SDG","Observed","Expected","Adjusted residual z","BH q"],
              residual_rows)
    return s

def build(args):
    workspace=Path(__file__).resolve().parent.parent
    private=(workspace/"data/revision_private").resolve()
    snap=args.snapshot.expanduser().resolve()
    if not snap.is_relative_to(private):
        raise ValueError("Frozen source snapshot must be private")
    if not snap.is_file():raise FileNotFoundError(str(snap))
    root=args.assets.expanduser().resolve()
    release_root=(workspace/"docs/revision_assets").resolve()
    if not root.is_relative_to(release_root):
        raise ValueError("Publication release may only be in docs/revision_assets")
    audit=load_json(args.audit.expanduser().resolve())
    if sha256_file(snap)!=audit["private_snapshot_sha256"]:
        raise ValueError("Private snapshot SHA-256 differs from frozen audit")
    df=pd.read_parquet(snap)
    verify_ledger(df,audit)
    output=root/"figures"
    tables=root/"tables"
    output.mkdir(parents=True,exist_ok=True)
    tables.mkdir(parents=True,exist_ok=True)

    counts={d:df[f"{d}_label"].value_counts().to_dict() for d in DOMAINS}
    if any(sum(counts[d].values())!=N for d in DOMAINS):
        raise ValueError("Selected-label totals not equal to 7830")
    year=pd.to_numeric(df["year"],errors="coerce")
    fac=df["faculty5"].value_counts().to_dict()
    advisor=int(df["advisor_reported"].sum())
    table(tables,"Table_01_Corpus_Profile",
        ["Measure","Value"],[
        ("Analytical repository records",N),
        ("Source-verified genuine-faculty records",int((df["faculty_source"]=="metadata").sum())),
        ("Career-imputed faculty records",int((df["faculty_source"]=="career_imputed").sum())),
        ("Unresolved faculty records",int((df["faculty_source"]=="unresolved").sum())),
        ("Records with a nonempty advisor value",advisor),
        ("Distinct unstandardized advisor values",audit["distinct_unstandardized_adviser_strings"]),
        ("Earliest documented year",int(year.dropna().min())),
        ("Latest documented year (2026 incomplete)",int(year.dropna().max())),
        ("Human reference reviewed by coders",450),
        ("Main-label conflicts examined by committee",47),
    ])
    table(tables,"Table_02_SDG_Top1_Affinities",
          ["SDG","N (model top-1)","Share (%)"],[
        (f"SDG {i}",int(counts["ods"].get(f"ODS {i}",0)),
         round(100*counts["ods"].get(f"ODS {i}",0)/N,3))
        for i in range(1,18)
    ])
    table(tables,"Table_03_PDOT_Top1_Affinities",
          ["Analytical PDOT axis","Descriptor (English analytical gloss)","N (model top-1)","Share (%)"],[
        (f"Axis {i}",PDOT_NAMES[f"PDOT {i}"],
         int(counts["pdot"].get(f"PDOT {i}",0)),
         round(100*counts["pdot"].get(f"PDOT {i}",0)/N,3))
        for i in range(1,7)
    ])
    # Need numbering is anchored to original source dictionary order in the
    # source reclassification report. English IDs avoid guessed translations.
    original=load_json(args.source_report.expanduser().resolve())
    need_source=list(original["domains"]["need"]["representations"]["legacy_raw"]
                     ["top1_category_counts_candidate_unvalidated"])
    if len(need_source)!=10 or set(need_source)!=set(counts["need"]):
        raise ValueError("Ten source-defined needs changed")
    need_codes={label:f"Local priority {i:02d}" for i,label in enumerate(need_source,1)}
    need_rows=[]
    for name in need_source:
        subset=df.loc[df["need_label"]==name,"need_top1_score"]
        if subset.empty or not np.isfinite(subset).all():
            raise ValueError("Invalid local-priority source scores")
        n=len(subset)
        need_rows.append((need_codes[name],n,round(100*n/N,3),
                          round(float(subset.mean()),6),
                          round(float(subset.median()),6)))
    table(tables,"Table_04_Local_Needs_Separate_Measures",
          ["Source-order local-priority code","N","Share (%)",
           "Mean selected-descriptor cosine","Median selected-descriptor cosine"],
          need_rows)
    if sum(x[1] for x in need_rows)!=N:raise ValueError("Local-need counts invalid")

    master,humans=coder_data(workspace)
    agreements=[]
    for domain in ("ods","pdot"):
        a=labels_from_coder(humans["A"],domain)
        b=labels_from_coder(humans["B"],domain)
        stats=agreement(a,b)
        agreements.append((domain.upper(),450,stats["observed_agreement"],
                           stats["cohen_kappa"],stats["classes_observed"]))
    table(tables,"Table_07_Human_Interrater_Agreement",
          ["Domain","Two-coder sample n","Observed agreement","Cohen kappa",
           "Classes observed across coders"],agreements)
    stats=study_five_faculty(df,tables)
    model,model_meta=model_validation(workspace,tables)
    # Annual/SDG/PDOT/need tables are built from same source as figures.
    yrs=year.astype("Int64")
    topics=df["topic"].astype("string").str.strip()
    good=yrs.isin([2021,2022,2024,2025]) & topics.notna() & topics.ne("")
    valid=pd.DataFrame({"year":yrs[good].astype(int),"topic":topics[good].astype(str)})
    early=valid[valid["year"].isin([2021,2022])]["topic"].value_counts()
    late=valid[valid["year"].isin([2024,2025])]["topic"].value_counts()
    trend=[]
    for t in sorted(set(early.index)|set(late.index)):
        a=int(early.get(t,0));b=int(late.get(t,0))
        if a+b>=12 and b>=5 and early.sum() and late.sum():
            trend.append((f"Topic {t}",a,b,
                         round(100*a/early.sum(),3),round(100*b/late.sum(),3),
                         round(100*(b/late.sum()-a/early.sum()),3)))
    if len(trend)<4:raise ValueError("Insufficient comparable topic counts for Figure 7")
    trend=sorted(trend,key=lambda row:row[-1],reverse=True)
    table(tables,"Table_08_Topic_Share_Change",
          ["Topic ID","2021–2022 count","2024–2025 count","Earlier share (%)",
           "Later share (%)","Difference (percentage points)"],trend)

    figures={
        "Figure 01":workflow(output),
        "Figure 02":annual(df,output),
        "Figure 03":heatmap(df,"ods",output),
        "Figure 04":heatmap(df,"pdot",output),
        "Figure 05":needs(df,need_codes,output),
        "Figure 06":centroid(df,args.fulltext.expanduser().resolve(),output),
        "Figure 07":topic_growth(df,output),
        "Figure S01":models(model,output),
    }
    captions=[
        "# Figure captions — revised Sustainability manuscript (English)",
        "",
        "**Figure 1.** An auditable methodological framework connecting repository records, "
        "full-text embeddings, thematic affinity and human-informed sensitivity analysis.",
        "",
        "**Figure 2.** Recorded thesis production by genuine faculty and unresolved metadata "
        "(2021–2026). The 2026 observation window is incomplete.",
        "",
        "**Figure 3.** Five-faculty distribution of SDG-related top-1 semantic affinity "
        "from the full-text-centered exploratory classifier; row percentages sum to 100%.",
        "",
        "**Figure 4.** Five-faculty distribution among six historically implemented PDOT "
        "analytical categories. These are not certified as identical to official provincial axes.",
        "",
        "**Figure 5.** Distinct distributional and semantic descriptors of ten local priorities: "
        "share of assigned theses and mean cosine similarity. No inferred composite coverage index.",
        "",
        "**Figure 6.** Cosine distances between faculty centroids in the 1,024-dimensional "
        "mean-centered full-text space. No area-based inference from UMAP convex hulls.",
        "",
        "**Figure 7.** Topics showing increases in relative share in 2024–2025 against "
        "2021–2022. The incomplete 2026 year is excluded; labels are topic IDs.",
        "",
        "**Supplementary Figure S1.** Accuracy of TF-IDF and four frozen E5 representations "
        "against two human coders on the same 120 randomly selected theses. "
        "Comparisons are retrospective and exploratory.",
        "",
        "# Table caption guidance",
        "",
        "**Table 1.** Analytical corpus, faculty provenance and advisor data completeness.",
        "**Table 2.** SDG top-1 thematic affinity counts in the 7,830-record corpus.",
        "**Table 3.** Territorial analytical-axis top-1 affinity frequencies.",
        "**Table 4.** Local priority counts and cosine similarity, reported separately.",
        "**Table 5.** Five-faculty SDG contingency analysis with permutation inference.",
        "**Table 6.** Human reference comparisons of lexical and embedding-based classifiers.",
        "**Table 7.** Interrater agreement before main-label adjudication.",
        "**Table 8.** Topic relative-share change across comparable year windows.",
        "**Table S1.** Per-class precision, recall, F1 and class support from A/B references.",
        "**Table S2.** Paired TF-IDF/E5 differences and bootstrap confidence intervals.",
        "",
        "MODEL DISCLAIMER: Semantic affinity does not establish SDG contribution, "
        "territorial impact or causal institutional performance.",
    ]
    (root/"CAPTIONS_EN.md").write_text("\n".join(captions)+"\n",encoding="utf-8")
    lock={
        "schema_version":1,
        "status":"descriptive_editorial_numbers_lock_not_prospective_validation",
        "dataset":"fulltext_centered exploratory top-1; NOT policy impact",
        "n_corpus":N,
        "snapshot_sha256":audit["private_snapshot_sha256"],
        "model_source_sha256":audit["source_matrix_sha256"],
        "faculty_counts":{FACULTY_SHORT.get(k,"Unassigned"):int(v) for k,v in fac.items()},
        "faculty_lineage_counts":audit["faculty_provenance_counts"],
        "advisor_reported_records":advisor,
        "advisor_unique_unstandardized":audit["distinct_unstandardized_adviser_strings"],
        "sdg4_top1_n":int(counts["ods"].get("ODS 4",0)),
        "sdg_counts_17":{f"SDG {i}":int(counts["ods"].get(f"ODS {i}",0)) for i in range(1,18)},
        "pdot_analytical_counts_6":{f"Axis {i}":int(counts["pdot"].get(f"PDOT {i}",0)) for i in range(1,7)},
        "local_need_counts_source_order":{need_codes[x]:int(counts["need"][x]) for x in need_source},
        "human_agreement_before_adjudication":{
            k:{"observed_agreement":v,"cohen_kappa":kap}
            for k,n,v,kap,_ in agreements
        },
        "faculty_sdg_inference":stats,
        "model_validation":model_meta,
        "figures":figures,
        "limitations":[
            "All SDG/PDOT/need counts are forced single-label semantic top-1 distributions.",
            "Human classification was declared genuine by the corresponding author; signed committee provenance is a separate documentary item.",
            "Model comparison A/B does not equal committee-adjudicated gold-standard performance.",
            "Fulltext-centered was investigated using the same 120-case comparison sample: retrospective exploratory choice.",
            "Local-priority source terms have not been independently translated/certified for public release.",
            "The composite coverage index has been excluded; PDOT policy official equivalence remains unverified.",
            "Small expected contingency cells may affect asymptotic inference; 999-shuffle permutation test reported.",
            "No inferred advisor profiles, hidden capabilities, impact claims, UMAP convex-hull areas or fabricated silhouette values are provided.",
        ]
    }
    (root/"paper_numbers_lock.json").write_text(
        json.dumps(lock,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    # Release manifest built after every figure/table is successfully created.
    extensions={".png",".svg",".pdf",".csv",".md",".json"}
    paths=[p for p in root.rglob("*") if p.is_file()]
    if not paths or any(p.suffix not in extensions for p in paths):
        raise ValueError("Unexpected generated file type in public release")
    sha={str(p.relative_to(root)):sha256_file(p) for p in sorted(paths)
         if p.name!="RELEASE_MANIFEST.json"}
    release={
        "schema_version":1,
        "status":"release_candidate_aggregate_no_row_level_data",
        "n_figure_panels":len(figures),
        "raster_png_dpi":600,
        "vector_formats":["pdf","svg"],
        "n_tables":len([p for p in paths if p.parent.name=="tables" and p.suffix==".csv"]),
        "files_sha256":sha,
        "source_lock_sha256":sha256_file(root/"paper_numbers_lock.json"),
        "private_snapshot_copied_to_public":False,
        "scripts_reproducible_on_CEDIA":True,
        "provenance_warning":"Committee minutes and official territorial taxonomy approval still require documentation."
    }
    (root/"RELEASE_MANIFEST.json").write_text(
        json.dumps(release,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PUBLIC AGGREGATE EXHIBITS BUILT:",root)
    print("FIGURES:",len(figures),"all with PNG 600 dpi + vector PDF/SVG")
    print("TABLES:",release["n_tables"])
    print("NUMBERS LOCK SDG4:",lock["sdg4_top1_n"],"N=",N)
    print("Source/lock audit verified; no private row-level records exported.")
    print("Review official PDOT lineage and signed human protocol before manuscript submission.")
    return release


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshot",type=Path,default=Path(
        "data/revision_private/manuscript_release_v1/model_snapshot_PRIVATE.parquet"))
    p.add_argument("--audit",type=Path,default=Path(
        "docs/revision_assets/v1/model_snapshot_audit.json"))
    p.add_argument("--fulltext",type=Path,default=Path(
        "data/revision_private/fulltext_e5_large_v1/fulltext_e5_large_7830_PRIVATE.npy"))
    p.add_argument("--source-report",type=Path,default=Path(
        "docs/audits/reviewer_fulltext_reclassification_v1.json"))
    p.add_argument("--assets",type=Path,default=Path("docs/revision_assets/v1"))
    build(p.parse_args())

if __name__=="__main__":
    main()
