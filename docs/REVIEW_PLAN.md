# Major revision work plan and reviewer traceability

Status: not completed. Editor decision 2026-11-03: major revision.

## Phase 0 — HPC recovery and reproducibility (critical)

- [ ] Record source snapshot, dependencies, seeds and code version.
- [ ] Reconcile harvested, downloaded, text-extracted, cleaned and final analytical counts (7,830 in manuscript).
- [ ] Audit full-thesis extraction versus legacy first-14,000-character selection and E5 512-token input limits.
- [ ] Locate actual original k=75 silhouette results and verify they match the manuscript.
- [ ] Reconcile Table 2, Figure 3, Figure 5 and the differing population totals.

## Phase 1 — classification validation (critical; reviewers 1–4)

- [ ] Record SDG, Imbabura PDOT and 10 local-needs descriptors with their provenance.
- [ ] Stratified sample target 400–500 theses; independent blinded annotation by two human coders.
- [ ] Adjudicate disagreements; calculate Cohen kappa and per-class/macro precision, recall, F1.
- [ ] Build threshold/no-match and multi-label comparisons; calibrate separately from evaluation.
- [ ] Compare chunked full-text E5 versus legacy E5 and a keyword baseline.
- [ ] Quantify SDG4 inflation (academic boilerplate, cross-faculty false positives).
- [ ] Sensitivity to descriptor wording, another embedding model and different seeds.

## Phase 2 — statistics and interpretation (reviewers 1–4)

- [ ] Correct faculty metadata; separate five real faculties from unassigned/miscellaneous labels.
- [ ] Audit chi-square expected counts, effect sizes, residuals and corrected post hoc tests.
- [ ] Replace unvalidated 'originality' claims with semantic atypicality/dispersion as appropriate.
- [ ] Replace UMAP hull area/overlap inferences with original-space centroid/k-NN mixing metrics.
- [ ] Re-evaluate bridge-topic thresholds and minimum counts.
- [ ] Correct 2026 trend interpretation and report valid uncertainty.
- [ ] Clarify coverage-index formula and whether it adds information beyond prevalence.

## Phase 3 — scientific paper (reviewers 1–4, editor)

- [ ] New single-institution title without 7,830 in title.
- [ ] Clearly separate semantic thematic alignment from proven sustainability impact.
- [ ] Full methodological framework and Ecuador/Imbabura policy context.
- [ ] Explain thesis categories, sampling, extraction, missingness and ethical data handling.
- [ ] Bibliography audit (notably duplicated reference 3/18), citation style and nomenclature.
- [ ] Regenerate every table and figure from one versioned analysis.
- [ ] Data availability and code release with protected data policy.
- [ ] Point-by-point reviewer response with exact manuscript locations.

## Scientific release rule

Do not treat unvalidated embeddings as a human-labeled ground truth, or overwrite original HPC results. Public GitHub excludes record-level student/advisor information and copyrighted full theses.
