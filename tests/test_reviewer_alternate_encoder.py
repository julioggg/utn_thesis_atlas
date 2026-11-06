"""Compare different-dimensional semantic spaces safely using synthetic embeddings."""
import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from reviewer_alternate_encoder_pilot import geometry_compare


class AlternateEncoderTests(unittest.TestCase):
    def test_different_dimensions_are_supported(self):
        rng=np.random.default_rng(2)
        a=rng.normal(size=(18,1024)).astype(np.float32)
        b=rng.normal(size=(18,768)).astype(np.float32)
        a/=np.linalg.norm(a,axis=1,keepdims=True)
        b/=np.linalg.norm(b,axis=1,keepdims=True)
        result=geometry_compare(a,b,5)
        self.assertEqual(result["n_documents"],18)
        self.assertEqual(result["topk"],5)
        self.assertTrue(0<=result["mean_topk_neighbor_overlap"]<=1)
        self.assertTrue(-1<=result["pairwise_similarity_spearman"]<=1)

    def test_unmatched_documents_refused(self):
        with self.assertRaises(ValueError):
            geometry_compare(np.ones((7,1024)),np.ones((6,768)),k=3)


if __name__=="__main__":
    unittest.main()
