"""Synthetic-only tests: protect positional provenance and private embeddings."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_embedding_comparison import comparison, check_row_alignment


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        import numpy as np
        import pandas as pd
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "original"
        self.workspace = Path(self.temp.name) / "revision"
        for name in ("04_clean_corpus", "06_corpus_with_topics",
                     "07_alignment_pdot_ods_needs"):
            dst = self.root / "data/processed" / (name + ".parquet")
            dst.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame({"handle_id": ["secret-A", "secret-B", "secret-C", "secret-D"]}).to_parquet(dst)
        embeddings = np.eye(4, 1024, dtype=np.float32)
        np.save(self.root / "data/processed/05_embeddings.npy", embeddings)
        self.run_id = "synthetic"
        out = self.workspace / "data/revision_private/dual_mig_pilot"
        for slot, indices in [(0, [0, 2]), (1, [1, 3])]:
            target = out / f"{self.run_id}_slot{slot}"
            target.mkdir(parents=True)
            np.savez(target / "gpu_pilot_vectors.npz",
                     row_indices=np.asarray(indices, dtype=np.int64),
                     vectors=embeddings[indices])
            audit = self.workspace / "docs/audits"
            audit.mkdir(parents=True, exist_ok=True)
            (audit / f"{self.run_id}_slot{slot}.json").write_text(
                json.dumps({"documents_processed": 2}))

    def tearDown(self):
        self.temp.cleanup()

    def test_full_alignment_and_aggregate_output(self):
        actual = comparison(self.root, self.workspace, self.run_id)
        self.assertEqual(actual["n_pilot_theses"], 4)
        self.assertEqual(actual["alignment_verified"], {"04_vs_06": True, "04_vs_07": True})
        self.assertAlmostEqual(actual["original_new_same_thesis_cosine"]["mean"], 1.0)
        output = json.dumps(actual)
        self.assertNotIn("secret-A", output)
        self.assertNotIn(str(self.root), output)
        self.assertNotIn("row_indices", output)

    def test_order_mismatch_refused(self):
        import pandas as pd
        path = self.root / "data/processed/07_alignment_pdot_ods_needs.parquet"
        pd.DataFrame({"handle_id": ["secret-B", "secret-A", "secret-C", "secret-D"]}).to_parquet(path)
        with self.assertRaises(ValueError):
            check_row_alignment(self.root)

    def test_duplicate_indices_refused(self):
        import numpy as np
        path = self.workspace / "data/revision_private/dual_mig_pilot" / (
            f"{self.run_id}_slot1/gpu_pilot_vectors.npz")
        np.savez(path, row_indices=np.array([0, 3]), vectors=np.eye(4, 1024)[[0, 3]])
        with self.assertRaises(ValueError):
            comparison(self.root, self.workspace, self.run_id)


if __name__ == "__main__":
    unittest.main()
