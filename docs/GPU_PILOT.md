# Full-text E5 GPU pilot

The verified full-corpus audit found that all 7,830 constructed legacy inputs exceeded 512 E5 tokens. A 48-thesis sample suggests about 1.02 million 384-token windows for full-text encoding, but the estimate has sampling uncertainty.

The next stage is an environment probe, followed by a three-document GPU pilot after CUDA-enabled PyTorch is available in an allocated CEDIA GPU job. Run full-text encoding only after confirming that the requested model fits memory and every input obeys the 512-token limit.

The pilot stores all document-level embeddings and source indices under ignored data/ storage on CEDIA. Only aggregate throughput, memory and token-coverage metrics should be published. It does not demonstrate ODS/PDOT classification accuracy; a blinded expert-coded validation set is still required.
