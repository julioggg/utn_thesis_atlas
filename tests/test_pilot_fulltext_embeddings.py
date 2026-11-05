"""CPU-only synthetic tests for pilot selection and exact token coverage."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from pilot_fulltext_embeddings import choose_indices, extract_rows, windows

class FakeTokenizer:
    def build_inputs_with_special_tokens(self, content):
        return [0] + content + [2]

class FullTextPilotTests(unittest.TestCase):
    def test_complete_coverage_and_max_length(self):
        tok = FakeTokenizer()
        for n in (1, 384, 385, 720, 721, 1000, 5000):
            token_ids = list(range(n))
            sequence = list(windows(token_ids, 384, 48, [101, 102], tok))
            self.assertEqual(sum(weight for _, weight in sequence), n)
            self.assertTrue(all(0 < weight <= 384 for _, weight in sequence))
            self.assertTrue(all(len(s) <= 512 for s, _ in sequence))
            self.assertEqual(sequence[0][1], min(n, 384))

    def test_length_quantile_sampling_is_unique(self):
        indices = choose_indices([10, 100, 30, 200, 40, 90, 80], 3)
        self.assertEqual(len(indices), 3)
        self.assertEqual(len(set(indices)), 3)
        self.assertTrue(set(indices).issubset(set(range(7))))

    def test_read_original_parquet_not_derived_short_text(self):
        import pandas as pd
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "private.parquet"
            pd.DataFrame({
                "full_text": ["thesis alpha", "thesis beta", "thesis gamma"],
                "analysis_text": ["short alpha", "short beta", "short gamma"],
            }).to_parquet(src, index=False)
            rows = extract_rows(src, [0, 2])
            self.assertEqual(rows, {0: "thesis alpha", 2: "thesis gamma"})
            self.assertNotIn("short alpha", list(rows.values()))

if __name__ == "__main__":
    unittest.main()
