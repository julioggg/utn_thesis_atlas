# Manuscript exhibit release — Sustainability major revision

## Run once on CEDIA

The author has stated that A/B coding and adjudication were performed by human reviewers. The repository does **not** contain signed committee minutes, so the release distinguishes author-confirmed human work from independently inspectable formal endorsement.

```bash
cd "$HOME/utn_thesis_atlas_revision"
git pull --ff-only origin main
bash scripts/run_manuscript_revision_release.sh
```

This invokes three **preinstalled repository scripts** (no copy/paste into editors and no PDF/embedding regeneration):

1. `scripts/reviewer_freeze_manuscript_snapshot.py` freezes **private, row-level** model predictions in `data/revision_private/manuscript_release_v1/model_snapshot_PRIVATE.parquet`. It verifies the 7,830 ID-aligned historical records, archived score matrices, descriptor order, observed faculty provenance and original adviser completeness. It defaults to `fulltext_centered` as a **retrospective exploratory descriptive choice**—not as a prospectively validated winner.
2. `scripts/reviewer_build_manuscript_assets.py` recomputes the aggregate statistical tables, figure source counts, human A/B kappa, TF-IDF versus E5 comparisons and `paper_numbers_lock.json` from that single snapshot and frozen CEDIA audit reports.
3. `scripts/run_manuscript_revision_release.sh` verifies export file types, PNG physical 600+ DPI metadata, table presence and publication directory boundaries. It then stages **only** `docs/revision_assets/v1/` (not `data/`) and pushes aggregate scientific figures/tables to the existing public GitHub repository.

**Never** commit any file in `data/revision_private`, thesis documents, source handles, individual human judgments, original thesis text or embeddings. All these remain on CEDIA.

## What will appear publicly

`docs/revision_assets/v1/figures/`: seven English main figures and one supplementary comparison figure, each as **PNG 600 dpi** plus vector PDF/SVG.

| Exhibit | Content | Reviewer concern addressed |
|---|---|---|
| Figure 1 | Auditable analysis/validation framework | R3/R4: framework, not only workflow |
| Figure 2 | Annual thesis counts by five faculties + unresolved metadata; 2026 marked incomplete | R1/R4: temporal trends and faculty truth |
| Figure 3 | Five-faculty SDG heatmap, row-normalized, numerical census reconciliation | R1/R2/R4: SDG 4, Figure 3 totals |
| Figure 4 | Five-faculty heatmap of six **analytical** PDOT categories | R1–R4: territorial distribution |
| Figure 5 | Two distinct observations: ten-priority share and mean selected cosine | R1/R2/R3: duplicate figure and unjustified index |
| Figure 6 | Centroid distance matrix in original 1,024-dimensional centered fulltext space | R1/R3: invalid UMAP hull-area inference |
| Figure 7 | Topic share change from 2021–2022 to 2024–2025, with support floor | R1/R4: incomplete 2026, unstable trends |
| Supplementary S1 | E5 and TF-IDF accuracy on the same 120 theses with both coders | R3: external method comparator |

`docs/revision_assets/v1/tables/`: manuscript Tables 1–8 plus supplementary per-category F1/support, paired TF-IDF/E5 inference, BH-adjusted residuals when appropriate. CSV and Markdown, **aggregate only**.

`docs/revision_assets/v1/paper_numbers_lock.json`: frozen counts (N=7,830, SDG4, each six PDOT analytical axis, faculty totals, kappa, source SHA-256). Use this to update the manuscript; **do not paste historical counts from the submitted draft**.

`docs/revision_assets/v1/CAPTIONS_EN.md`: English captions with distinctions between semantic proximity, contribution and impact.

`docs/revision_assets/v1/RELEASE_MANIFEST.json`: expected files, hashes, figure resolution and machine-verifiable release checks.

## Editorial guardrails

- No synthetic/fabricated values: a missing PDF embedding matrix, missing topic series, unexpected class code, incomplete validation JSON or inconsistent total causes a **hard failure**, not a placeholder chart.
- All three semantic domains come from one score variant (SDG, PDOT analytical categories, and source-defined ten local needs); prior historical categories are comparator baselines only.
- The local priority numeric display codes reflect the **source dictionary order** without asserting an unverified English translation. The source terms/descriptors still require explicit documentary review before final submission.
- The prior `share × similarity` coverage index is **removed** because its original formal definition was not independently established. Figure 5 shows observed indicators separately.
- UMAP convex hulls are **not used** as overlap measures. No citation about hidden institutional capability, tutor profiles, causation or measured SDG progress is inferred from these plots.
- For statistics, report five real faculties only; a high-specificity career-to-faculty imputation remains distinguishable from verified institutional metadata. Expected cells less than five require conservative interpretation; a permutation test is included.
- Four representations plus TF-IDF were evaluated on the same 120 randomly selected theses and A/B separately. Tests are **retrospective/exploratory**, not prospectively untouched, and A/B are correlated coders.
- The historical PDOT six groups are an **analytical classifier taxonomy** until explicitly mapped to the official provincial policy plan. Ten territorial needs also require source/version justification.
- A signed human ratification statement and formally agreed rule for the other 403 A=B cases are still necessary if the manuscript presents the 450 as a single consensual **gold standard**. Human ratification of 47 has been stated by the researcher; do not invent a signed act or signatories.
- Corpus flow, two anomalous non-thesis items, OCR handling, 75-topic silhouette provenance, bibliographic duplicates, ethics/data privacy, scientific caveats, and point-by-point R1–R4 responses remain **manuscript editing tasks**, not grounds for inventing metrics.

## Final use

After successful completion, review the public results at:

https://github.com/julioggg/utn_thesis_atlas/tree/main/docs/revision_assets/v1

Inspect figure readability and aggregate tables before importing into the DOCX manuscript. The images have explicit raster dpi and vector equivalents, but an editorial design proof against the final Word page layout is still required.
