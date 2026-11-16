"""Integration regression: ODS metrics must never be overwritten by PDOT metrics."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import reviewer_four_e5_variant_dual_coder_metrics as subject
from reviewer_human_validation_metrics import PDOT_ID

class FourE5SchemaIntegration(unittest.TestCase):
    def test_both_domains_keep_four_variants_and_both_coders(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d)
            private=base/"data/revision_private"
            validation=private/"validation"
            validation.mkdir(parents=True)
            (base/"docs/audits").mkdir(parents=True)
            matrix_path=private/"reclassification_all_7830_PRIVATE.npz"
            report_path=base/"docs/audits/reclassification.json"
            metric_path=private/"fresh_per_class"
            ods=[f"ODS {i}" for i in range(1,18)]
            pdot=list(PDOT_ID)
            report={
                "status":(
                    "fulltext_and_centered_ods_pdot_needs_reclassification_"
                    "exploratory_not_human_validated"
                ),
                "n_theses":7830,
                "variants":list(subject.VARIANTS),
                "source_alignment_verified":{"04_vs_05":True},
                "descriptor_source_sha256":"source-dictionary-checksum",
                "domains": {
                    "ods":{"representations":{"legacy_raw":{
                        "top1_category_counts_candidate_unvalidated":dict.fromkeys(ods,0)
                    }}},
                    "pdot":{"representations":{"legacy_raw":{
                        "top1_category_counts_candidate_unvalidated":dict.fromkeys(pdot,0)
                    }}},
                }
            }
            report_path.write_text(json.dumps(report),encoding="utf-8")
            matrices={}
            for domain,names in (("ods",ods),("pdot",pdot)):
                for variant in subject.VARIANTS:
                    array=np.zeros((7830,len(names)),dtype=np.float32)
                    chosen=names.index("ODS 4") if domain=="ods" else names.index(
                        "Sistema Socio Cultural"
                    )
                    if domain=="ods" and variant.startswith("fulltext"):
                        chosen=names.index("ODS 3")
                    if domain=="pdot" and variant=="fulltext_centered":
                        chosen=names.index("Sistema Económico Productivo")
                    array[:,chosen]=0.9
                    matrices[f"{domain}_{variant}_scores"]=array
            np.savez_compressed(matrix_path,**matrices)
            handles=[f"private-handle-{i}" for i in range(7830)]
            source_frame=pd.DataFrame({
                "handle_id":handles,
                "ods_top1":["ODS 4"]*7830,
                "pdot_top1":["Sistema Socio Cultural"]*7830
            })
            master=pd.DataFrame({
                "study_id":[f"TH-{i+1:04d}" for i in range(450)],
                "handle_id":handles[:450],
                "source_row_index":[str(i) for i in range(450)],
                "selection_stratum":[
                    "population_random" if i<120 else "targeted_enrichment"
                    for i in range(450)
                ],
            })
            A=pd.DataFrame({
                "study_id":master["study_id"],
                "private_source_handle":handles[:450],
                "sdg_primary":["ODS 4"]*450,
                "sdg_no_match":["no"]*450,
                "pdot_primary":["PDOT 2"]*450,
                "pdot_no_match":["no"]*450,
            })
            B=A.copy()
            def read_csv(path,*args,**kwargs):
                name=Path(path).name
                if name=="sample_master_private.csv":return master.copy()
                if name=="coder_A_private.csv":return A.copy()
                if name=="coder_B_private.csv":return B.copy()
                raise AssertionError("Unexpected CSV path "+str(path))
            args=type("Args",(),{
                "private_dir":validation,
                "reclassification_report":report_path,
                "reclassification_scores":matrix_path,
                "project_root":base,
                "private_metrics_dir":metric_path,
                "output":base/"docs/audits/fresh_result.json",
            })()
            with patch.object(subject,"__file__",str(
                base/"scripts/reviewer_four_e5_variant_dual_coder_metrics.py"
            )), patch.object(subject,"inspect_files",return_value={
                "all_annotations_finished":True
            }), patch.object(subject.pd,"read_parquet",return_value=source_frame), \
                patch.object(subject.pd,"read_csv",side_effect=read_csv):
                results=subject.analyze(args)
            self.assertEqual(set(results["comparisons"]),{"ods","pdot"})
            for domain in ("ods","pdot"):
                self.assertEqual(set(results["comparisons"][domain]),
                                 set(subject.VARIANTS))
                for variant in subject.VARIANTS:
                    self.assertEqual(
                        set(results["comparisons"][domain][variant]),{"A","B"}
                    )
            self.assertEqual(
                results["comparisons"]["ods"]["legacy_raw"]["A"]
                ["random_120"]["accuracy"],1.0
            )
            self.assertEqual(
                results["comparisons"]["ods"]["fulltext_raw"]["A"]
                ["random_120"]["accuracy"],0.0
            )
            self.assertEqual(
                results["comparisons"]["pdot"]["legacy_raw"]["B"]
                ["random_120"]["accuracy"],1.0
            )
            self.assertEqual(
                results["comparisons"]["pdot"]["fulltext_raw"]["B"]
                ["random_120"]["accuracy"],1.0
            )
            self.assertEqual(len(list(metric_path.glob("*_perclass_PRIVATE.csv"))),48)

if __name__=="__main__":
    unittest.main()
