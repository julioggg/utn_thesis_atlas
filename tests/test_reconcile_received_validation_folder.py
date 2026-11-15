"""Synthetic integration tests: one received folder, three unmodified originals."""
from __future__ import annotations
import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))

from export_blinded_validation_workbooks import (
    ANNOTATION_FIELDS, BOUNDARY_FIELDS,
    annotation_sheets, boundary_sheets, build_xlsx
)
from reconcile_received_validation_folder import (
    FILE_NAMES, preflight_all, received_folder
)


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class PrivateReceivedFolderTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name).resolve()
        self.private=self.root/"data/revision_private"
        self.incoming=received_folder(self.root)
        self.incoming.mkdir(parents=True)
        master=[]
        originals=[]
        texts={}
        for i in range(1,451):
            sid=f"TH-{i:04d}"
            h=f"https://samples.private.edu/thesis/{i:04d}"
            master.append({"study_id":sid,"handle_id":h})
            originals.append(dict.fromkeys(ANNOTATION_FIELDS,""))
            originals[-1].update(study_id=sid,private_source_handle=h)
            texts[h]={
                "title":"Synthetic source","abstract":"","preview":"Section sample",
                "tail":"Conclusion sample","characters":140
            }
        write_csv(self.private/"validation/sample_master_private.csv",
                  ["study_id","handle_id"],master)
        for letter,rows in (
            ("A",originals),
            ("B",list(reversed(originals)))
        ):
            write_csv(
                self.private/f"validation/coder_{letter}_private.csv",
                list(ANNOTATION_FIELDS),rows
            )
            sheets=annotation_sheets(rows,texts,letter)
            build_xlsx(self.incoming/FILE_NAMES[letter],sheets)
        boundary=[]
        strata=[
            "late_reference_with_appendix",
            "late_reference_without_appendix",
            "early_reference_only",
            "no_reference_heading",
        ]
        for i in range(1,81):
            h=f"https://samples.private.edu/boundary/{i:04d}"
            case=dict.fromkeys(BOUNDARY_FIELDS,"")
            case.update({
                "review_id":f"SB-{i:04d}",
                "private_source_handle":h,
                "sampling_stratum":strata[(i-1)//20],
                "extracted_fulltext_chars":"90000",
                "candidate_position_fraction":"0.91",
                "heading_line":"Referencias",
                "context_before":"Conclusiones",
                "context_after":"Capítulo referencias",
                "trailing_excerpt":"Anexos posteriores",
            })
            boundary.append(case)
            texts[h]={"title":"Synthetic boundary source"}
        write_csv(
            self.private/"section_boundary_review_v1/section_boundary_review_private.csv",
            list(BOUNDARY_FIELDS),boundary
        )
        submitted=[dict(r) for r in boundary]
        for index,row in enumerate(submitted):
            row["human_heading_is_real_references_start"]="yes"
            row["human_tail_contains_scientific_contribution"]="yes"
            row["human_trim_from_boundary_safe"]="no"
            row["human_notes"]="Evidence reviewed from the fulltext."
            if index<2:
                row["human_heading_is_real_references_start"]="no"
                row["human_corrected_boundary_fraction"]="0.63"
        build_xlsx(
            self.incoming/FILE_NAMES["80"],
            boundary_sheets(submitted,texts)
        )

    def test_all_three_source_files_unchanged_and_verified(self):
        before={p.name:p.read_bytes() for p in self.incoming.glob("*.xlsx")}
        folder, report=preflight_all(self.root)
        self.assertEqual(folder,self.incoming)
        self.assertEqual(set(report),{"A","B","80"})
        for letter in ("A","B"):
            self.assertEqual(report[letter]["cases"],450)
            self.assertEqual(report[letter]["complete_by_required_fields"],0)
            self.assertTrue(report[letter]["import_shape_compatible"])
            self.assertFalse(report[letter]["human_independence_or_provenance_verified"])
        self.assertEqual(report["80"]["cases"],80)
        self.assertEqual(report["80"]["status_counts"]["reviewed"],78)
        self.assertEqual(report["80"]["status_counts"]["invalid"],2)
        after={p.name:p.read_bytes() for p in self.incoming.glob("*.xlsx")}
        self.assertEqual(before,after)

    def test_filename_missing_fails_without_guessing_replacement(self):
        (self.incoming/FILE_NAMES["B"]).unlink()
        with self.assertRaisesRegex(FileNotFoundError,"Expected exact filename"):
            preflight_all(self.root)

    def test_received_folder_cannot_escape_private_data(self):
        with self.assertRaisesRegex(ValueError,"inside private"):
            received_folder(self.root,self.root/"docs/audits")


if __name__=="__main__":
    unittest.main()
