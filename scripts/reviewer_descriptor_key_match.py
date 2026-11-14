#!/usr/bin/env python3
"""Propose exact taxonomy-key matches from original source descriptors, privately.

Never executes source scripts. Never interprets list order as taxonomy
order. Never marks descriptors verified, never overwrites the original
verified_descriptors_PRIVATE.json, and never publishes descriptor strings.
No human label or accuracy claim is generated.
"""
from __future__ import annotations
import argparse
import json
import re
import unicodedata
from pathlib import Path
from reviewer_shared import private_output, sha256_file, write_public

DOMAIN_SIZES = {"ods": 17, "pdot": 6, "need": 10}


def normalize_label(text):
    s = unicodedata.normalize("NFKD", str(text).casefold())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+", s))


def sdg_key(text):
    k = normalize_label(text)
    match = re.fullmatch(r"(?:(?:ods|sdg|goal|objetivo)\s+)?0?([1-9]|1[0-7])", k)
    if not match:
        return None
    return f"ODS {int(match.group(1))}"


def match_candidate(candidate, ids):
    """Only unambiguous exact category keys or numbers; never positional guess."""
    raw = candidate["candidate_literal"]
    expected = set(ids)
    source = {
        "relative_source_path": candidate.get("relative_source_path"),
        "variable_name": candidate.get("variable_name"),
        "taxonomy_guess": candidate.get("taxonomy_guess"),
        "number_of_entries": candidate.get("number_of_entries"),
    }
    if not isinstance(raw, dict):
        return {
            **source, "matched": False,
            "reason": "sequence_has_no_verified_category_key_order",
            "possible_labels": [],
        }
    if len(raw) != len(expected):
        return {
            **source, "matched": False,
            "reason": "entry_count_differs_from_taxonomy",
            "possible_labels": [],
        }
    found = {}
    for key, text in raw.items():
        if not isinstance(text, str) or not text.strip():
            return {**source, "matched": False, "reason": "missing_or_non_string_description",
                    "possible_labels": []}
        if all(str(s).startswith("ODS ") for s in ids):
            mapped = sdg_key(key)
        else:
            nk = normalize_label(key)
            choices = [value for value in ids if normalize_label(value) == nk]
            mapped = choices[0] if len(choices) == 1 else None
        if mapped is None or mapped not in expected or mapped in found:
            return {
                **source, "matched": False,
                "reason": "missing_or_ambiguous_exact_key_mapping",
                "possible_labels": sorted(found),
            }
        found[mapped] = text
    if set(found) != expected:
        return {**source, "matched": False, "reason": "category_set_incomplete",
                "possible_labels": sorted(found)}
    return {
        **source, "matched": True,
        "reason": "one_to_one_exact_category_keys",
        "possible_labels": sorted(found),
        "proposed_descriptors": found,
    }


def propose(template, inventory):
    if template.get("verified") is not False:
        raise ValueError("The supplied template is already verified; refuse mutation")
    if inventory.get("status") != "unverified_ast_descriptor_candidates":
        raise ValueError("Not the original AST inventory")
    taxa = template["taxonomies"]
    out = {"schema_version": 1, "status": "unverified_exact_key_match_proposals",
           "source_documents": inventory.get("candidate_source_inventory", []),
           "proposals": {}, "matched_domains": [],
           "notes": [
               "These are string-key matching proposals, NOT official SDG/PDOT verification.",
               "A list/tuple has no defensible category order without reviewing original scoring code.",
               "Two or more complete candidates for a domain are deliberately marked ambiguous.",
               "Source code and policy-document provenance must still be checked by a researcher.",
               "No human annotation, cosine scoring, classification F1, or PDOT validity is inferred.",
           ]}
    for domain, size in DOMAIN_SIZES.items():
        categories = [x["id"] for x in taxa[domain]]
        if len(categories) != size or len(set(categories)) != size:
            raise ValueError(f"Invalid {domain} category template")
        possibles = []
        for c in inventory["literal_candidates"]:
            if c["number_of_entries"] != size:
                continue
            # Do NOT constrain by name: a variable could have a different
            # prefix; require exact category keys rather than keyword guesses.
            possibles.append(match_candidate(c, categories))
        complete = [p for p in possibles if p["matched"]]
        # Remove texts from summary-only candidates to prevent accidental
        # unreviewed descriptor duplication in the result's status area.
        out["proposals"][domain] = {
            "target_categories": size,
            "all_candidates": possibles,
            "uniquely_mapped_by_keys": len(complete) == 1,
            "number_of_complete_key_matches": len(complete),
        }
        if len(complete) == 1:
            out["matched_domains"].append(domain)
    return out


