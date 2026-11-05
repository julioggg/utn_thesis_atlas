"""Synthetic-only tests of the pipeline provenance audit; no real thesis records."""
import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_pipeline_provenance import main_audit

class StageAuditTests(unittest.TestCase):
    def test_disclosure_minimized_counts_and_margins(self):
        import numpy as np
        import pandas as pd
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            def write(rel, frame):
                dest = root / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                frame.to_parquet(dest, index=False)
            write("data/metadata/01_items_metadata.parquet", pd.DataFrame({
                "handle_id": ["demo1", "demo2", "demo3"],
                "title": ["private title one", "", ""],
                "authors": ["private author one", "", ""],
                "faculty": ["Faculty A", "Faculty B", None],
                "advisor": ["private advisor one", "private advisor two", None],
                "n_pdfs": [1, 1, 0],
                "ok": [True, True, False],
            }))
            write("data/metadata/02_pdf_downloads.parquet", pd.DataFrame({
                "handle_id": ["demo1", "demo2"], "download_ok": [True, False], "size": [900, 0],
            }))
            write("data/metadata/03_text_extraction.parquet", pd.DataFrame({
                "handle_id": ["demo1"], "extract_ok": [True], "chars": [1200], "pages": [3],
            }))
            write("data/processed/04_clean_corpus.parquet", pd.DataFrame({
                "handle_id": ["demo1", "demo2"], "text_hash": ["a", "a"],
                "analysis_text": ["secret abstract one", "secret abstract two"],
                "fulltext_chars": [7000, 9000],
            }))
            write("data/processed/06_corpus_with_topics.parquet", pd.DataFrame({
                "handle_id": ["demo1", "demo2"], "topic": [1, 2],
            }))
            write("data/processed/07_alignment_pdot_ods_needs.parquet", pd.DataFrame({
                "handle_id": ["demo1", "demo2"], "faculty": ["Faculty A", "Faculty B"],
                "ods_top1": ["ODS 4 Educación", "ODS 9 Industria"],
                "ods_top1_score": [.80, .75], "ods_top2_score": [.79, .71],
                "pdot_top1_score": [.81, .77], "pdot_top2_score": [.78, .72],
                "need_top1_score": [.83, .76], "need_top2_score": [.79, .73],
            }))
            dest = root / "data/processed/05_embeddings.npy"
            np.save(dest, np.ones((2, 1024), dtype=np.float32) / np.sqrt(1024))
            results = root / "reports/06_k_optimization.csv"
            results.parent.mkdir(parents=True)
            pd.DataFrame({"k": [50, 75], "silhouette_cosine_sample": [.1, .2]}).to_csv(results, index=False)

            audit = main_audit(root)
            self.assertEqual(audit["stages"]["metadata"]["rows"], 3)
            self.assertEqual(audit["stages"]["downloads"]["download_success_rows"], 1)
            self.assertEqual(audit["stages"]["clean"]["repeated_text_prefix_hash_rows"], 1)
            self.assertEqual(audit["classification"]["sdg4_by_faculty"], [])  # suppress tiny groups
            self.assertEqual(audit["k_selection"]["best_k"], 75)
            self.assertEqual(audit["embeddings"]["shape"], [2, 1024])
            sanitized = json.dumps(audit)
            for secret in ["private title one", "private author one", "private advisor one",
                           "secret abstract one", str(root)]:
                self.assertNotIn(secret, sanitized)

if __name__ == "__main__":
    unittest.main()
