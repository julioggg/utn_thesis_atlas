#!/usr/bin/env python3
"""English journal-grade figure renderer. Every PNG >=600 DPI; also vector PDF/SVG.

No placeholder figures, no fictitious coverage index, no UMAP convex hulls.
All diagrams are rendered from a preflight-verified single frozen snapshot.
Plotting is pure presentation; population counts must match the locked tables.
"""
from __future__ import annotations
import math
from pathlib import Path

import numpy as np
import pandas as pd

from reviewer_shared import FIVE_FACULTIES

FACULTY_SHORT={
    FIVE_FACULTIES[0]:"Applied Engineering",
    FIVE_FACULTIES[1]:"Education and Technology",
    FIVE_FACULTIES[2]:"Business and Economics",
    FIVE_FACULTIES[3]:"Health Sciences",
    FIVE_FACULTIES[4]:"Agro-Environmental Eng.",
}
FACULTY_ORDER=[FACULTY_SHORT[x] for x in FIVE_FACULTIES]
PDOT_NAMES={
    "PDOT 1":"Physical–environmental",
    "PDOT 2":"Socio-cultural",
    "PDOT 3":"Economic and productive",
    "PDOT 4":"Settlements and connectivity",
    "PDOT 5":"Political–institutional",
    "PDOT 6":"Cross-cutting",
}
NAVY="#15243C"; DARK="#23354A"; SLATE="#65758A"; LIGHT="#E9EFF5"
TEAL="#087F8C"; AQUA="#37A9A3"; GOLD="#DC9A41"; CORAL="#CC6470"
GREY="#C3CFDA"; WHITE="#FFFFFF"
FACULTY_COLORS=[NAVY,TEAL,GOLD,CORAL,"#7588AD"]

def make_style():
    import matplotlib
    matplotlib.use("Agg",force=True)
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap
    plt.rcParams.update({
        "figure.facecolor":WHITE,"savefig.facecolor":WHITE,
        "font.family":"DejaVu Sans","font.size":9.5,
        "axes.titlesize":13.5,"axes.titleweight":"bold",
        "axes.labelsize":10,"axes.labelcolor":DARK,
        "axes.edgecolor":LIGHT,"axes.spines.top":False,
        "axes.spines.right":False,"axes.spines.left":False,
        "axes.spines.bottom":False,"xtick.color":SLATE,
        "ytick.color":DARK,"figure.dpi":120,
        "pdf.fonttype":42,"ps.fonttype":42,
    })
    cmap=LinearSegmentedColormap.from_list("journal_teal",["#F3F7FA","#9BD4D3",TEAL,NAVY])
    return plt,cmap

def save(fig,outdir,name):
    outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=True)
    fig.savefig(outdir/(name+".png"),dpi=600,bbox_inches="tight",pad_inches=.18,
                facecolor="white",metadata={"Software":"Matplotlib"})
    fig.savefig(outdir/(name+".pdf"),bbox_inches="tight",pad_inches=.18,
                facecolor="white")
    fig.savefig(outdir/(name+".svg"),bbox_inches="tight",pad_inches=.18,
                facecolor="white")
    import matplotlib.pyplot as plt
    plt.close(fig)
    return {"png":name+".png","pdf":name+".pdf","svg":name+".svg",
            "raster_dpi":600,"vector_formats":["pdf","svg"]}

def accent(ax,small):
    ax.text(0,1.06,small.upper(),transform=ax.transAxes,
            color=TEAL,fontsize=9.2,fontweight="bold",va="bottom")
    ax.set_axisbelow(True)

