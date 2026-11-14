"""Test that original descriptor matching does not invent category order or source verification."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from reviewer_descriptor_key_match import (
    match_candidate, make_prefilled, propose, sdg_key
)


def template():
    def rows(names):
        return [
            {"id":x,"descriptor":"","paraphrase_1":"","paraphrase_2":"",
             "source_document":"","source_location":"","verified_by":""}
            for x in names
        ]
    return {
        "verified":False, "status":"TEMPLATE_REQUIRES_SOURCE_VERIFICATION",
        "official_pdot_edition":"","needs_definition_source":"",
        "taxonomies":{
            "ods":rows([f"ODS {i}" for i in range(1,18)]),
            "pdot":rows([f"Axis {i}" for i in range(1,7)]),
            "need":rows([f"Need {i}" for i in range(1,11)])
        }
    }


def source(variable,values,kind):
    return {
        "relative_source_path":"scripts/original_classifier.py",
        "variable_name":variable,"taxonomy_guess":kind,
        "number_of_entries":len(values),"candidate_literal":values,
    }


class ExactDescriptorMatchingTests(unittest.TestCase):
    def setUp(self):
        self.t = template()
        self.inv = {
            "status":"unverified_ast_descriptor_candidates",
            "candidate_source_inventory":[],
            "literal_candidates":[
                source("ods_descriptors", {f"ODS_{i:02d}":f"SDG source text {i}"
                                          for i in range(1,18)},"ods"),
                source("pdot_descriptors", {f"Axis {i}":f"PDOT source text {i}"
                                           for i in range(1,7)},"pdot"),
                source("needs_descriptors", {f"Need {i}":f"Need source text {i}"
                                            for i in range(1,11)},"need"),
                source("pdot_alt", [f"unknown order {i}" for i in range(6)],"pdot"),
            ]
        }

    def test_sdg_key_parser_exact_only(self):
        self.assertEqual(sdg_key("ODS_04"),"ODS 4")
        self.assertEqual(sdg_key("SDG 17"),"ODS 17")
        self.assertIsNone(sdg_key("ODS 18"))
        self.assertIsNone(sdg_key("ODS 4 schools and courses"))

    def test_three_taxonomies_match_only_exact_category_keys(self):
        report=propose(self.t,self.inv)
        self.assertEqual(report["matched_domains"],["ods","pdot","need"])
        candidate=make_prefilled(self.t,report)
        self.assertFalse(candidate["verified"])
        self.assertEqual(candidate["taxonomies"]["ods"][3]["descriptor"],
                         "SDG source text 4")
        self.assertEqual(candidate["taxonomies"]["pdot"][1]["source_location"],
                         "pdot_descriptors")
        self.assertEqual(self.t["taxonomies"]["ods"][3]["descriptor"],"")
        self.assertEqual(candidate["official_pdot_edition"],"")
        self.assertEqual(candidate["taxonomies"]["ods"][3]["verified_by"],"")

    def test_ambiguous_source_candidates_never_prefill(self):
        self.inv["literal_candidates"].append(
            source("pdot_other", {f"Axis {i}":f"Other description {i}"
                                  for i in range(1,7)}, "pdot")
        )
        report=propose(self.t,self.inv)
        self.assertNotIn("pdot",report["matched_domains"])
        self.assertEqual(report["proposals"]["pdot"]["number_of_complete_key_matches"],2)
        candidate=make_prefilled(self.t,report)
        self.assertEqual(candidate["taxonomies"]["pdot"][0]["descriptor"],"")

    def test_list_without_category_keys_never_autofills(self):
        proposal=match_candidate(
            source("ods", [f"description {i}" for i in range(17)],"ods"),
            [f"ODS {i}" for i in range(1,18)]
        )
        self.assertFalse(proposal["matched"])
        self.assertEqual(proposal["reason"],
                         "sequence_has_no_verified_category_key_order")

    def test_refuses_already_verified_template(self):
        self.t["verified"]=True
        with self.assertRaises(ValueError):
            propose(self.t,self.inv)


if __name__=="__main__":
    unittest.main()
