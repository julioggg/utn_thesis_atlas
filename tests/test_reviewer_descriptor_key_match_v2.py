"""Synthetic source reconciliation tests with full SDG titles and competing PDOT."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from reviewer_descriptor_key_match_v2 import (
    normalized_ods_key, keyed_candidate, classify_sources, prefill_new_unverified,
)


def manifest():
    def rows(prefix, n):
        return [{
            "id": f"{prefix} {i}", "descriptor": "", "paraphrase_1": "",
            "paraphrase_2": "", "source_document": "", "source_location": "",
            "verified_by": ""
        } for i in range(1, n + 1)]
    return {
        "verified": False, "status": "TEMPLATE_REQUIRES_SOURCE_VERIFICATION",
        "taxonomies": {
            "ods": rows("ODS", 17), "pdot": rows("PDOT", 6),
            "need": rows("Need", 10),
        }
    }


def candidate(name, label, values):
    return {
        "relative_source_path": name, "variable_name": label,
        "number_of_entries": len(values), "candidate_literal": values,
    }


class DescriptorReconciliationV2Tests(unittest.TestCase):
    def setUp(self):
        self.source = {
            "status": "unverified_ast_descriptor_candidates",
            "literal_candidates": [
                candidate("utn_atlas_pipeline.py", "ODS", {
                    f"ODS {i} Titulo ficticio de objetivo {i}":
                        f"Texto original SDG {i}"
                    for i in range(1, 18)
                }),
                candidate("utn_atlas_pipeline.py", "PDOT", {
                    f"PDOT {i}": f"Texto PDOT {i}" for i in range(1, 7)
                }),
                candidate("utn_atlas_q1_extras.py", "PDOT_MAP", {
                    f"PDOT {i}": f"Texto PDOT {i}" for i in range(1, 7)
                }),
                candidate("utn_atlas_pipeline.py", "NEEDS", {
                    f"Need {i}": f"Texto necesidad {i}" for i in range(1, 11)
                }),
            ]
        }

    def test_sdg_number_prefix_is_unambiguous(self):
        self.assertEqual(
            normalized_ods_key("ODS 4 Educación de calidad"), "ODS 4"
        )
        self.assertEqual(normalized_ods_key("ODS 14 Vida submarina"), "ODS 14")
        self.assertIsNone(normalized_ods_key("ODS 18 No válido"))
        self.assertIsNone(normalized_ods_key("Fin de la pobreza"))

    def test_multiple_identical_pdot_sources_are_not_ambiguous(self):
        result = classify_sources(manifest(), self.source)
        self.assertEqual(
            result["domains"]["pdot"]["resolution"],
            "multiple_sources_identical_descriptors",
        )
        self.assertEqual(result["domains"]["ods"]["resolution"],
                         "one_complete_key_match")
        self.assertEqual(set(result["candidate_winners"]), {"ods", "pdot", "need"})
        self.assertEqual(
            result["candidate_winners"]["pdot"]["source_variable"], "PDOT"
        )
        proposed = prefill_new_unverified(manifest(), result)
        self.assertFalse(proposed["verified"])
        self.assertEqual(
            proposed["taxonomies"]["ods"][3]["descriptor"],
            "Texto original SDG 4",
        )
        self.assertEqual(proposed["taxonomies"]["pdot"][1]["verified_by"], "")

    def test_conflicting_pdot_sources_are_blocked(self):
        self.source["literal_candidates"][2]["candidate_literal"]["PDOT 3"] = "Conflict"
        result = classify_sources(manifest(), self.source)
        self.assertEqual(
            result["domains"]["pdot"]["resolution"],
            "conflicting_complete_source_dictionaries",
        )
        self.assertNotIn("pdot", result["candidate_winners"])
        proposed = prefill_new_unverified(manifest(), result)
        self.assertEqual(proposed["taxonomies"]["pdot"][0]["descriptor"], "")

    def test_ods_duplicate_numeric_prefix_is_refused(self):
        bad = dict(self.source["literal_candidates"][0]["candidate_literal"])
        bad.pop("ODS 17 Titulo ficticio de objetivo 17")
        bad["ODS 1 Otro nombre"] = "duplicated label"
        res = keyed_candidate(candidate("src.py", "ODS", bad),
                              [f"ODS {i}" for i in range(1, 18)], "ods")
        self.assertFalse(res["complete"])

    def test_prefill_never_mutates_original(self):
        original = manifest()
        result = classify_sources(original, self.source)
        prefill_new_unverified(original, result)
        self.assertEqual(original["taxonomies"]["ods"][0]["descriptor"], "")
        original["verified"] = True
        with self.assertRaises(ValueError):
            classify_sources(original, self.source)


if __name__ == "__main__":
    unittest.main()
