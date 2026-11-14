#!/usr/bin/env python3
"""V2 private source-descriptor reconciliation.

Handle verbose original ODS labels (e.g. 'ODS 4 Educación de calidad');
compare duplicate PDOT dictionaries by exact category-to-text mapping.
Never assume category order, never invent official PDOT provenance, never
mark descriptor manifest verified, and never overwrite V1/private inputs.
Outputs private V2 candidates and an aggregate-only public status.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from reviewer_descriptor_key_match import normalize_label
from reviewer_shared import private_output, sha256_file, write_public

DOMAIN_SIZES = {"ods": 17, "pdot": 6, "need": 10}


def normalized_ods_key(key):
    norm = normalize_label(key)
    # Require an explicit ODS/SDG/goal prefix. A title alone is not a stable ID.
    m = re.fullmatch(
        r"(?:ods|sdg|goal|objetivo)\s+0?([1-9]|1[0-7])(?:\s+\S(?:.*\S)?)?",
        norm,
    )
    return f"ODS {int(m.group(1))}" if m else None


def keyed_candidate(candidate, taxonomy_ids, domain):
    """An entire, one-to-one set of category IDs is mandatory."""
    source = {
        "source_file": candidate.get("relative_source_path", ""),
        "source_variable": candidate.get("variable_name", ""),
        "domain": domain,
        "source_entry_count": candidate.get("number_of_entries"),
    }
    obj = candidate.get("candidate_literal")
    if not isinstance(obj, dict):
        return {**source, "complete": False, "reason": "no_category_keys"}
    if len(obj) != len(taxonomy_ids):
        return {**source, "complete": False, "reason": "wrong_cardinality"}
    keys = set(taxonomy_ids)
    lookup = {normalize_label(s): s for s in taxonomy_ids}
    if len(lookup) != len(keys):
        raise ValueError("Nonunique normalized target labels")
    mapped = {}
    for key, description in obj.items():
        if not isinstance(description, str) or not description.strip():
            return {**source, "complete": False, "reason": "empty_description"}
        resolved = (
            normalized_ods_key(key) if domain == "ods"
            else lookup.get(normalize_label(key))
        )
        if resolved not in keys or resolved in mapped:
            return {
                **source, "complete": False,
                "reason": "unmapped_or_duplicate_source_key",
            }
        mapped[resolved] = description
    if set(mapped) != keys:
        return {**source, "complete": False, "reason": "incomplete_label_set"}
    return {
        **source, "complete": True, "reason": "complete_one_to_one_category_key_match",
        "descriptors": mapped,
    }


def classify_sources(template, inventory):
    if template.get("verified") is not False:
        raise ValueError("Verified template cannot be automatically revised")
    if inventory.get("status") != "unverified_ast_descriptor_candidates":
        raise ValueError("Not the original unverified AST inventory")
    result = {
        "schema_version": 2,
        "status": "unverified_candidate_reconciliation_v2",
        "domains": {},
        "candidate_winners": {},
        "notes": [
            "No source snippets or policy documents have been independently verified.",
            "Multiple exact dictionary duplicates are accepted only if all descriptions are byte-identical by matched category.",
            "Conflicting original-source dictionaries remain unresolved and require human source-lineage review.",
            "Do not mark the original descriptor manifest verified.",
        ],
    }
    for domain, cardinality in DOMAIN_SIZES.items():
        ids = [r["id"] for r in template["taxonomies"][domain]]
        if len(ids) != cardinality or len(set(ids)) != cardinality:
            raise ValueError(f"Invalid {domain} taxonomy template")
        candidates = [
            keyed_candidate(raw, ids, domain)
            for raw in inventory["literal_candidates"]
            if raw.get("number_of_entries") == cardinality
        ]
        complete = [x for x in candidates if x["complete"]]
        provenance = [
            {
                "source_file": item["source_file"],
                "source_variable": item["source_variable"],
                "complete": item["complete"],
                "reason": item["reason"],
            } for item in candidates
        ]
        if len(complete) == 0:
            resolution = "no_complete_exact_key_match"
        elif len(complete) == 1:
            resolution = "one_complete_key_match"
        elif all(
            x["descriptors"] == complete[0]["descriptors"]
            for x in complete[1:]
        ):
            resolution = "multiple_sources_identical_descriptors"
        else:
            resolution = "conflicting_complete_source_dictionaries"
        result["domains"][domain] = {
            "expected_labels": cardinality,
            "candidate_objects": len(candidates),
            "complete_matches": len(complete),
            "resolution": resolution,
            "provenance_candidates_private": provenance,
        }
        if resolution in (
            "one_complete_key_match", "multiple_sources_identical_descriptors"
        ):
            def priority(x):
                name = x["source_file"]
                original_first = name.endswith("utn_atlas_pipeline.py")
                return (not original_first, name, x["source_variable"])
            result["candidate_winners"][domain] = sorted(complete, key=priority)[0]
    return result


def prefill_new_unverified(template, matched):
    out = json.loads(json.dumps(template, ensure_ascii=False))
    out["status"] = "UNVERIFIED_SOURCE_KEY_CANDIDATE_V2"
    out["verified"] = False
    for domain, winner in matched["candidate_winners"].items():
        for item in out["taxonomies"][domain]:
            if item.get("descriptor"):
                raise ValueError("Never overwrite an existing descriptor")
            item["descriptor"] = winner["descriptors"][item["id"]]
            item["source_document"] = winner["source_file"]
            item["source_location"] = winner["source_variable"]
            # Keep 'verified_by', original policy edition, and paraphrases EMPTY.
    out.setdefault("notes", []).append(
        "V2 prefilled candidate only; requires verification of source-code usage, documentary origins and expert-reviewed paraphrases."
    )
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--private-dir", type=Path,
        default=Path("data/revision_private/descriptor_inventory")
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path("docs/audits/reviewer_descriptor_key_match_v2_status.json")
    )
    args = parser.parse_args()
    workspace = Path(__file__).resolve().parent.parent
    directory = private_output(args.private_dir, workspace)
    manifest = directory / "verified_descriptors_PRIVATE.json"
    source = directory / "descriptor_source_candidates_PRIVATE.json"
    if not manifest.exists() or not source.exists():
        raise FileNotFoundError("Original private manifest and inventory are required")

    p_candidates = directory / "descriptor_exact_key_proposals_v2_PRIVATE.json"
    p_template = directory / "descriptor_prefilled_unverified_v2_PRIVATE.json"
    if any(p.exists() for p in (p_candidates, p_template)):
        raise FileExistsError("V2 proposal already exists; inspect, never overwrite")

    doc = json.loads(manifest.read_text(encoding="utf-8"))
    inv = json.loads(source.read_text(encoding="utf-8"))
    resolved = classify_sources(doc, inv)
    proposed = prefill_new_unverified(doc, resolved)
    p_candidates.write_text(
        json.dumps(resolved, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )
    p_template.write_text(
        json.dumps(proposed, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )
    summary = {
        "schema_version": 2,
        "status": "candidate_only_descriptor_reconciliation",
        "source_inventory_sha256": sha256_file(source),
        "n_domains_prefilled": len(resolved["candidate_winners"]),
        "domains": {
            key: {
                "required": entry["expected_labels"],
                "complete_matches": entry["complete_matches"],
                "resolution": entry["resolution"],
                "prefilled_unverified": key in resolved["candidate_winners"],
            } for key, entry in resolved["domains"].items()
        },
        "source_code_usage_verified": False,
        "official_policy_provenance_verified": False,
        "original_manifest_modified": False,
        "semantic_classification_recomputed": False,
        "note": "The output excludes all private descriptor strings. Human review must verify original source-code use, official PDOT edition and needs definitions.",
    }
    dest = write_public(summary, args.output, workspace)
    print("Aggregate-only V2 reconciliation:", dest)
    for key, entry in summary["domains"].items():
        print(key, ":", entry)
    print("Private candidate prefill:", p_template)
    print("No original private template or V1 candidate was overwritten.")


if __name__ == "__main__":
    main()
