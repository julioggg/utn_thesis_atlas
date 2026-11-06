# Two-MIG E5 pilot: CEDIA benchmark

This is the next experiment after the successful one-thesis full-text E5 test (65 chunks; 21,849 tokens; 1.306 seconds of processing, excluding model loading; peak PyTorch allocation 1.06 GiB). The original thesis data stay on CEDIA.

## Objective

Determine whether two NVIDIA A100 MIG 2g.10gb compute instances can process DIFFERENT documents concurrently. This is a benchmark, not an SDG/PDOT validation study and not authorization for a 7,830-thesis rerun.

## Run from the existing Singularity shell

    cd "$HOME/utn_thesis_atlas_revision"
    git pull --ff-only origin main
    source "$HOME/.venvs/utn-atlas-audit/bin/activate"

    python scripts/run_two_mig_pilot.py \
      --project-root "$HOME/utn_thesis_atlas" \
      --run-id two_mig_pilot_v1 \
      --documents 12 \
      --batch-size 1 \
      --chunk-tokens 384 \
      --overlap 48 \
      --max-chunks 400 \
      --timeout-seconds 1200 \
      --local-files-only

Remove --local-files-only only if the model is not in the current Hugging Face cache and external downloading is authorized.

## Implementation and safety

The orchestrator reads nvidia-smi -L to find exactly two MIG compute-instance UUIDs, then launches two subprocesses concurrently. Each receives a different CUDA_VISIBLE_DEVICES value. On NVIDIA R535 a process is expected to see only one device. Both workers start from one shared, deterministic 12-document length-quantile selection, then split it into disjoint six-document shards. The workers never select identical row indices.

The token limit remains 512 (including E5 prefix and special tokens), with 384 content tokens and 48 tokens of overlap. The pooling method is a length-weighted mean of L2-normalized chunk vectors followed by document-level normalization. The tokenizer is allowed to read full texts, but thesis content is never uploaded to GitHub.

The wrapper puts three public-candidate aggregate reports in docs/audits:

- two_mig_pilot_v1_slot0.json
- two_mig_pilot_v1_slot1.json
- two_mig_pilot_v1_summary.json

Private logs and per-document vectors remain in ignored data/revision_private/dual_mig_pilot. Do NOT upload that directory, even if a process fails. Inference failures leave diagnostic logs there for local review.

If the pilot succeeds and the JSONs contain no sensitive content:

    cat docs/audits/two_mig_pilot_v1_summary.json
    git add docs/audits/two_mig_pilot_v1_slot0.json \
            docs/audits/two_mig_pilot_v1_slot1.json \
            docs/audits/two_mig_pilot_v1_summary.json
    python scripts/git_safety.py
    git diff --cached --stat
    git commit -m "Benchmark E5 full-text encoding across two MIG workers"
    git push origin main

If it fails, do not commit incomplete reports. Share the error message with secrets and private data redacted.

## What to measure

Use the real combined throughput (chunks / wall time INCLUDING model startup), per-GPU throughput (excluding model loading), memory allocated, processed/omitted documents, and token coverage. The benchmark estimates capacity, not classifier correctness or scientific contribution. A true model comparison requires a human gold standard and pre-specified evaluation protocol.
