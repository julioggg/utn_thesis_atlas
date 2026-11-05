"""Synthetic tests for full-text token window arithmetic."""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_chunk_budget import chunk_count

class ChunkWindowTests(unittest.TestCase):
    def test_chunk_boundaries(self):
        self.assertEqual(chunk_count(0, 384, 48), 0)
        self.assertEqual(chunk_count(1, 384, 48), 1)
        self.assertEqual(chunk_count(384, 384, 48), 1)
        self.assertEqual(chunk_count(385, 384, 48), 2)
        self.assertEqual(chunk_count(720, 384, 48), 2)
        self.assertEqual(chunk_count(721, 384, 48), 3)

    def test_bad_config(self):
        for size, overlap in [(384,384), (0,0), (384,-1)]:
            with self.assertRaises(ValueError):
                chunk_count(1000, size, overlap)

if __name__ == "__main__":
    unittest.main()
