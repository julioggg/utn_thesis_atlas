"""Synthetic unit tests for lexical TF-IDF baseline and historical source labels."""
import sys
import unittest
from pathlib import Path

import numpy as np
import importlib.util
HAS_SKLEARN=importlib.util.find_spec("sklearn") is not None

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from reviewer_historical_tfidf_human_metrics import (
    fit_lexical_baseline,prepare_lexical_texts
)
from reviewer_human_validation_metrics import PDOT_ID


class SourceDescriptorLexicalBaselineTests(unittest.TestCase):
    def test_all_17_sdg_codes_and_original_order_kept(self):
        original={f"ODS {i} Test label":f"Method for goal {i}" for i in range(1,18)}
        keys,ids,texts=prepare_lexical_texts(original,"ods")
        self.assertEqual(keys,list(original))
        self.assertEqual(ids,[f"ODS {i}" for i in range(1,18)])
        self.assertTrue(texts[3].startswith("ODS 4 Test label."))
        
    def test_pdot_analytical_axes_not_reordered_or_invented(self):
        raw={k:f"Source description {j}" for j,k in enumerate(PDOT_ID)}
        keys,ids,descriptions=prepare_lexical_texts(raw,"pdot")
        self.assertEqual(keys,list(PDOT_ID))
        self.assertEqual(ids,list(PDOT_ID.values()))
        self.assertEqual(len(descriptions),6)

    def test_human_coder_classes_must_be_exact(self):
        raw={f"ODS {i}":f"goal {i}" for i in range(1,18)}
        raw["ODS 17"]="last"
        raw["ODS 16"]="different"
        keys,ids,_=prepare_lexical_texts(raw,"ods")
        self.assertEqual(len(ids),17)
        raw["ODS 99"]="not a real class"
        with self.assertRaisesRegex(ValueError,"size"):
            prepare_lexical_texts(raw,"ods")

    @unittest.skipUnless(HAS_SKLEARN, "scikit-learn optional; installed in CEDIA")
    def test_fit_excludes_private_heldout_docs(self):
        texts=[
            "physics electric energy frequency",
            "physics electric power network",
            "student school teaching learning",
            "student teaching learning classroom",
            "rare holdoutword only evaluation",
        ]
        fit=np.array([1,1,1,1,0],dtype=bool)
        scores,nwords,nnz=fit_lexical_baseline(
            texts,fit,["electric power","teaching classroom"],max_features=200
        )
        self.assertEqual(scores.shape,(5,2))
        self.assertGreater(nwords,4)
        self.assertGreater(nnz,0)
        self.assertGreater(scores[0,0],scores[0,1])
        self.assertGreater(scores[2,1],scores[2,0])
        self.assertTrue(np.isfinite(scores).all())

if __name__=="__main__":
    unittest.main()
