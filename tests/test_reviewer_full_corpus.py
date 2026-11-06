"""Synthetic-only tests of resumable two-MIG checkpoint integrity."""
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from reviewer_full_corpus_two_mig import (
    count_worker_documents,checkpoint_indices,atomic_checkpoint,
    load_verified_checkpoint
)


class FulltextCheckpointTests(unittest.TestCase):
    def test_disjoint_shards_and_complete_indices(self):
        n=11
        self.assertEqual(count_worker_documents(0,n),6)
        self.assertEqual(count_worker_documents(1,n),5)
        a=np.concatenate([checkpoint_indices(0,b,2,n) for b in range(3)])
        b=np.concatenate([checkpoint_indices(1,b,2,n) for b in range(3)])
        self.assertEqual(a.tolist(),[0,2,4,6,8,10])
        self.assertEqual(b.tolist(),[1,3,5,7,9])
        self.assertEqual(len(set(a)|set(b)),n)
        self.assertFalse(set(a)&set(b))

    def test_atomic_private_checkpoint_and_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/"batch_0000.npz"
            rows=np.array([0,2,4],dtype=np.int64)
            vectors=np.zeros((3,1024),dtype=np.float32)
            vectors[:,0]=1
            atomic_checkpoint(file,rows,vectors,[100,101,102],[1,2,3],"digestA")
            got=load_verified_checkpoint(file,rows,"digestA")
            self.assertEqual(got["rows"],3)
            self.assertEqual(got["tokens"],303)
            self.assertEqual(got["chunks"],6)
            with self.assertRaises(ValueError):
                load_verified_checkpoint(file,rows,"wrong_digest")
            with self.assertRaises(ValueError):
                load_verified_checkpoint(file,np.array([2,0,4]),"digestA")
            self.assertTrue(file.exists())
            self.assertEqual(len(list(Path(tmp).glob(".pending_*"))),0)

    def test_overlapping_workers_refused(self):
        with self.assertRaises(ValueError):
            count_worker_documents(2,11)


if __name__=="__main__":
    unittest.main()
