"""Pure-logic tests for disjoint two-MIG pilot distribution; no GPUs needed."""
import sys
import unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from pilot_fulltext_embeddings import shard_indices, choose_indices
from run_two_mig_pilot import discover_mig_slots


class MultiMigTests(unittest.TestCase):
    def test_indices_are_disjoint_and_complete(self):
        sample = choose_indices(list(range(1, 101)), 12)
        left = shard_indices(sample, 0, 2)
        right = shard_indices(sample, 1, 2)
        self.assertEqual(len(left), 6)
        self.assertEqual(len(right), 6)
        self.assertFalse(set(left) & set(right))
        self.assertEqual(set(left) | set(right), set(sample))

    def test_single_worker_compatibility(self):
        s = [31, 18, 72, 5]
        self.assertEqual(shard_indices(s, 0, 1), s)
        with self.assertRaises(ValueError):
            shard_indices(s, 2, 2)

    @mock.patch("subprocess.run")
    def test_mig_slot_selection(self, proc):
        proc.return_value.stdout = (
            "GPU 0: NVIDIA A100 (UUID: GPU-test)\n"
            "  MIG 2g.10gb Device 0: (UUID: MIG-aaa)\n"
            "  MIG 2g.10gb Device 1: (UUID: MIG-bbb)\n"
        )
        self.assertEqual(discover_mig_slots(), ["MIG-aaa", "MIG-bbb"])

    @mock.patch("subprocess.run")
    def test_not_run_if_only_one_mig(self, proc):
        proc.return_value.stdout = (
            "GPU 0: NVIDIA A100 (UUID: GPU-test)\n"
            "  MIG 2g.10gb Device 0: (UUID: MIG-aaa)\n"
        )
        with self.assertRaises(RuntimeError):
            discover_mig_slots()


if __name__ == "__main__":
    unittest.main()
