"""Synthetic-only integration check for exploratory E5 versus A/B metrics."""
import sys
import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from reviewer_legacy_e5_dual_coder_provisional import evaluate

class TwoReferenceE5Tests(unittest.TestCase):
    def test_all_450_and_two_coders_without_adjudicating(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            private=root/"data/revision_private/validation"
            private.mkdir(parents=True)
            workspace_private=root/"data/revision_private/dual"
            master=[]
            A=[]
            B=[]
            source=[]
            for i in range(450):
                sid=f"TH-{i+1:04d}"
                h=f"private-handle-{i}"
                master.append({
                    "study_id":sid,"handle_id":h,"source_row_index":str(i),
                    "selection_stratum":"population_random" if i<120 else "targeted_enrichment",
                })
                row={
                    "study_id":sid,"private_source_handle":h,
                    "sdg_primary":"ODS 4","sdg_secondary":"","sdg_no_match":"no",
                    "pdot_primary":"PDOT 2","pdot_secondary":"","pdot_no_match":"no",
                    "uncertain":"no","brief_evidence":"Read original document",
                    "coder_notes":"",
                }
                A.append(dict(row))
                B.append(dict(row))
                source.append({"handle_id":h,"ods_top1":"ODS 4",
                               "pdot_top1":"Sistema Socio Cultural"})
            B[0]["sdg_primary"]="ODS 3"
            for filename,data in (("sample_master_private.csv",master),
                                  ("coder_A_private.csv",A),("coder_B_private.csv",B)):
                with (private/filename).open("w",newline="",encoding="utf-8") as f:
                    writer=csv.DictWriter(f,fieldnames=list(data[0]))
                    writer.writeheader()
                    writer.writerows(data)
            # Root of the production script is the installed revision checkout;
            # only private metric-output root is patched to the synthetic temp.
            with patch(
                "reviewer_legacy_e5_dual_coder_provisional.inspect_files",
                return_value={"all_annotations_finished":True}
            ), patch(
                "reviewer_legacy_e5_dual_coder_provisional.pd.read_parquet",
                return_value=pd.DataFrame(source)
            ), patch(
                "reviewer_legacy_e5_dual_coder_provisional.read_original_embeddings",
                return_value=(np.zeros((450,1024),dtype=np.float32),{"synthetic":True})
            ), patch(
                "reviewer_legacy_e5_dual_coder_provisional.private_output",
                return_value=workspace_private
            ):
                workspace_private.mkdir(parents=True,exist_ok=True)
                result=evaluate(root,private,workspace_private)
            self.assertEqual(
                result["comparisons"]["A"]["ods"]["probability_sample_120"]["accuracy"],
                1.0)
            self.assertEqual(
                result["comparisons"]["B"]["ods"]["probability_sample_120"]["accuracy"],
                round(119/120,6))
            self.assertEqual(
                result["comparisons"]["B"]["pdot"]["probability_sample_120"]["accuracy"],
                1.0)
            self.assertEqual(len(list(workspace_private.glob("*_perclass_PRIVATE.csv"))),12)
            self.assertIn("not_adjudicated",result["status"])

if __name__=="__main__":
    unittest.main()