def workflow(outdir):
    plt,_=make_style()
    from matplotlib.patches import FancyBboxPatch,FancyArrowPatch
    fig,ax=plt.subplots(figsize=(14.2,5.3))
    fig.subplots_adjust(left=.04,right=.96,top=.87,bottom=.12)
    ax.set(xlim=(0,12),ylim=(0,5));ax.axis("off")
    ax.text(0,5.12,"From repository records to auditable institutional evidence",
            fontsize=16,fontweight="bold",color=NAVY)
    ax.text(0,4.72,"Reproducible workflow  •  Ecuadorian single-university case study",
            color=SLATE,fontsize=10)
    blocks=[
        (0.15,2.9,"01","Data capture","Records, documents\nand metadata"),
        (2.62,2.9,"02","Quality control","Text extraction,\nscreening and lineage"),
        (5.09,2.9,"03","Representation","E5 full text,\nwindow aggregation"),
        (7.56,2.9,"04","Interpretation","SDG, territorial\nand topic affinity"),
        (10.03,2.9,"05","Outputs","Audited distributions\nand limitations"),
    ]
    for i,(x,y,num,head,sub) in enumerate(blocks):
        box=FancyBboxPatch((x,y),2.04,1.30,boxstyle="round,pad=0.10,rounding_size=0.12",
                           linewidth=1.1,edgecolor="#DCE4EC",facecolor="#F7FAFC")
        ax.add_patch(box)
        ax.text(x+.16,y+1.03,num,fontsize=10.5,fontweight="bold",color=TEAL)
        ax.text(x+.16,y+.73,head,fontsize=11,fontweight="bold",color=NAVY)
        ax.text(x+.16,y+.22,sub,fontsize=8.5,color=SLATE,linespacing=1.4)
        if i<4:
            ax.add_patch(FancyArrowPatch((x+2.16,y+.63),(x+2.47,y+.63),
                        arrowstyle="-|>",mutation_scale=12,lw=1.4,color=AQUA))
    labels=[
        (1.00,"Human reference","450 independent A/B assessments\n47 main-label conflicts reviewed"),
        (4.50,"Method sensitivity","TF-IDF and four E5 variants\ncalibration + paired uncertainty"),
        (8.38,"Reporting discipline","Five genuine faculties\nNo causal impact claims"),
    ]
    for x,h,sub in labels:
        ax.add_patch(FancyBboxPatch((x,.38),2.65,1.18,
                      boxstyle="round,pad=0.12,rounding_size=0.10",
                      linewidth=1,edgecolor="#D1E5E5",facecolor="#ECF7F6"))
        ax.text(x+.15,1.20,h,fontsize=10.2,fontweight="bold",color=TEAL)
        ax.text(x+.15,.61,sub,fontsize=8.2,color=DARK,linespacing=1.35)
    ax.plot([.25,11.75],[1.97,1.97],color=LIGHT,lw=1.0,ls="--")
    ax.text(5.75,2.08,"REVIEW AND ROBUSTNESS LAYER",
            ha="center",fontsize=8.8,color=SLATE,fontweight="bold")
    return save(fig,outdir,"Figure_01_Methodological_Framework")

def annual(df,outdir):
    plt,_=make_style()
    years=range(2021,2027)
    fac=list(FIVE_FACULTIES)
    order=fac+["Unassigned"]
    tab=pd.crosstab(df["year"],df["faculty5"]).reindex(
        index=years,columns=order,fill_value=0)
    if tab.to_numpy().sum()==0:raise ValueError("No year/faculty records for Figure 2")
    fig,ax=plt.subplots(figsize=(12,5.9))
    fig.subplots_adjust(left=.10,right=.82,top=.80,bottom=.17)
    accent(ax,"Figure 02 / Corpus production")
    ax.set_title("Thesis output across the five faculties",loc="left",pad=20,color=NAVY)
    base=np.zeros(len(years))
    for i,col in enumerate(order):
        color=FACULTY_COLORS[i] if i<5 else GREY
        vals=tab[col].to_numpy()
        bars=ax.bar(list(years),vals,bottom=base,width=.63,label=(
            FACULTY_SHORT.get(col,"Unassigned metadata")),color=color,
            edgecolor="white",linewidth=.45)
        if i==5:
            for rect in bars:
                rect.set_hatch("///")
        base+=vals
    for year,total in zip(years,base):
        ax.text(year,total+max(base)*.018,f"{int(total):,}",
                ha="center",color=NAVY,fontsize=9.2,fontweight="bold")
    ax.set_ylabel("Number of repository theses")
    ax.set_xticks(list(years))
    ax.set_ylim(0,max(base)*1.15)
    ax.yaxis.grid(True,color=LIGHT)
    ax.legend(loc="upper left",bbox_to_anchor=(1.02,1.0),fontsize=8.6,
              frameon=False,title="Faculty / metadata",title_fontsize=9.1)
    ax.text(.0,-.17,"2026 is an incomplete observation year; do not interpret as annual decline.",
            transform=ax.transAxes,color=SLATE,fontsize=8.9)
    return save(fig,outdir,"Figure_02_Annual_Thesis_Production")

