#!/usr/bin/env python3
"""Audit provenance of competing 6-axis PDOT descriptors on private CEDIA.

Compares the original literal dictionaries PDOT and PDOT_MAP by normalized
category key. Reads original source code as text / AST; NEVER executes it.
Scans static load references, which are evidence but NOT definitive pipeline
execution proof. Verifies source checksums against the frozen AST inventory.
Stores all values, contexts and differences only in git-ignored revision/data/.
Public-candidate JSON summarizes counts, names and limitations only.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import re
from pathlib import Path

from reviewer_descriptor_key_match import normalize_label
from reviewer_shared import private_output, sha256_file, write_public

SOURCES = (
    ("utn_atlas_pipeline.py", "PDOT"),
    ("utn_atlas_q1_extras.py", "PDOT_MAP"),
)


def normalize_contents(value):
    return " ".join(normalize_label(value).split())


def statically_trace(source, variable):
    """Find direct LOAD references with enclosing function or class and line."""
    tree = ast.parse(source)
    lines = source.splitlines()
    references = []
    scopes = []

    class Scanner(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            scopes.append(("function", node.name))
            self.generic_visit(node)
            scopes.pop()

        def visit_AsyncFunctionDef(self, node):
            scopes.append(("async_function", node.name))
            self.generic_visit(node)
            scopes.pop()

        def visit_ClassDef(self, node):
            scopes.append(("class", node.name))
            self.generic_visit(node)
            scopes.pop()

        def visit_Name(self, node):
            if node.id == variable and isinstance(node.ctx, ast.Load):
                line = lines[node.lineno - 1].strip()
                references.append({
                    "line": int(node.lineno),
                    "scope": [list(x) for x in scopes],
                    "code_line_private": line[:500],
                    "possible_scoring_context": bool(re.search(
                        r"(align|score|simil|embed|cosine|classif|assign|pdot)",
                        line + " ".join(n for _, n in scopes),
                        flags=re.IGNORECASE
                    )),
                })

    Scanner().visit(tree)
    mention_lines = [
        {"line": i + 1, "code_line_private": s.strip()[:500]}
        for i, s in enumerate(lines)
        if re.search(r"\bpdot_top1\b|\bpdot_top2\b", s, re.IGNORECASE)
    ]
    return {
        "source_lines": len(lines),
        "direct_load_reference_count": len(references),
        "references_private": references,
        "lines_mentioning_output_classification": mention_lines[:80],
        "limit": (
            "Static references do not establish which script generated the "
            "historical 07 parquet; dynamic lookups/import aliases may be missed."
        ),
    }


def compare_source_candidates(inventory, original_root):
    all_candidates = inventory.get("literal_candidates", [])
    by_source = {}
    for name, variable in SOURCES:
        candidates = [
            x for x in all_candidates
            if Path(x.get("relative_source_path", "")).name == name
            and x.get("variable_name") == variable
        ]
        if len(candidates) != 1:
            raise ValueError(f"Missing or duplicate source candidate {name}:{variable}")
        c = candidates[0]
        obj = c.get("candidate_literal")
        if not isinstance(obj, dict) or len(obj) != 6:
            raise ValueError(f"Expected six PDOT literal entries in {name}:{variable}")
        relative = c["relative_source_path"]
        source_path = original_root / relative
        if not source_path.is_file() or not source_path.resolve().is_relative_to(original_root.resolve()):
            raise ValueError("Source path missing or outside original root")
        inventory_files = [
            item for item in inventory.get("candidate_source_inventory", [])
            if item.get("relative_path") == relative
        ]
        if len(inventory_files) != 1:
            raise ValueError("Frozen descriptor inventory does not pin exact source file")
        sha = sha256_file(source_path)
        if sha != inventory_files[0]["sha256"]:
            raise ValueError(f"Original {name} has changed since descriptor inventory: stop")
        source = source_path.read_text(encoding="utf-8", errors="replace")
        keyed = {}
        for label, descriptor in obj.items():
            norm = normalize_label(label)
            if not norm or norm in keyed or not isinstance(descriptor, str) or not descriptor.strip():
                raise ValueError("Invalid/duplicated PDOT label or empty descriptor")
            keyed[norm] = {
                "original_key": label,
                "descriptor": descriptor,
                "sha256": hashlib.sha256(descriptor.encode("utf-8")).hexdigest(),
                "tokens": len(normalize_contents(descriptor).split()),
                "characters": len(descriptor),
            }
        by_source[variable] = {
            "relative_source": relative,
            "source_sha256": sha,
            "keyed": keyed,
            "trace": statically_trace(source, variable),
        }

    baseline = by_source["PDOT"]["keyed"]
    alternate = by_source["PDOT_MAP"]["keyed"]
    if set(baseline) != set(alternate):
        raise ValueError("The two dictionaries have DIFFERENT PDOT category sets")
    entries = []
    for category in sorted(baseline):
        a = baseline[category]
        b = alternate[category]
        sa = normalize_contents(a["descriptor"])
        sb = normalize_contents(b["descriptor"])
        x, y = set(sa.split()), set(sb.split())
        entries.append({
            "category": a["original_key"],
            "same_exact_text": a["descriptor"] == b["descriptor"],
            "same_after_normalization": sa == sb,
            "token_jaccard": round(len(x & y) / max(len(x | y), 1), 6),
            "original_characters": a["characters"],
            "alternate_characters": b["characters"],
            "original_word_count": a["tokens"],
            "alternate_word_count": b["tokens"],
            "original_sha256": a["sha256"],
            "alternate_sha256": b["sha256"],
            "original_descriptor_PRIVATE": a["descriptor"],
            "alternate_descriptor_PRIVATE": b["descriptor"],
        })
    counts = {
        "categories": len(entries),
        "exact_text_disagreements": sum(not x["same_exact_text"] for x in entries),
        "normalized_text_disagreements": sum(not x["same_after_normalization"] for x in entries),
    }
    return by_source, entries, counts


def analyze(args):
    workspace = Path(__file__).resolve().parent.parent
    original_root = args.project_root.expanduser().resolve()
    private_dir = private_output(args.private_dir, workspace)
    inventory_file = private_dir / "descriptor_source_candidates_PRIVATE.json"
    if not inventory_file.is_file():
        raise FileNotFoundError("Original private descriptor source inventory missing")
    inv = json.loads(inventory_file.read_text(encoding="utf-8"))
    if inv.get("status") != "unverified_ast_descriptor_candidates":
        raise ValueError("Unexpected source inventory type")
    details, categories, counts = compare_source_candidates(inv, original_root)
    private_output_file = private_dir / "pdot_source_lineage_PRIVATE.json"
    if private_output_file.exists():
        raise FileExistsError("Previous private PDOT lineage report exists; inspect first")
    private_output_file.write_text(
        json.dumps({
            "schema_version": 1,
            "status": "private_pdot_source_lineage_evidence_not_verified",
            "candidate_source_files": details,
            "category_descriptor_comparison": categories,
            "differences": counts,
            "warning": (
                "Variable reference counts and text similarity do NOT prove "
                "which dictionary generated the original labels."
            ),
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report = {
        "schema_version": 1,
        "status": "unverified_pdot_source_lineage_audited",
        "source_file_sha256_verified_against_inventory": True,
        "pdot_categories": counts["categories"],
        "exact_text_disagreements": counts["exact_text_disagreements"],
        "normalized_text_disagreements": counts["normalized_text_disagreements"],
        "per_category_summary": [{
            "category": x["category"],
            "same_exact_text": x["same_exact_text"],
            "same_after_normalization": x["same_after_normalization"],
            "token_jaccard": x["token_jaccard"],
            "original_word_count": x["original_word_count"],
            "alternate_word_count": x["alternate_word_count"],
        } for x in categories],
        "original_source_variable_load_references": {
            variable: values["trace"]["direct_load_reference_count"]
            for variable, values in details.items()
        },
        "original_source_output_label_mention_lines": {
            variable: len(values["trace"]["lines_mentioning_output_classification"])
            for variable, values in details.items()
        },
        "resolved_which_dictionary_produced_07": False,
        "verified_official_pdot_edition": False,
        "classification_recomputed": False,
        "note": (
            "All descriptor strings, SHA256 values and source-code context "
            "are PRIVATE and never included in this aggregate report."
        ),
    }
    dest = write_public(report, args.output, workspace)
    print("PDOT source discrepancy audit completed:", dest)
    print("Exact differences:", counts["exact_text_disagreements"], "of", counts["categories"])
    print("Source-variable direct LOAD references:", report["original_source_variable_load_references"])
    print("Inspect private file pdot_source_lineage_PRIVATE.json for source-lineage details.")
    print("DO NOT mark PDOT definitions verified until historical source code and official policy are checked.")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root", type=Path, required=True)
    p.add_argument("--private-dir", type=Path,
                   default=Path("data/revision_private/descriptor_inventory"))
    p.add_argument("--output", type=Path,
                   default=Path("docs/audits/reviewer_pdot_source_lineage_status.json"))
    args = p.parse_args()
    analyze(args)


if __name__ == "__main__":
    main()
