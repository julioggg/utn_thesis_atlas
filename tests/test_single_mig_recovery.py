"""Synthetic tests only: verify one-MIG resume reuses frozen two-shard checkpoints."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from reviewer_full_corpus_two_mig import atomic_checkpoint
from resume_fulltext_one_mig import read_frozen_run, verify_existing_shards
from reviewer_shared import sha256_file


class SingleMigRecoveryTests(unittest.TestCase):
    def prepare(self, root):
        workspace = root / "revision"
        project = root / "atlas"
        (project / "data/processed").mkdir(parents=True)
        src = project / "data/processed/04_clean_corpus.parquet"
        src.write_bytes(b"TEST PARQUET HASH SOURCE; only a mock here")
        (workspace / "scripts").mkdir(parents=True)
        corpus_script = workspace / "scripts/reviewer_full_corpus_two_mig.py"
        encoder_script = workspace / "scripts/pilot_fulltext_embeddings.py"
        corpus_script.write_text("# synthetic model script\n")
        encoder_script.write_text("# synthetic encoder script\n")
        run_dir = workspace / "data/revision_private/fulltext_e5_large_v1"
        run_dir.mkdir(parents=True)
        manifest = {
            "schema_version": 1,
            "original_root": str(project.resolve()),
            "model_hf_revision_sha": "deadbeef1234567890",
            "original_04_parquet_sha256": sha256_file(src),
            "code_fingerprints": {
                "full_corpus_script": sha256_file(corpus_script),
                "e5_window_encoder_script": sha256_file(encoder_script),
            },
            "population_rows": 7830,
            "model": "intfloat/multilingual-e5-large",
            "chunk_tokens": 384,
            "overlap_tokens": 48,
            "batch_size": 1,
            "max_chunks_per_document": 1500,
            "documents_per_checkpoint": 16,
            "precision": "fp16",
            "pooling": "length-weighted chunk mean of normalized embeddings, L2 document norm",
        }
        (run_dir / "run_parameters_PRIVATE.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        return workspace, project, run_dir

    def test_verify_existing_two_shards_independently(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace, project, run_dir = self.prepare(Path(tmp))
            manifest, _, fingerprint = read_frozen_run(workspace, project, run_dir)
            for slot in (0, 1):
                v = np.zeros((16, 1024), dtype=np.float32)
                v[:, slot] = 1
                atomic_checkpoint(
                    run_dir / f"mig_slot{slot}/batch_0000.npz",
                    np.arange(16, dtype=np.int64) * 2 + slot,
                    v, np.ones(16, dtype=np.int64)*20,
                    np.ones(16, dtype=np.int64)*2,
                    fingerprint,
                )
            reports = verify_existing_shards(run_dir, manifest, fingerprint)
            self.assertEqual(sum(s["completed_documents"] for s in reports), 32)
            self.assertEqual(reports[0]["valid_checkpoint_blocks"], 1)
            self.assertEqual(reports[1]["valid_checkpoint_blocks"], 1)
            self.assertEqual(reports[0]["total_expected_blocks"], 245)
            self.assertEqual(reports[0]["remaining_documents"], 3915-16)

    def test_reject_changed_source_code_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace, project, run_dir = self.prepare(Path(tmp))
            read_frozen_run(workspace, project, run_dir)
            (workspace / "scripts/reviewer_full_corpus_two_mig.py").write_text(
                "# altered script\n"
            )
            with self.assertRaisesRegex(ValueError, "SHA256"):
                read_frozen_run(workspace, project, run_dir)

    def test_reject_changed_corpus_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace, project, run_dir = self.prepare(Path(tmp))
            (project / "data/processed/04_clean_corpus.parquet").write_bytes(
                b"Different extracted text"
            )
            with self.assertRaisesRegex(ValueError, "parquet SHA256"):
                read_frozen_run(workspace, project, run_dir)


if __name__ == "__main__":
    unittest.main()