def heatmap(df,domain,outdir):
    plt,cmap=make_style()
    categories=([f"ODS {i}" for i in range(1,18)]
                if domain=="ods" else [f"PDOT {i}" for i in range(1,7)])
    mask=df["faculty5"].isin(FIVE_FACULTIES)
    sub=df.loc[mask].copy()
    tab=pd.crosstab(sub["faculty5"],sub[f"{domain}_label"]).reindex(
        index=FIVE_FACULTIES,columns=categories,fill_value=0)
    if tab.to_numpy().sum()!=len(sub):raise ValueError("Faculty/domain totals mismatch")
    denom=tab.sum(axis=1).to_numpy()
    if np.any(denom==0):raise ValueError("Empty genuine faculty")
    prop=tab.to_numpy()/denom[:,None]
    fig,ax=plt.subplots(figsize=(13.6 if domain=="ods" else 11.8,5.0))
    fig.subplots_adjust(left=.23,right=.90,top=.79,bottom=.18)
    accent(ax,"Figure 03 / SDG thematic affinities" if domain=="ods"
           else "Figure 04 / Territorial analytic axes")
    ax.set_title("Faculty distribution across "+(
        "Sustainable Development Goals" if domain=="ods"
        else "historical PDOT analytical categories"),loc="left",pad=19,color=NAVY)
    im=ax.imshow(prop,aspect="auto",interpolation="nearest",cmap=cmap,vmin=0,
                 vmax=max(.12,float(prop.max())))
    ax.set_yticks(range(5),[FACULTY_SHORT[x] for x in FIVE_FACULTIES])
    ax.set_xticks(range(len(categories)),[
        f"SDG {i}" for i in range(1,18)
    ] if domain=="ods" else [f"Axis {i}" for i in range(1,7)])
    ax.tick_params(axis="both",length=0,pad=6)
    if domain=="ods":ax.tick_params(axis="x",labelsize=8.5)
    for i in range(5):
        for j in range(len(categories)):
            if domain=="pdot" or prop[i,j]>=.03:
                ax.text(j,i,f"{prop[i,j]*100:.0f}%",ha="center",va="center",
                        fontsize=8.3,color=WHITE if prop[i,j]>.52*im.norm.vmax else DARK)
    cb=fig.colorbar(im,ax=ax,shrink=.94,pad=.024)
    cb.outline.set_visible(False);cb.ax.set_ylabel("Within-faculty share",color=SLATE)
    ax.text(0,-.25,"Genuine faculties only; career-imputed cases indicated in methods.",
            transform=ax.transAxes,color=SLATE,fontsize=8.6)
    return save(fig,outdir,"Figure_03_Faculty_SDG_Heatmap" if domain=="ods"
                else "Figure_04_Faculty_PDOT_Heatmap")

def needs(df,need_codes,outdir):
    plt,_=make_style()
    tmp=df.copy()
    tmp["code"]=tmp["need_label"].map(need_codes)
    if tmp["code"].isna().any():raise ValueError("Missing source-order local need mapping")
    tab=tmp.groupby("code",sort=False).agg(
        n=("code","size"),mean_similarity=("need_top1_score","mean")
    ).reindex(need_codes.values())
    if int(tab["n"].sum())!=len(df):raise ValueError("Need totals mismatch")
    tab["share"]=100*tab["n"]/len(df)
    tab=tab.sort_values("share",ascending=True)
    fig,(ax1,ax2)=plt.subplots(1,2,figsize=(14.8,6.0),sharey=True,
                                 gridspec_kw={"width_ratios":[1.1,1]})
    fig.subplots_adjust(left=.17,right=.95,bottom=.14,top=.79,wspace=.14)
    for a in (ax1,ax2):
        a.set_axisbelow(True);a.xaxis.grid(True,color=LIGHT)
        a.tick_params(length=0)
    fig.text(.17,.90,"FIGURE 05  /  TERRITORIAL PRIORITIES",color=TEAL,
             fontsize=9.4,fontweight="bold")
    fig.text(.17,.84,"Distinct measures of local-priority affinity",
             color=NAVY,fontsize=15,fontweight="bold")
    yy=np.arange(len(tab));lab=list(tab.index)
    ax1.barh(yy,tab["share"],height=.62,color=TEAL)
    ax1.set_yticks(yy,lab)
    ax1.set_title("Share of assigned theses",loc="left",color=NAVY)
    ax1.set_xlabel("% of the 7,830-record corpus")
    ax1.set_xlim(0,max(tab["share"])*1.18)
    for i,x in enumerate(tab["share"]):
        ax1.text(x+max(tab["share"])*.018,i,f"{x:.1f}%",
                 va="center",fontsize=8.7,color=DARK)
    ax2.barh(yy,tab["mean_similarity"],height=.62,color=GOLD)
    ax2.set_title("Mean top-1 cosine similarity",loc="left",color=NAVY)
    ax2.set_xlabel("Cosine similarity (unitless)")
    lo=min(0,float(tab["mean_similarity"].min()))
    hi=max(float(tab["mean_similarity"].max())*1.12,.02)
    ax2.set_xlim(lo,hi)
    ax2.tick_params(labelleft=False)
    fig.text(.17,.045,"These measures are shown separately; no unverified composite coverage index is used.",
             fontsize=8.7,color=SLATE)
    return save(fig,outdir,"Figure_05_Local_Needs_Separate_Measures")

