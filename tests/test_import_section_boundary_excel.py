"""Synthetic structural Excel import checks preserving the original 80-case sample."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from export_blinded_validation_workbooks import (
    BOUNDARY_FIELDS, build_xlsx, boundary_sheets
)
from import_section_boundary_excel import parse_boundary_excel


class StructuralExcelImportTests(unittest.TestCase):
    def test_80_structural_rows_read_from_workbook(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"structural.xlsx"
            cases=[]
            texts={}
            for i in range(1,81):
                handle=f"https://example.edu/tesis/{i}"
                cases.append({
                    **{name:"" for name in BOUNDARY_FIELDS},
                    "review_id":f"SB-{i:04d}",
                    "private_source_handle":handle,
                    "sampling_stratum":"late_reference_with_appendix",
                    "extracted_fulltext_chars":"85000",
                    "candidate_position_fraction":"0.82",
                    "heading_line":"Referencias",
                    "context_before":"Anexo","context_after":"Fuente",
                    "trailing_excerpt":"Cita y anexos",
                })
                texts[handle]={"title":"Synthetic title"}
            build_xlsx(path,boundary_sheets(cases,texts))
            rows=parse_boundary_excel(path)
            self.assertEqual(len(rows),80)
            self.assertEqual(rows[79]["review_id"],"SB-0080")
            self.assertEqual(rows[0]["human_trim_from_boundary_safe"],"")
            self.assertEqual(rows[0]["candidate_position_fraction"],"0.82")


if __name__=="__main__":
    unittest.main()
