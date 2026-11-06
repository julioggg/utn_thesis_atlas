#!/usr/bin/env python3
"""Discover SDG, Imbabura-PDOT and territorial descriptor literals SAFELY.

AST inspection only (never executes original code). Candidate descriptors,
their full strings and source paths are stored in ignored private data/;
only aggregate candidate counts and hashes are public-candidate.
Does NOT certify taxonomy provenance or invent missing descriptors.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import re
import time
from collections import Counter
from pathlib import Path
from reviewer_shared import private_output, sha256_file, write_public

TRIGGERS = re.compile(
    r"(?:ods|sdg|pdot|territor|need|necesidad|descrip|taxonomy|taxonomia)",
    re.I
)
EXT = {".py",".json",".yaml",".yml",".md",".txt"}
FOLDERS = ("scripts","src","config","configs","docs","notebooks")
MAX_BYTES = 750_000


def categorize(name):
    s = str(name).casefold()
    if "ods" in s or "sdg" in s:
        return "ods"
    if "pdot" in s or "territorial" in s:
        return "pdot"
    if "need" in s or "necesidad" in s:
        return "need"
    return "unknown"


def candidates_from_python(code, relative):
    """Extract simple literal dict/list values; no imports/eval/exec."""
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return []
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            variables = [x.id for x in node.targets if isinstance(x, ast.Name)]
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            variables = [node.target.id] if isinstance(node.target, ast.Name) else []
            value = node.value
        else:
            continue
        if value is None or not variables:
            continue
        for name in variables:
            if not TRIGGERS.search(name):
                continue
            try:
                literal = ast.literal_eval(value)
            except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
                continue
            if isinstance(literal, dict):
                values = list(literal.values())
                count = len(literal)
            elif isinstance(literal, (list, tuple)):
                values = list(literal)
                count = len(literal)
            else:
                continue
            if not 5 <= count <= 50 or not all(isinstance(x, str) for x in values):
                continue
            if sum(len(x) for x in values) > 50000:
                continue
            found.append({
                "relative_source_path": str(relative), "variable_name": name,
                "taxonomy_guess": categorize(name),
                "number_of_entries": count,
                "candidate_literal": literal,
            })
    return found


def inventory(project, workspace, private, seed=None):
    paths = []
    for folder in FOLDERS:
        root = project / folder
        if root.is_dir():
            paths.extend(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in EXT)
    paths.extend(p for p in project.iterdir()
                 if p.is_file() and p.suffix.lower() in EXT)
    distinct = sorted(set(paths))
    inventory = []
    literals = []
    candidate_domain_files = Counter()
    for p in distinct:
        if p.stat().st_size > MAX_BYTES:
            continue
        rel = p.relative_to(project)
        if any(x in rel.parts for x in (".git","__pycache__",".venv","data","private")):
            continue
        if not TRIGGERS.search(str(rel)):
            # Non-descriptor filenames can contain literal descriptors, but
            # we still scan Python files under source folders.
            if p.suffix.lower() != ".py":
                continue
        content = p.read_text(encoding="utf-8", errors="replace")
        hits = list(TRIGGERS.finditer(content))
        if not hits:
            continue
        found = candidates_from_python(content, rel) if p.suffix == ".py" else []
        record = {
            "relative_path": str(rel),
            "sha256": sha256_file(p),
            "file_bytes": p.stat().st_size,
            "keyword_occurrences": len(hits),
            "ast_literal_candidates": len(found),
        }
        inventory.append(record)
        literals.extend(found)
        for word in ("ods","sdg","pdot","need","necesidad"):
            if re.search(word, content, re.I):
                candidate_domain_files[word] += 1
    private.mkdir(parents=True, exist_ok=True)
    private_file = private / "descriptor_source_candidates_PRIVATE.json"
    private_file.write_text(
        json.dumps({
            "status": "unverified_ast_descriptor_candidates",
            "source": "original local UTN thesis atlas code files",
            "candidate_source_inventory": inventory,
            "literal_candidates": literals,
            "important": "Do not treat these strings as validated/released official descriptors.",
        }, ensure_ascii=False, indent=2)+"\n", encoding="utf-8"
    )
    return {
        "schema_version": 1,
        "status": "descriptor_source_inventory_complete_requires_manual_provenance_review",
        "source_files_examined": len(distinct),
        "files_with_descriptor_terms": len(inventory),
        "literal_candidate_objects": len(literals),
        "literal_candidates_by_taxonomy_guess": dict(Counter(
            x["taxonomy_guess"] for x in literals
        )),
        "candidate_source_term_file_counts": dict(candidate_domain_files),
        "original_descriptors_verified": False,
        "official_imbabura_pdot_edition_verified": False,
        "ten_local_needs_documentary_source_verified": False,
        "private_candidate_file_created": True,
        "limitations": [
            "AST inspection never executes source code and cannot recover dynamically assembled descriptors.",
            "All candidate literal strings, filenames and file hashes are private to the HPC workspace.",
            "Manuscript descriptor sensitivity requires a separate verified descriptor manifest with source provenance.",
            "Do not invent PDOT axes, local-needs definitions or human labels from this inventory.",
        ]
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root", type=Path, required=True)
    p.add_argument("--private-dir", type=Path,
                   default=Path("data/revision_private/descriptor_inventory"))
    p.add_argument("--output", type=Path,
                   default=Path("docs/audits/descriptor_source_inventory.json"))
    a = p.parse_args()
    workspace = Path(__file__).resolve().parent.parent
    report = inventory(a.project_root.expanduser().resolve(), workspace,
                       private_output(a.private_dir, workspace))
    path = write_public(report, a.output, workspace)
    print("Descriptor source inventory:", path)
    print("Candidate literal objects:", report["literal_candidate_objects"])
    print("Original descriptors NOT YET verified: inspect ignored private candidates.")
    print("No private descriptors or documents were exported.")


if __name__ == "__main__":
    main()