def make_prefilled(template, proposal):
    """Returns separate UNVERIFIED file; leaves original template unchanged."""
    revised = json.loads(json.dumps(template, ensure_ascii=False))
    revised["status"] = "PREFILLED_CANDIDATE_REQUIRES_HUMAN_SOURCE_VALIDATION"
    revised["verified"] = False
    revised.setdefault("notes", []).append(
        "Exact source keys were matched automatically; never mark verified without source and policy review."
    )
    for domain in proposal["matched_domains"]:
        candidates = proposal["proposals"][domain]["all_candidates"]
        winner = next(x for x in candidates if x["matched"])
        for row in revised["taxonomies"][domain]:
            if row["descriptor"].strip():
                raise ValueError("Refusing to overwrite a preexisting descriptor")
            row["descriptor"] = winner["proposed_descriptors"][row["id"]]
            row["source_document"] = winner["relative_source_path"] or ""
            row["source_location"] = winner["variable_name"] or ""
            # Keep paraphrases, PDOT official edition, needs provenance,
            # reviewer and verified flag unfilled.
    return revised


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--private-dir", type=Path,
                   default=Path("data/revision_private/descriptor_inventory"))
    p.add_argument("--report", type=Path,
                   default=Path("docs/audits/reviewer_descriptor_key_match_status.json"))
    args = p.parse_args()
    workspace = Path(__file__).resolve().parent.parent
    directory = private_output(args.private_dir, workspace)
    template = directory / "verified_descriptors_PRIVATE.json"
    inventory = directory / "descriptor_source_candidates_PRIVATE.json"
    if not template.is_file() or not inventory.is_file():
        raise FileNotFoundError("Expected private manifest and AST inventory are missing")
    proposal_path = directory / "descriptor_exact_key_proposals_PRIVATE.json"
    prefilled_path = directory / "descriptor_prefilled_unverified_PRIVATE.json"
    if proposal_path.exists() or prefilled_path.exists():
        raise FileExistsError("Proposal files already exist; inspect instead of overwriting")
    a = json.loads(template.read_text(encoding="utf-8"))
    b = json.loads(inventory.read_text(encoding="utf-8"))
    generated = propose(a,b)
    prefilled = make_prefilled(a,generated)
    proposal_path.write_text(json.dumps(generated,ensure_ascii=False,indent=2)+"\n",
                             encoding="utf-8")
    prefilled_path.write_text(json.dumps(prefilled,ensure_ascii=False,indent=2)+"\n",
                              encoding="utf-8")
    summary = {
        "schema_version":1,
        "status":"unverified_descriptor_key_matching_completed",
        "source_inventory_sha256":sha256_file(inventory),
        "private_template_sha256":sha256_file(template),
        "taxonomies": {
            d: {
                "required": DOMAIN_SIZES[d],
                "candidates_matching_expected_entry_count":
                    len(generated["proposals"][d]["all_candidates"]),
                "complete_unambiguous_key_match":
                    generated["proposals"][d]["uniquely_mapped_by_keys"],
                "number_of_complete_key_matches":
                    generated["proposals"][d]["number_of_complete_key_matches"],
            } for d in DOMAIN_SIZES
        },
        "source_verified": False,
        "source_policy_verified": False,
        "models_or_legacy_predictions_recomputed": False,
        "note": "Private proposals, source strings and candidate prefill remain git-ignored; original manifest untouched.",
    }
    write_public(summary,args.report,workspace)
    print("Candidate-only key matches (NOT official source verification):")
    for domain,status in summary["taxonomies"].items():
        print(domain,":",status)
    print("Private candidate files:",proposal_path.name,prefilled_path.name)
    print("No original files overwritten; human documentary verification still mandatory.")


if __name__ == "__main__":
    main()
