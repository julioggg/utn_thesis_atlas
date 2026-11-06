# Full-text E5 GPU pilot

The verified full-corpus audit found that all 7,830 constructed legacy inputs exceeded 512 E5 tokens. A 48-thesis sample suggests about 1.02 million 384-token windows for full-text encoding, but the estimate has sampling uncertainty.

The next stage is an environment probe, followed by a three-document GPU pilot after CUDA-enabled PyTorch is available in an allocated CEDIA GPU job. Run full-text encoding only after confirming that the requested model fits memory and every input obeys the 512-token limit.

The pilot stores all document-level embeddings and source indices under ignored data/ storage on CEDIA. Only aggregate throughput, memory and token-coverage metrics should be published. It does not demonstrate ODS/PDOT classification accuracy; a blinded expert-coded validation set is still required.

## CEDIA R535 and two MIG devices

The A100 is one physical GPU subdivided into two 2g.10gb MIG compute instances. NVIDIA driver 535 permits only a single MIG instance per CUDA process. To exercise both, start two separate processes with distinct CUDA_VISIBLE_DEVICES=MIG-UUID values; do not expect torch.cuda.device_count() == 2 in one process. First install CUDA 12.1 PyTorch in the dedicated virtual environment and use scripts/probe_mig_instances.py to test both slots independently. The script redacts UUIDs in its JSON report.

## Verified CEDIA environment (2026-11-06)

- A100 hardware with two separately visible MIG 2g.10gb compute instances; each Python subprocess reported 9.62 GiB visible VRAM.
- PyTorch 2.5.1+cu121 on Python 3.10; successful CUDA addition on both MIG instances. No need to reinstall CUDA or Singularity.
- On NVIDIA R535, run one CUDA process per MIG when parallelizing; a single process enumerating one GPU is expected.
- `intfloat/multilingual-e5-large` has safetensors weights. The first inference run may download the model weights to the local Hugging Face cache.

### First real inference: one thesis only

Start in the revision clone with the existing audit environment activated. This is a **GPU inference experiment**, not yet a validation result.

```bash
cd "$HOME/utn_thesis_atlas_revision"
git pull --ff-only origin main
source "$HOME/.venvs/utn-atlas-audit/bin/activate"
python -c "import torch; from transformers import AutoModel; print(torch.cuda.is_available())"
python scripts/pilot_fulltext_embeddings.py \\
  --project-root "$HOME/utn_thesis_atlas" \\
  --documents 1 --batch-size 1 --chunk-tokens 384 --overlap 48 \\
  --max-chunks 160 --precision fp16 --device cuda \\
  --output docs/audits/gpu_pilot_report.json
```

The aggregated JSON report may be reviewed for public release. Do **not** upload `data/revision_private/gpu_pilot/gpu_pilot_vectors.npz` or source full texts. If CUDA memory fails, stop and report the redacted error rather than raising batch size.