def centroid(df,fulltext_path,outdir):
    plt,cmap=make_style()
    from reviewer_fulltext_anisotropy import center_and_normalize
    path=Path(fulltext_path)
    if not path.is_file():raise FileNotFoundError("Fulltext document embedding file required for Figure 6")
    vectors=np.load(path,mmap_mode="r",allow_pickle=False)
    if vectors.shape!=(7830,1024):raise ValueError("Fulltext embeddings not aligned")
    clean,_,_=center_and_normalize(vectors)
    faculty=df["faculty5"].to_numpy()
    centers=[]
    for f in FIVE_FACULTIES:
        sub=clean[faculty==f]
        if len(sub)<30:raise ValueError("Too few samples for genuine faculty "+f)
        mean=sub.mean(axis=0,dtype=np.float64)
        n=np.linalg.norm(mean)
        if n<1e-9:raise ValueError("Degenerate faculty centroid")
        centers.append(mean/n)
    centers=np.stack(centers)
    d=1-centers@centers.T
    d=np.clip(d,0,2)
    fig,ax=plt.subplots(figsize=(9.4,6.7))
    fig.subplots_adjust(left=.25,right=.90,bottom=.21,top=.82)
    accent(ax,"Figure 06 / Native 1,024-dimensional embedding space")
    ax.set_title("Between-faculty semantic centroid distances",
                 loc="left",pad=19,color=NAVY)
    im=ax.imshow(d,cmap=cmap,vmin=0,vmax=max(.05,float(d.max())))
    ax.set_xticks(range(5),[FACULTY_SHORT[f] for f in FIVE_FACULTIES],
                 rotation=27,ha="right")
    ax.set_yticks(range(5),[FACULTY_SHORT[f] for f in FIVE_FACULTIES])
    ax.tick_params(length=0)
    for i in range(5):
        for j in range(5):
            ax.text(j,i,"—" if i==j else f"{d[i,j]:.2f}",
                    ha="center",va="center",fontsize=10,
                    color=WHITE if d[i,j]>.6*im.norm.vmax else DARK)
    cb=fig.colorbar(im,ax=ax,shrink=.83,pad=.025)
    cb.outline.set_visible(False);cb.ax.set_ylabel("Cosine distance",color=SLATE)
    fig.text(.25,.048,"No UMAP hull areas; centroid separation does not prove interfaculty collaboration.",
             fontsize=8.4,color=SLATE)
    return save(fig,outdir,"Figure_06_Centroid_Cosine_Distance")

