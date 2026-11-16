"""Render synthetic publication charts to catch runtime/layout dependency errors.

No real institutional records or human source labels are used. These tests
check PNG physical DPI; PDF and SVG presence; and figure generation without
placeholder panels. They intentionally cannot certify aesthetics by eye.
"""
from __future__ import annotations
import struct
import sys
import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from reviewer_render_manuscript_figures import (
    FACULTY_SHORT,annual,centroid,heatmap,models,needs,topic_growth,workflow
)
from reviewer_shared import FIVE_FACULTIES

class PublicationRenderSmokeTests(unittest.TestCase):
    def synthetic(self):
        rows=[]
        for f in FIVE_FACULTIES:
            for j in range(100):
                rows.append({
                    "faculty5":f,
                    "year":[2021,2022,2024,2025,2026][j%5],
                    "ods_label":f"ODS {j%17+1}",
                    "pdot_label":f"PDOT {j%6+1}",
                    "need_label":f"source need {j%10}",
                    "need_top1_score":.42+.01*(j%12),
                    "topic":j%8,
                })
        return pd.DataFrame(rows)

    def check_render(self,dest,meta):
        self.assertGreaterEqual(meta["raster_dpi"],600)
        png=dest/meta["png"]
        pdf=dest/meta["pdf"]
        svg=dest/meta["svg"]
        for f in (png,pdf,svg):
            self.assertTrue(f.exists(),str(f))
            self.assertGreater(f.stat().st_size,1000)
        buf=png.read_bytes()[:250]
        self.assertTrue(buf.startswith(b"\x89PNG\r\n\x1a\n"))
        p=buf.find(b"pHYs")
        self.assertGreater(p,0)
        x,y,unit=struct.unpack(">IIB",buf[p+4:p+13])
        self.assertEqual(unit,1)
        self.assertGreaterEqual(x/39.3701,599)
        svg_text=svg.read_text(encoding="utf-8")
        self.assertTrue(svg_text.lstrip().startswith("<?xml"))
        self.assertFalse(any(line.endswith((" ","\\t")) for line in svg_text.splitlines()),
                         "SVG has trailing whitespace and would fail git diff --check")

    def test_core_figure_rendering(self):
        with tempfile.TemporaryDirectory() as td:
            dest=Path(td)
            df=self.synthetic()
            self.check_render(dest,workflow(dest))
            self.check_render(dest,annual(df,dest))
            self.check_render(dest,heatmap(df,"ods",dest))
            self.check_render(dest,heatmap(df,"pdot",dest))
            codes={f"source need {j}":f"Local priority {j+1:02d}"
                   for j in range(10)}
            self.check_render(dest,needs(df,codes,dest))
            self.check_render(dest,topic_growth(df,dest))
            model=[]
            for domain in ("SDG","PDOT"):
                for coder in ("A","B"):
                    for meth in ("TF-IDF","Legacy E5","Legacy E5 centered",
                                 "Fulltext E5","Fulltext E5 centered"):
                        model.append((domain,coder,meth,"random_120",
                                      "accuracy",.5))
            model=pd.DataFrame(model,columns=[
                "domain","coder","method","stratum","metric","value"
            ])
            self.check_render(dest,models(model,dest))
            self.assertEqual(len(list(dest.glob("*.png"))),7)

    def test_centroid_figure_avoids_umap_convex_hulls(self):
        with tempfile.TemporaryDirectory() as td:
            dest=Path(td)
            rng=np.random.default_rng(42)
            matrix=rng.normal(size=(7830,1024)).astype(np.float32)
            np.save(dest/"synthetic_embeddings.npy",matrix)
            faculty=(list(FIVE_FACULTIES)*1566)[:7830]
            df=pd.DataFrame({"faculty5":faculty})
            self.check_render(dest,centroid(df,dest/"synthetic_embeddings.npy",dest))

if __name__=="__main__":
    unittest.main()
