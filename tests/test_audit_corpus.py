import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

class AggregateAuditTests(unittest.TestCase):
    def test_audit_is_aggregate_only(self):
        import pandas as pd
        from audit_corpus import run
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "data/processed/07_alignment_pdot_ods_needs.parquet"
            path.parent.mkdir(parents=True)
            pd.DataFrame({
                "handle_id": [11, 12, 12],
                "year": [2024, 2025, 2026],
                "faculty": ["Engineering", "Engineering", "Unassigned"],
                "advisor": ["Fake Tutor A", "Fake Tutor B", "Fake Tutor B"],
                "title": ["Private thesis title A", "Private thesis title B", "Private thesis title C"],
                "analysis_text": ["Confidential sample 1", "Confidential sample 2", "Confidential sample 3"],
                "ods_top1": ["SDG 4", "SDG 9", "SDG 4"],
                "ods_top1_score": [0.4, 0.8, 0.3],
            }).to_parquet(path, index=False)
            payload = run(root)
            self.assertEqual(payload["row_count"], 3)
            self.assertEqual(payload["duplicate_handles"], 1)
            self.assertEqual(payload["ods_assigned"], 3)
            body = json.dumps(payload)
            for private in ["Fake Tutor A", "Fake Tutor B", "Private thesis title", "Confidential sample"]:
                self.assertNotIn(private, body)

if __name__ == "__main__":
    unittest.main()
