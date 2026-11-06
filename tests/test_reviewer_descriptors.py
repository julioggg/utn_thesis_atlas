"""Synthetic descriptor provenance and scoring logic, no neural model required."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from reviewer_descriptor_inventory import candidates_from_python
from reviewer_prepare_descriptors import template
from reviewer_descriptor_sensitivity import load_verified_manifest,summarise_domain


class DescriptorTests(unittest.TestCase):
    def test_ast_never_executes_code(self):
        code = ("ods_descriptors = {'ODS 1': 'poverty and social protection', "
                "'ODS 2': 'agriculture and hunger', 'ODS 3': 'health targets', "
                "'ODS 4':'education objectives', 'ODS 5': 'gender equality'}\n"
                "import os\n"
                "os.system('echo SHOULD_NOT_BE_EXECUTED')\n")
        result=candidates_from_python(code,"test.py")
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]["number_of_entries"],5)

    def test_private_template_has_empty_strings_and_real_labels(self):
        df=pd.DataFrame({
            "ods_top1":[f"ODS {i}" for i in range(1,18)],
            "pdot_top1":[f"P{x%6}" for x in range(17)],
            "need_top1":[f"Need{x%10}" for x in range(17)]
        })
        t=template(df)
        self.assertFalse(t["verified"])
        self.assertEqual(len(t["taxonomies"]["ods"]),17)
        self.assertEqual(len(t["taxonomies"]["pdot"]),6)
        self.assertEqual(len(t["taxonomies"]["need"]),10)
        self.assertEqual(t["taxonomies"]["ods"][0]["descriptor"],"")

    def test_manifest_blocks_unverified_and_missing_provenance(self):
        data={"verified":False,"taxonomies":{}}
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"test.json"
            p.write_text(json.dumps(data),encoding="utf-8")
            with self.assertRaises(ValueError):
                load_verified_manifest(p)

    def test_score_sensitivity_is_not_reported_as_f1(self):
        sims=np.array([[.85,.84,.4],[.3,.9,.4],[.5,.4,.7]],dtype="float32")
        stats,labels=summarise_domain(sims,["ODS 1","ODS 2","ODS 3"],
                                      ["ODS 1","ODS 2","ODS 3"],"ods")
        self.assertEqual(stats["n"],3)
        self.assertEqual(stats["candidate_top1_agreement_with_legacy_forced_labels"],1)
        self.assertEqual(stats["sdg4_original_n"],0) if "sdg4_original_n" in stats else None
        self.assertIn("NOT accuracy",stats["warning"])
        self.assertNotIn("F1",stats)


if __name__ == "__main__":
    unittest.main()
