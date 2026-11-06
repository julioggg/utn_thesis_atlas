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

## Implementación computacional preparada (2026-11-06)

**Advertencia de estado:** las pruebas sintéticas CI pasan, pero los nuevos módulos enumerados a continuación aún NO tienen resultados del corpus privado en CEDIA. Los archivos originales de 7.830 tesis y las dos GPU MIG solo están accesibles desde la sesión CEDIA del investigador.

| Bloque | Código ya implementado | Prueba real |
|---|---|---|
| Cinco facultades, imputación por carrera, asociación con residuos y permutaciones, V, Kruskal ε², post hoc, entropía rarefactada | `reviewer_stage1_stats.py` | Pendiente en CEDIA |
| Distribuciones top1, márgenes top2 y abstención exploratoria | `reviewer_stage1_stats.py` | Pendiente en CEDIA; calibración humana aún no |
| Centroides originales, k-NN, Rao-Stirling, puentes y tendencias excluyendo 2026 | `reviewer_stage2_geometry.py` | Pendiente en CEDIA |
| Variación de k=50/75/100, semillas KMeans y UMAP | `reviewer_stage3_stability.py` | Pendiente en CEDIA; análisis alternativo, no reproducción original |
| Regenerar Tabla 2, figura SDG, figura PDOT y figura de diez necesidades | `reviewer_rebuild_figures.py` | Pendiente en CEDIA; salidas de base legacy no validada |
| Inventariar descriptores y preparar manifiesto sin inventar sus textos | `reviewer_descriptor_inventory.py`, `reviewer_prepare_descriptors.py` | Pendiente en CEDIA |
| Descriptor paraphrases, top2/multi-label candidate, mean-centering | `reviewer_descriptor_sensitivity.py` | **Bloqueado** hasta recuperar y validar fuentes reales |
| Baseline léxico TF-IDF | `reviewer_keyword_baseline.py` | **Bloqueado** hasta recuperar y validar fuentes reales |
| Segundo modelo E5-base frente a E5-large, mismos textos completos | `reviewer_alternate_encoder_pilot.py` | Pendiente en CEDIA; puede requerir descarga |
| Regeneración completa E5-large de 7.830 tesis con dos MIG y checkpoints atómicos | `reviewer_full_corpus_two_mig.py` | Pendiente; requiere lanzamiento explícito del investigador |
| Kappa, F1, precision y recall, calibración vs test independiente | `reviewer_human_validation_metrics.py` | **Bloqueado**: dos evaluadores y adjudicación todavía sin hacer |

Ver **[instrucciones de la suite](COMPUTATIONAL_REVIEW_RUNBOOK_ES.md)** y **[pipeline completo de E5](FULL_CORPUS_TWO_MIG_ES.md)**. Los resultados originales ya auditados (procedencia, truncamiento, censo de 854.145 ventanas, pilotos 1 y 12 tesis, 450 fichas temáticas y 80 fichas estructurales) permanecen como línea base; **no sobrescribirlos**.

La publicación final todavía requiere validar legalidad/licencias, el PDOT específico, la fuente de diez necesidades, calidad de metadatos y tipos de tesis, corregir redacción/bibliografía y contestar a los cuatro revisores con números y localizaciones verificables.
