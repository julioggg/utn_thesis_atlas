"""Synthetic PDOT lineage analysis without executing original source scripts."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from reviewer_pdot_source_lineage import (
    compare_source_candidates, statically_trace
)
from reviewer_shared import sha256_file


class PDOTLineageTests(unittest.TestCase):
    def prepare(self, root, mismatch=True):
        source = root / "utn_atlas_pipeline.py"
        extras = root / "utn_atlas_q1_extras.py"
        original = {f"Axis {i}":f"PDOT source descriptor about {i}"
                    for i in range(1,7)}
        alternative = original.copy()
        if mismatch:
            alternative["Axis 3"] = "Different text for category 3"
        source.write_text(
            "PDOT = " + repr(original) +
            "\ndef scoring():\n    return list(PDOT.items())\n",
            encoding="utf-8",
        )
        extras.write_text(
            "PDOT_MAP = " + repr(alternative) +
            "\ndef extra():\n    return list(PDOT_MAP.items())\n",
            encoding="utf-8",
        )
        return {
            "status":"unverified_ast_descriptor_candidates",
            "literal_candidates":[
                {"relative_source_path":source.name,"variable_name":"PDOT",
                 "number_of_entries":6,"candidate_literal":original},
                {"relative_source_path":extras.name,"variable_name":"PDOT_MAP",
                 "number_of_entries":6,"candidate_literal":alternative},
            ],
            "candidate_source_inventory":[
                {"relative_path":p.name, "sha256":sha256_file(p)}
                for p in (source,extras)
            ],
        }

    def test_detect_real_changes_and_source_references(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            inv = self.prepare(root)
            sources, rows, counts = compare_source_candidates(inv,root)
            self.assertEqual(counts["exact_text_disagreements"],1)
            self.assertEqual(counts["normalized_text_disagreements"],1)
            self.assertEqual(sum(not x["same_exact_text"] for x in rows),1)
            self.assertEqual(sources["PDOT"]["trace"]["direct_load_reference_count"],1)
            self.assertIn("original_descriptor_PRIVATE",rows[0])

    def test_identical_descriptors_report_no_conflict(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            inv=self.prepare(root,mismatch=False)
            _,_,counts=compare_source_candidates(inv,root)
            self.assertEqual(counts["exact_text_disagreements"],0)

    def test_reject_modified_original_script(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            inv=self.prepare(root)
            (root/"utn_atlas_pipeline.py").write_text("PDOT={}\n")
            with self.assertRaisesRegex(ValueError, "changed"):
                compare_source_candidates(inv,root)

    def test_static_reference_is_not_execution(self):
        script = (
            "PDOT={'a':'b'}\n"
            "def example():\n"
            "    return PDOT.get('a')\n"
        )
        report=statically_trace(script,"PDOT")
        self.assertEqual(report["direct_load_reference_count"],1)
        self.assertEqual(report["references_private"][0]["scope"],[
            ["function","example"]
        ])


if __name__ == "__main__":
    unittest.main()
