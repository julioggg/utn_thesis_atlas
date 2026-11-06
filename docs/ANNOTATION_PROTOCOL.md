# Human-validation protocol — 450 UTN theses (draft for ethics and expert approval)

**Purpose.** Create independent reference judgments on thematic relevance to the 17 UN Sustainable Development Goals (SDGs/ODS) and the six territorial-planning dimensions used in the original Imbabura PDOT mapping. The outcome measured here is **semantic thematic alignment**, not evidence of actual SDG achievement, policy impact, implementation or territorial benefit.

**Status.** Draft codebook and sampling workflow. NO human annotation has been performed. A scientific lead and two independent coders must approve the operational definitions before annotating. Confirm the exact provincial PDOT edition, official descriptions and legal/licensing permissions; the six names below are the taxonomy USED BY THE ORIGINAL PIPELINE, not newly verified official definitions.

## 1. Unit of analysis and sources

One thesis record is one annotation unit. Coders should inspect the full thesis when available (at least objectives, introduction/problem, methodology, results and conclusions). Do NOT choose labels from chapter index, acknowledgments, university headers, references/bibliography or generic mentions alone. Record missing or unreadable documents in the notes for coordinator review rather than guessing.

The original analytical corpus contains 7,830 unique handles. The initial automated pipeline force-assigned a top-1 label for every thesis. Human coders MUST have a genuine **no credible alignment** option.

The corpus includes some records with missing title/author metadata. The research coordinator will supply restricted-access documents based on the private handles. Annotation CSVs MUST NOT be uploaded to this public repo.

## 2. Sampling and privacy

Default sample size 450. Selection:

- 120 simple random records from the full population, for more representative population estimates.
- 330 additional distinct records with targeted enrichment by original predicted ODS class using a minimum-per-label and square-root-frequency allocation; within each class about one third are intentionally low-margin cases, with faculty diversity encouraged.
- No thesis appears more than once. Stratification uses original model labels **only in the restricted sampling program**. Those predictions and scores are not visible on coder sheets.
- All selection flags, original predicted labels and dataset positions remain in the private coordinator master sheet.
- The two coder sheets are independently shuffled and contain only study ID, a restricted document access handle, and empty annotation fields.

**Inferential caution:** the enriched subset is not a representative random sample. Always report the sampling design; do not interpret raw pooled label proportions as population prevalence. The 120 probability-sample records are a separate prevalence check with finite-sample uncertainty; detailed class error estimates from enrichment require explicit design-aware treatment. Rare ODS strata will have wide confidence intervals even if overrepresented.

**Data governance:** grant only authorized coders access to full theses, preserve institutional approval and intellectual-property licensing requirements, avoid public row-level exports, and retain a versioned adjudication record in restricted storage.

## 3. ODS label codebook (taxonomy identifiers)

Use the 17 ODS categories identified in the existing pipeline, with internationally standardized goals:

| Code | Category |
|---|---|
| ODS 1 | Fin de la pobreza |
| ODS 2 | Hambre cero |
| ODS 3 | Salud y bienestar |
| ODS 4 | Educación de calidad |
| ODS 5 | Igualdad de género |
| ODS 6 | Agua limpia y saneamiento |
| ODS 7 | Energía asequible y no contaminante |
| ODS 8 | Trabajo decente y crecimiento económico |
| ODS 9 | Industria, innovación e infraestructura |
| ODS 10 | Reducción de las desigualdades |
| ODS 11 | Ciudades y comunidades sostenibles |
| ODS 12 | Producción y consumo responsables |
| ODS 13 | Acción por el clima |
| ODS 14 | Vida submarina |
| ODS 15 | Vida de ecosistemas terrestres |
| ODS 16 | Paz, justicia e instituciones sólidas |
| ODS 17 | Alianzas para lograr los objetivos |

**Primary label:** the one ODS whose substantive target is most directly represented by the thesis's research questions, objectives, evaluated intervention or analytical results. **Secondary label:** one optional additional ODS supported by clear direct evidence. Secondary labels should not be inferred merely because a method could someday have applications. **No match:** choose when none has credible substantive support.

Special ODS 4 bias instruction: university origin, mention of students, thesis methodology or ordinary pedagogical vocabulary do NOT establish ODS 4. Only learning/education-focused research objectives or outcomes justify it.

If a thesis actually studies multiple ODS, code primary + secondary without restricting multi-label scope to a single goal.

## 4. PDOT dimensions used by the original semantic model

These are the original six prediction axes, pending review against the actual source PDOT document:

| Code | Atlas label |
|---|---|
| PDOT 1 | Sistema Físico Ambiental |
| PDOT 2 | Sistema Socio Cultural |
| PDOT 3 | Sistema Económico Productivo |
| PDOT 4 | Asentamientos Humanos Movilidad Energía Conectividad |
| PDOT 5 | Sistema Político Institucional |
| PDOT 6 | Ejes Transversales |

Determine thematic alignment from specific research questions and results, **not** an assumed policy benefit. A thesis conducted in Imbabura is not automatically aligned to PDOT. Do not count "Ejes Transversales" merely as a default fallback. Primary, optional secondary, and **no credible alignment** are available.

## 5. Independent coding and adjudication

1. Train coders with ~20 pilot theses outside the final evaluation sample; refine the frozen codebook together before scoring the 450 records.
2. Coder A and B independently fill their CSVs with primary/secondary ODS and PDOT, no-match flags and concise evidence locations. Neither sees model predictions or the other coder's judgments.
3. The coordinator resolves missing/unreadable records by a prespecified protocol without substituting automated labels.
4. Freeze both completed coder datasets before discussing disagreements. Compute agreement: Cohen's kappa separately for primary ODS and PDOT including no-match, and explicit multi-label agreement for secondary choices. Report complete confusion matrices and class sizes.
5. Adjudicate unresolved items with a third trained evaluator or documented consensus, blinded to model predictions. Never overwrite the original coding sheets; store a separate final reference table.
6. Before inspecting model results, predefine a calibration subset and held-out test subset. Report per-label precision/recall/F1, macro and weighted averages, sample uncertainty, abstention coverage and sensitivity to class weighting. Compare original E5, full-text E5, a keyword baseline and descriptor variants.

**Do not describe a low Cohen kappa as good model performance or an adjudicated consensus as independently observed agreement.** Report both coder reliability and model-vs-adjudicated reference accuracy.

## 6. Private files generated on CEDIA

Run scripts/prepare_blinded_validation_sample.py from the revision clone:

- data/revision_private/validation/sample_master_private.csv — restricted coordinator only; includes original predictions and selection strata.
- data/revision_private/validation/coder_A_private.csv — blinded coder A sheet.
- data/revision_private/validation/coder_B_private.csv — blinded coder B sheet.
- docs/audits/validation_sample_design.json — aggregate sample design only; suitable for public review after inspection.

The CSV files belong to the private research workflow. Do not push them to GitHub or send unencrypted to third parties.
