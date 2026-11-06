"""Synthetic parsing tests; no GPU required."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from probe_mig_instances import detect_mig_uuids

class MIGProbeTests(unittest.TestCase):
    def test_two_mig_instances(self):
        output = """GPU 0: NVIDIA A100-SXM4-40GB (UUID: GPU-example)
  MIG 2g.10gb Device 0: (UUID: MIG-abc-111)
  MIG 2g.10gb Device 1: (UUID: MIG-def-222)
"""
        self.assertEqual(detect_mig_uuids(output), ["MIG-abc-111", "MIG-def-222"])

    def test_deduplicate_and_no_mig(self):
        self.assertEqual(detect_mig_uuids("GPU 0 (UUID: GPU-test)"), [])
        self.assertEqual(detect_mig_uuids(
            "MIG x (UUID: MIG-aa)\nMIG x (UUID: MIG-aa)"), ["MIG-aa"])

if __name__ == "__main__":
    unittest.main()
