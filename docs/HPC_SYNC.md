# CEDIA HPC to GitHub — first synchronization

This repository is PUBLIC. Never copy the entire original project into GitHub. Store PDFs, extracted text, thesis/advisor/student metadata, embeddings, row-level assignments, logs with names and credentials on approved HPC storage.

## A. On HPC: find the original project

Run from the directory where the old project folder exists:

    pwd
    realpath utn_thesis_atlas

Save that absolute path **only in your terminal**, not in a public issue or GitHub report.

## B. Clone separately; protect the original

    ORIGINAL="$(realpath utn_thesis_atlas)"
    cd "$HOME"
    git clone https://github.com/julioggg/utn_thesis_atlas.git utn_thesis_atlas_revision
    cd utn_thesis_atlas_revision

Do not clone inside the old directory or overwrite any old scripts or data.

## C. Perform read-only audit

    python3 scripts/hpc_inventory.py --project-root "$ORIGINAL" --output reports/public/hpc_inventory.json
    python3 scripts/audit_corpus.py --project-root "$ORIGINAL" --output reports/public/corpus_audit.json

The inventory requires only the Python standard library. Corpus audit requires pandas and pyarrow in the active environment. If dependencies are missing, activate the existing research environment; do not modify the shared system Python.

    cat reports/public/hpc_inventory.json
    cat reports/public/corpus_audit.json

If an expected artifact exists elsewhere, rerun audit with --corpus /absolute/path/to/the/file.parquet. These commands never modify the old project.

## D. Publish ONLY the inspected aggregate results

    git status --short
    git add reports/public/hpc_inventory.json reports/public/corpus_audit.json
    git diff --cached --stat
    git diff --cached -- reports/public/
    git commit -m "Add aggregate HPC inventory and corpus audit"
    git push origin main

Use your existing GitHub SSH/HTTPS authentication. Never paste passwords or personal-access tokens into chat, shell command arguments or committed files. If push fails, report a sanitized error message.

## E. Next scientific stage

After the aggregate audit, the team will verify the analytical population, 2026 completeness, PDF and faculty coverage, embedding input lengths, label-score distributions, original k-selection and contradictory figure/table counts. Only then start GPU re-embedding and stratified expert evaluation.
