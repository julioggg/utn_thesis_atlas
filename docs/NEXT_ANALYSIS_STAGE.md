# Next scientific gate after the 12-thesis dual-MIG pilot

Status: the dual-MIG pilot completed 12/12 documents, 1,199 E5 windows and 401,623 tokens in 22.626 seconds of wall time (including model loading). The measured combined rate was 52.992 windows/s; individual GPU processing rates excluding startup were 84.014 and 84.622 windows/s. This is infrastructure evidence, not model quality.

## Gate A — exact full-corpus window census (CPU)

Run census_fulltext_chunks.py on 04_clean_corpus.parquet with 384 content tokens and 48 overlap. The result reports the exact number of windows and the number of theses requiring more than 400/800/1200 windows. The 400-window cap was exclusively a pilot safety device. Never silently omit long theses in the final analysis.

## Gate B — baseline-versus-fulltext comparison (CPU)

Run audit_embedding_comparison.py on the 12 private pilot vectors. It requires the original 05_embedding_index.csv and verifies that handles align across stages 04, 05, 06, and 07 before comparing any embeddings. It outputs only aggregate cosine similarities and pairwise-rank diagnostics, not raw thesis vectors or IDs.

Differences between old and new embeddings are not measurements of correctness. Do not describe greater difference as improved quality.

## Gate C — scientifically designed human validation

Prepare a private sample of approximately 400-500 theses stratified across predicted SDG/PDOT groups, faculties, low-margin cases and rare labels. Two independent coders must assign reference labels without seeing model predictions. Include a valid no-alignment label and an adjudication protocol.

Evaluate per-label precision, recall and F1, macro averages, Cohen's kappa, uncertainty and calibration/hold-out separation. Compare legacy embeddings, chunked full-text embeddings and a simple keyword model; assess boilerplate and SDG 4 bias. The sample and raw annotations remain private on CEDIA until a data-governance review.

## Gate D — full pipeline

Only then use the two MIG GPUs for the entire corpus with deterministic sharding, per-document checkpointing, bounded temporary memory and an auditable index. Preserve the original 7,830-vectors and all earlier experiment outputs as untouched baselines.

### HPC commands

    cd "$HOME/utn_thesis_atlas_revision"
    git pull --ff-only origin main
    source "$HOME/.venvs/utn-atlas-audit/bin/activate"

    python scripts/audit_embedding_comparison.py \
      --project-root "$HOME/utn_thesis_atlas" \
      --workspace "$PWD" \
      --run-id two_mig_pilot_v1 \
      --output docs/audits/embedding_comparison_v1.json

    python scripts/census_fulltext_chunks.py \
      --project-root "$HOME/utn_thesis_atlas" \
      --local-files-only \
      --output docs/audits/fulltext_chunk_census.json

The files in docs/audits contain aggregate metrics only; review them before pushing to a public repository. Individual thesis text, row IDs, labels and vectors are never to be published without appropriate institutional authorization.
