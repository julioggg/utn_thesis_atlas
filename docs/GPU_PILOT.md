# Full-text E5 GPU pilot

The verified full-corpus audit found that all 7,830 constructed legacy inputs exceeded 512 E5 tokens. A 48-thesis sample suggests about 1.02 million 384-token windows for full-text encoding, but the estimate has sampling uncertainty.

The next stage is an environment probe, followed by a three-document GPU pilot after CUDA-enabled PyTorch is available in an allocated CEDIA GPU job. Run full-text encoding only after confirming that the requested model fits memory and every input obeys the 512-token limit.

The pilot stores all document-level embeddings and source indices under ignored data/ storage on CEDIA. Only aggregate throughput, memory and token-coverage metrics should be published. It does not demonstrate ODS/PDOT classification accuracy; a blinded expert-coded validation set is still required.

## CEDIA R535 and two MIG devices

The A100 is one physical GPU subdivided into two 2g.10gb MIG compute instances. NVIDIA driver 535 permits only a single MIG instance per CUDA process. To exercise both, start two separate processes with distinct CUDA_VISIBLE_DEVICES=MIG-UUID values; do not expect torch.cuda.device_count() == 2 in one process. First install CUDA 12.1 PyTorch in the dedicated virtual environment and use scripts/probe_mig_instances.py to test both slots independently. The script redacts UUIDs in its JSON report.
