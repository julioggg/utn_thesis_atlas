"""Verify generated private blinded review workbooks without disclosing source data."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from export_blinded_validation_workbooks import (
    ANNOTATION_FIELDS, BOUNDARY_FIELDS, ODS, PDOT,
    build_xlsx, canonical_handle, annotation_sheets,
    boundary_sheets, instructions_sheet, secure_archive,
    VALIDATION_STEPS, STRUCTURE_STEPS,
)


class HumanExcelExportTests(unittest.TestCase):
    def setUp(self):
        self.case={
            **{k:"" for k in ANNOTATION_FIELDS},
            "study_id":"TH-0001",
            "private_source_handle":"https://repositorio.utn.edu.ec/sample",
        }
        self.txt="Contenido íntegro de tesis de prueba." * 30

    def test_valid_minimal_xlsx_and_blind_columns(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            h=self.case["private_source_handle"]
            txt=root/"source.txt"
            txt.write_text(self.txt,encoding="utf-8")
            records={h:{
                "file":txt,"title":"Caso sintético","abstract":"",
                "preview":self.txt[:100],"tail":self.txt[-100:],
                "characters":len(self.txt)
            }}
            sheets=[instructions_sheet(VALIDATION_STEPS,"EVALUADOR A"),
                    *annotation_sheets([self.case],records,"A"),
                    instructions_sheet(STRUCTURE_STEPS,"Nota adicional"),
                    ]
            output=root/"test.xlsx"
            build_xlsx(output,sheets)
            with ZipFile(output) as z:
                self.assertIsNone(z.testzip())
                names=set(z.namelist())
                self.assertIn("xl/workbook.xml",names)
                self.assertIn("xl/worksheets/sheet2.xml",names)
                self.assertIn("xl/styles.xml",names)
                w=z.read("xl/worksheets/sheet2.xml").decode("utf-8")
                self.assertIn("sdg_primary",w)
                self.assertIn("pdot_no_match",w)
                self.assertNotIn("ods_top1",w)
                self.assertNotIn("selection_stratum",w)
                self.assertIn("dataValidations",w)
                ET.fromstring(w)

    def test_one_fulltext_per_private_record(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            h=self.case["private_source_handle"]
            txt=root/"real_original.txt"
            txt.write_text(self.txt,encoding="utf-8")
            records={h:{
                "file":txt,"title":"Caso sintético","abstract":"",
                "preview":self.txt[:100],"tail":self.txt[-100:],
                "characters":len(self.txt)
            }}
            cases=[self.case]
            secure_archive(root/"Evaluator_A_PRIVADO.zip","Evaluator_A.xlsx",
                           [*annotation_sheets(cases,records,"A")],
                           cases,records,"study_id")
            with ZipFile(root/"Evaluator_A_PRIVADO.zip") as z:
                self.assertEqual(set(z.namelist()),{
                    "Evaluator_A.xlsx","Evidencias/TH-0001.txt",
                    "LEEME_PRIVACIDAD.txt",
                })
                self.assertEqual(z.read("Evidencias/TH-0001.txt").decode("utf-8"),
                                 self.txt)
            with self.assertRaises(FileExistsError):
                secure_archive(root/"Evaluator_A_PRIVADO.zip","Evaluator_A.xlsx",
                               [],cases,records,"study_id")

    def test_excel_text_never_executes_leading_formula(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"test.xlsx"
            rows=[["=HYPERLINK('http://bad')"],[],[],[],["x"],["=2+2"]]
            build_xlsx(root,[("TEST",rows,[35],"annotation",None)])
            with ZipFile(root) as z:
                xml=z.read("xl/worksheets/sheet1.xml").decode("utf-8")
                self.assertIn("=2+2",xml)
                self.assertNotIn("<f>",xml)
                self.assertIn("inlineStr",xml)

    def test_canonical_handle_only_removes_known_excel_escape(self):
        self.assertEqual(canonical_handle("'=abc","=abc"),"=abc")
        self.assertEqual(canonical_handle("abc","abc"),"abc")
        with self.assertRaises(ValueError):
            canonical_handle("'another","abc")


if __name__=="__main__":
    unittest.main()
