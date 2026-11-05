# UTN Thesis Atlas — validated revision workspace

Repository for the **major-revision analysis** of the manuscript on semantic mapping of thesis repositories, Sustainable Development Goals (SDGs) and Imbabura territorial-planning priorities (PDOT).

**Current status:** revision scaffolding. No HPC data have been transferred, and no corrected manuscript results are claimed.

## Important: public repository and data protection

This repository is PUBLIC. **Do not push** thesis PDFs, extracted thesis text, student/advisor identities, handle-level records, metadata tables, row-level model predictions, raw embedding matrices, credentials, HPC account names, or unreviewed exports. Publicly available repository content is **not automatically cleared for wholesale redistribution**. Verify the applicable licenses and institutional/data-protection requirements before releasing any dataset.

Approved candidates for GitHub: source code without secrets, configuration templates, fixed SDG/PDOT descriptors with provenance, aggregate summaries after disclosure review, methods, validation protocol, charts without identifying information, and test fixtures with synthetic records.

The original HPC project remains the source of truth. Work in a separate clone; do not run a destructive setup or overwrite the original research directory.

## Quick start on CEDIA HPC

```bash
# Run from your HOME (or another suitable workspace), not inside your original project
git clone https://github.com/julioggg/utn_thesis_atlas.git utn_thesis_atlas_revision
cd utn_thesis_atlas_revision
python3 scripts/hpc_inventory.py --project-root "$HOME/utn_thesis_atlas" --output reports/public/hpc_inventory.json
python3 scripts/audit_corpus.py --project-root "$HOME/utn_thesis_atlas" --output reports/public/corpus_audit.json
```

If your original path is not `$HOME/utn_thesis_atlas`, replace it with the actual absolute path returned by `realpath utn_thesis_atlas`.

Inventory runs with the Python standard library. Corpus audit requires pandas and a Parquet reader (typically pyarrow). Neither script changes the original source files. Outputs are aggregate statistics only; inspect before publishing.

### Review workflow

1. **Inventory / audit:** locate the original model inputs, processed corpus, alignment outputs, embeddings, k-selection scores and execution logs; document counts and processing limitations.
2. **Data quality:** recover real faculties via a documented mapping, quantify failures, identify duplicates and missing titles, and reconcile the 7,830-record population.
3. **Human reference:** independently annotate a stratified set of theses with two coders; adjudicate disagreements and evaluate label reliability. Annotation files must stay private pending ethics/license review.
4. **Document representation:** compare original/truncated inputs with chunked full-text embeddings; record exact token limits, chunk strategy, aggregation and hardware/runtime.
5. **Classifier:** evaluate no-alignment thresholds, multi-label options, alternative descriptors and a keyword baseline. Report per-label precision/recall/F1, macro metrics and confusion matrices.
6. **Statistical robustness:** rerun inference on the five actual faculties; check sparse expected counts and effect sizes; quantify thematic dispersion, neighborhood mixing and topic trends without treating projected UMAP hull areas as physical quantities.
7. **Reporting:** generate all manuscript tables and figures from one versioned analysis dataset. Deposit only release-cleared research materials in an archival repository after review.

See `docs/REVIEW_PLAN.md` for the reviewer-to-analysis checklist and `docs/HPC_SYNC.md` for safe HPC synchronization. A stage-level audit, `scripts/audit_pipeline_provenance.py`, examines original pipeline attrition, SDG4 classifications by faculty, score margins and k-selection results. A third script, `scripts/audit_token_truncation.py`, measures the legacy E5 tokenizer's 512-token cutoff without exporting thesis text. Automated tests use synthetic data only.

## Source provenance

The submitted supplementary archive includes `utn_atlas_pipeline.py`, `utn_harvest_full_v2.py`, `utn_atlas_q1_extras.py` and notebooks. Their archived execution is **not** evidence that all proposed revisions have been completed. Original scripts will be maintained separately from corrected analyses, with no silent modification of historical outputs.
