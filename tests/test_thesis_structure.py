"""CPU-only synthetic tests for conservative thesis section heading audit."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_thesis_structure import analyze_text, census


class ThesisStructureTests(unittest.TestCase):
    def test_late_spanish_bibliography_and_annexes(self):
        text = (
            "RESUMEN\n" + "Este trabajo contiene metodologia y resultados.\n" * 220
            + "5. CONCLUSIONES\n" + "Discusion metodologica final.\n" * 15
            + "6. REFERENCIAS BIBLIOGRÁFICAS\n"
            + "Libro de ejemplo.\n" * 20 + "7. ANEXOS\n"
            + "Resultados complementarios.\n" * 15
        )
        result = analyze_text(text)
        self.assertTrue(result["late_reference"])
        self.assertTrue(result["appendix_after_reference"])
        self.assertTrue(0.55 < result["late_reference_position"] < 1.0)
        self.assertEqual(result["headings"]["references"], 1)

    def test_early_toc_heading_is_not_late_bibliography(self):
        text = "ÍNDICE\nREFERENCIAS\n" + ("cuerpo de la tesis.\n" * 1000)
        result = analyze_text(text)
        self.assertTrue(result["early_reference_only"])
        self.assertFalse(result["late_reference"])
        self.assertIsNone(result["late_reference_position"])

    def test_mentions_do_not_count_as_standalone_headings(self):
        text = ("Las referencias bibliográficas son relevantes en este modelo.\n" * 50)
        result = analyze_text(text)
        self.assertEqual(result["headings"]["references"], 0)
        self.assertFalse(result["found_any_reference"])

    def test_english_section_and_empty(self):
        text = "1. INTRODUCTION\n" + ("A study.\n" * 300) + "CHAPTER 5 REFERENCES\n" + "Citation\n" * 2
        result = analyze_text(text)
        self.assertEqual(result["headings"]["references"], 1)
        self.assertEqual(result["headings"]["introduction"], 1)
        self.assertEqual(analyze_text("")["chars"], 0)

    def test_private_pdf_data_not_exported(self):
        import pandas as pd
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "test.parquet"
            texts = ["PRIVATE-USER-NAME\n" + "THESIS BODY\n" * 300,
                     "REFERENCIAS\n" + "BODY\n" * 300]
            pd.DataFrame({"full_text": texts}).to_parquet(file, index=False)
            result = census(file)
            self.assertEqual(result["population_rows"], 2)
            self.assertNotIn("PRIVATE-USER-NAME", str(result))
            self.assertNotIn("THESIS BODY", str(result))
            self.assertEqual(result["n_with_reference_heading_only_in_early_text"], 1)


if __name__ == "__main__":
    unittest.main()