def topic_growth(df,outdir):
    plt,_=make_style()
    year=pd.to_numeric(df["year"],errors="coerce")
    topic=df["topic"].astype("string").str.strip()
    ok=year.isin([2021,2022,2024,2025]) & topic.notna() & topic.ne("") & ~topic.isin(["nan","None"])
    sub=pd.DataFrame({"year":year[ok].astype(int),"topic":topic[ok].astype(str)})
    if sub.empty:raise ValueError("Missing frozen year-topic data for emerging topics")
    early=sub[sub["year"].isin([2021,2022])]["topic"].value_counts()
    later=sub[sub["year"].isin([2024,2025])]["topic"].value_counts()
    if early.sum()==0 or later.sum()==0:raise ValueError("Missing comparable topic-year windows")
    rows=[]
    for name in set(early.index)|set(later.index):
        a=int(early.get(name,0));b=int(later.get(name,0))
        if a+b<12 or b<5:continue
        change=100*(b/later.sum()-a/early.sum())
        rows.append((name,a,b,float(change)))
    if len(rows)<4:raise ValueError("Too few topic trajectories; do not render placeholders")
    rows=sorted(rows,key=lambda v:v[3],reverse=True)[:12]
    rows=sorted(rows,key=lambda v:v[3])
    vals=[r[3] for r in rows]
    labels=[f"Topic {r[0]}" for r in rows]
    fig,ax=plt.subplots(figsize=(11.6,6.0))
    fig.subplots_adjust(left=.20,right=.94,bottom=.19,top=.80)
    accent(ax,"Figure 07 / Temporal sensitivity")
    ax.set_title("Topics gaining relative share in comparable periods",
                 color=NAVY,loc="left",pad=20)
    ax.barh(range(len(rows)),vals,color=AQUA,height=.7)
    ax.set_yticks(range(len(rows)),labels)
    ax.set_xlabel("Change in relative topic share (percentage points)")
    ax.axvline(0,color=SLATE,lw=1)
    ax.xaxis.grid(True,color=LIGHT)
    ax.set_xlim(min(0,min(vals)*1.1),max(vals)*1.18)
    for i,v in enumerate(vals):
        ax.text(v+max(vals)*.016,i,f"+{v:.2f} pp",
                color=DARK,va="center",fontsize=8.4)
    fig.text(.20,.05,
        "2021–2022 vs 2024–2025; minimum 12 combined / 5 later records. 2026 excluded.",
        color=SLATE,fontsize=8.9)
    return save(fig,outdir,"Figure_07_Topic_Share_Change")

def models(df,outdir):
    plt,_=make_style()
    subset=df[(df["stratum"]=="random_120") & (df["metric"]=="accuracy")]
    candidates=["TF-IDF","Legacy E5","Legacy E5 centered","Fulltext E5","Fulltext E5 centered"]
    coder=["A","B"]
    fig,(ax1,ax2)=plt.subplots(1,2,figsize=(13.4,5.8),sharey=True)
    fig.subplots_adjust(left=.085,right=.97,bottom=.27,top=.81,wspace=.15)
    for ax,domain in zip([ax1,ax2],["SDG","PDOT"]):
        data=subset[subset["domain"]==domain]
        mat=np.zeros((len(candidates),2))
        for i,method in enumerate(candidates):
            for j,who in enumerate(coder):
                match=data[(data["method"]==method)&(data["coder"]==who)]
                if len(match)!=1:raise ValueError("Missing comparator accuracy: "+domain+method+who)
                mat[i,j]=float(match["value"].iloc[0])*100
        xx=np.arange(len(candidates))
        for j,c in enumerate(coder):
            ax.bar(xx+(-.17 if j==0 else .17),mat[:,j],width=.32,
                   color=TEAL if j==0 else GOLD,label=f"Coder {c}")
        ax.set_ylim(0,80)
        ax.set_xticks(xx,candidates,rotation=35,ha="right",fontsize=8.5)
        ax.set_title(domain+" classification",color=NAVY)
        ax.yaxis.grid(True,color=LIGHT)
        ax.legend(frameon=False,fontsize=8.9)
    ax1.set_ylabel("Exact-match accuracy (%)")
    fig.text(.085,.92,"SUPPLEMENTARY  /  ROBUSTNESS",color=TEAL,
             fontsize=9,fontweight="bold")
    fig.text(.085,.855,"Lexical and semantic classifiers on 120 random theses",
             color=NAVY,fontsize=14.8,fontweight="bold")
    fig.text(.085,.065,"Exploratory A/B reference comparisons; not a prospectively untouched test.",
             color=SLATE,fontsize=8.7)
    return save(fig,outdir,"Figure_S01_Method_Accuracy_Sensitivity")
