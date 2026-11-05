import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from hpc_inventory import inventory

class InventoryTests(unittest.TestCase):
    def test_inventory_does_not_include_absolute_path_or_personal_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "data/processed").mkdir(parents=True)
            (root / "data/processed/04_clean_corpus.parquet").write_bytes(b"fake")
            (root / "data/pdfs").mkdir(parents=True)
            (root / "data/pdfs/student_private.pdf").write_bytes(b"private")
            result = inventory(root)
            self.assertTrue(result["known_file_locations"][
                "data/processed/04_clean_corpus.parquet"]["exists"])
            payload = json.dumps(result)
            self.assertNotIn(temp, payload)
            self.assertNotIn("student_private.pdf", payload)

if __name__ == "__main__":
    unittest.main()
