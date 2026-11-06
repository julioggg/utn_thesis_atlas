"""Synthetic orchestration guards; no CEDIA data or external jobs executed."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from run_reviewer_computational_suite import parse_stages,STAGES


class SuiteTests(unittest.TestCase):
    def test_default_stages_are_unique_and_known(self):
        s=parse_stages("stats,geometry,stability,figures,inventory,alternate")
        self.assertEqual(len(s),6)
        self.assertTrue(set(s).issubset(STAGES))

    def test_all_includes_gated_descriptors(self):
        s=parse_stages("all")
        self.assertIn("descriptors",s)
        self.assertIn("keywords",s)
        self.assertIn("template",s)

    def test_bad_stage_and_duplicates_rejected(self):
        for query in ("stats,stats","stats,nothing",""):
            with self.assertRaises(ValueError):
                parse_stages(query)


if __name__=="__main__":
    unittest.main()
