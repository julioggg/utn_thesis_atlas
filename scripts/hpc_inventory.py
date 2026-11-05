#!/usr/bin/env python3
"""Read-only inventory of expected HPC artifacts; no thesis content is exported."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

EXPECTED = [
    "data/metadata/01_items_metadata_full_v2.parquet",
    "data/metadata/01_items_metadata.parquet",
    "data/metadata/02_pdf_downloads.parquet",
    "data/metadata/03_text_extraction.parquet",
    "data/processed/04_clean_corpus.parquet",
    "data/processed/05_embeddings.npy",
    "data/processed/06_corpus_with_topics.parquet",
    "data/processed/07_alignment_pdot_ods_needs.parquet",
    "reports/06_k_optimization.csv",
    "code/scripts/utn_atlas_pipeline.py",
    "code/scripts/utn_harvest_full_v2.py",
    "code/scripts/utn_atlas_q1_extras.py",
    "scripts/utn_atlas_pipeline.py",
    "scripts/utn_harvest_full_v2.py",
    "scripts/utn_atlas_q1_extras.py",
]
DIRS = ["data/metadata", "data/processed", "data/pdfs", "data/texts",
        "reports", "reports/figures", "code", "scripts", "logs"]

def inventory(root: Path) -> dict:
    if not root.is_dir():
        raise FileNotFoundError("The specified HPC project directory does not exist")
    result = {"schema_version": 1, "project_path_redacted": True,
              "known_file_locations": {}, "known_directories": {},
              "caution": "Only expected paths are checked. Missing here does not prove absent elsewhere."}
    for rel in EXPECTED:
        path = root / rel
        state = {"exists": path.is_file(), "size_bytes": path.stat().st_size if path.is_file() else None}
        result["known_file_locations"][rel] = state
    for rel in DIRS:
        result["known_directories"][rel] = (root / rel).is_dir()
    return result

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root", required=True, type=Path)
    p.add_argument("--output", type=Path, default=Path("reports/public/hpc_inventory.json"))
    args = p.parse_args()
    payload = inventory(args.project_root.expanduser().resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    hits = sum(x["exists"] for x in payload["known_file_locations"].values())
    print(f"Inventory written to {args.output}; {hits} known file location(s) found.")
    print("No original project file was changed; no thesis record was exported.")

if __name__ == "__main__":
    main()
