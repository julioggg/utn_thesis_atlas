#!/usr/bin/env python3
"""Public-safe full-corpus thesis structure audit: headings, not deletions.

Read-only CPU scan of 04_clean_corpus.parquet:full_text.
The heuristics are intentionally conservative: a bibliography is detected
only from a STANDALONE line near the end; a mention in the text is NOT a
heading. No individual document records or raw text are written to the
public aggregate report. This is NOT a parser or a preprocessing pipeline.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter
from pathlib import Path

from audit_chunk_budget import summary

HEADING_PREFIX = (
    r"[ \t]*(?:(?:cap[ií]tulo|chapter)[ \t]+(?:[IVXivx]+|[0-9]+)[ \t]*[.:\-]?[ \t]*)?"
    r"(?:(?:[IVXivx]+|[0-9]+(?:\.[0-9]+){0,3})[.:\-)]?[ \t]*)?"
)
HEADING_SUFFIX = r"[ \t]*[.:\-]?[ \t]*$"

PATTERNS = {
    "references": re.compile(
        "^" + HEADING_PREFIX +
        r"(?:referencias(?:[ \t]+bibliogr[aá]ficas)?|bibliograf[ií]a|"
        r"references|bibliography|works[ \t]+cited)"
        + HEADING_SUFFIX, re.IGNORECASE | re.MULTILINE
    ),
    "introduction": re.compile(
        "^" + HEADING_PREFIX + r"(?:introducci[oó]n|introduction)"
        + HEADING_SUFFIX, re.IGNORECASE | re.MULTILINE
    ),
    "methodology": re.compile(
        "^" + HEADING_PREFIX + r"(?:metodolog[ií]a|materiales[ \t]+y[ \t]+m[eé]todos|"
        r"materials[ \t]+and[ \t]+methods|methods)"
        + HEADING_SUFFIX, re.IGNORECASE | re.MULTILINE
    ),
    "results": re.compile(
        "^" + HEADING_PREFIX + r"(?:resultados(?:[ \t]+y[ \t]+discusi[oó]n)?|"
        r"results(?:[ \t]+and[ \t]+discussion)?)"
        + HEADING_SUFFIX, re.IGNORECASE | re.MULTILINE
    ),
    "conclusions": re.compile(
        "^" + HEADING_PREFIX + r"(?:conclusiones|conclusions)"
        + HEADING_SUFFIX, re.IGNORECASE | re.MULTILINE
    ),
    "appendix": re.compile(
        "^" + HEADING_PREFIX + r"(?:anexos?|ap[eé]ndices?|appendices|appendix)"
        + HEADING_SUFFIX, re.IGNORECASE | re.MULTILINE
    ),
    "abstract": re.compile(
        "^" + HEADING_PREFIX + r"(?:resumen|abstract)"
        + HEADING_SUFFIX, re.IGNORECASE | re.MULTILINE
    ),
}
KNOWN_HEADINGS = tuple(PATTERNS)


def analyze_text(text: str, late_fraction: float = 0.55):
    """Return only position statistics; never source text, snippets or IDs."""
    if not isinstance(text, str) or not text:
        return {
            "chars": 0, "linebreaks": 0, "headings": {},
            "late_reference": False, "early_reference_only": False,
            "late_reference_position": None, "after_reference_fraction": None,
            "found_any_reference": False,
            "appendix_after_reference": False,
            "distinct_headings": 0,
        }
    n = len(text)
    matches = {name: [m.start() / n for m in pattern.finditer(text)]
               for name, pattern in PATTERNS.items()}
    late_ref = [pos for pos in matches["references"] if late_fraction <= pos <= .99]
    early_only = bool(matches["references"] and not late_ref)
    # Most downstream applications place bibliography near the last third,
    # but this is only a plausible candidate boundary, not a verified section.
    boundary = late_ref[-1] if late_ref else None
    appendix_after = bool(
        boundary is not None and any(pos > boundary for pos in matches["appendix"])
    )
    return {
        "chars": n,
        "linebreaks": text.count("\n"),
        "headings": {key: len(positions) for key, positions in matches.items()},
        "late_reference": bool(late_ref),
        "early_reference_only": early_only,
        "late_reference_position": boundary,
        "after_reference_fraction": 1.0 - boundary if boundary is not None else None,
        "found_any_reference": bool(matches["references"]),
        "appendix_after_reference": appendix_after,
        "distinct_headings": sum(bool(x) for x in matches.values()),
    }


def census(source: Path, min_late_fraction: float = .55):
    import pyarrow.parquet as pq
    p = pq.ParquetFile(source)
    if "full_text" not in p.schema_arrow.names:
        raise ValueError("Expected original corpus full_text column")
    counts = Counter()
    headings = Counter()
    ref_position = []
    ref_tail = []
    chars = []
    n = 0
    start = time.perf_counter()
    for batch in p.iter_batches(columns=["full_text"], batch_size=32):
        for value in batch.column(0):
            result = analyze_text(value.as_py() or "", min_late_fraction)
            n += 1
            chars.append(result["chars"])
            if result["chars"] == 0:
                counts["empty_fulltext"] += 1
            if result["linebreaks"] == 0:
                counts["no_linebreaks"] += 1
            if result["found_any_reference"]:
                counts["any_standalone_reference_heading"] += 1
            if result["late_reference"]:
                counts["late_reference_heading_candidate"] += 1
                ref_position.append(result["late_reference_position"])
                ref_tail.append(result["after_reference_fraction"])
            if result["early_reference_only"]:
                counts["early_reference_only"] += 1
            if result["appendix_after_reference"]:
                counts["appendix_after_late_reference"] += 1
            if result["distinct_headings"] >= 4:
                counts["at_least_four_heading_types"] += 1
            for key, found in result["headings"].items():
                if found:
                    headings[key] += 1
    if n != p.metadata.num_rows:
        raise AssertionError("Parquet row count differs from streaming census")
    return {
        "schema_version": 1,
        "status": "complete_original_thesis_structure_audit",
        "source": "04_clean_corpus.parquet:full_text",
        "population_rows": n,
        "heading_detection": "standalone newline-delimited titles; case-insensitive ES/EN",
        "late_heading_definition": f"at or after {min_late_fraction:.2f} of extracted text",
        "n_original_empty_texts": int(counts["empty_fulltext"]),
        "n_without_linebreaks": int(counts["no_linebreaks"]),
        "n_with_any_standalone_reference_heading": int(counts["any_standalone_reference_heading"]),
        "n_with_late_reference_heading_candidate": int(counts["late_reference_heading_candidate"]),
        "n_with_reference_heading_only_in_early_text": int(counts["early_reference_only"]),
        "n_with_appendix_after_late_reference": int(counts["appendix_after_late_reference"]),
        "n_with_at_least_four_heading_types": int(counts["at_least_four_heading_types"]),
        "document_count_with_each_heading_type": dict(sorted(headings.items())),
        "late_reference_position_distribution": summary(ref_position),
        "tail_char_fraction_after_late_reference_heading": summary(ref_tail),
        "total_fulltext_characters": int(sum(chars)),
        "elapsed_cpu_seconds": round(time.perf_counter() - start, 3),
        "limitations": [
            "Standalone heading regex is a candidate detector, NOT validated section labeling.",
            "Headings may be absent, mistranscribed or included in a table of contents.",
            "A late bibliography heading does NOT prove that all trailing text is irrelevant.",
            "No text removal or E5 retokenization/inference was performed.",
            "No identifiers, titles, author information, section excerpts or raw document texts are exported.",
            "Review document-level section boundaries privately before using them in an embedding pipeline.",
        ],
    }


def main():
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--project-root", type=Path, required=True)
    a.add_argument("--late-fraction", type=float, default=.55)
    a.add_argument("--output", type=Path,
                   default=Path("docs/audits/thesis_structure_census.json"))
    args = a.parse_args()
    if not 0.3 <= args.late_fraction <= 0.9:
        a.error("Require late fraction between 0.3 and 0.9")
    corpus = args.project_root.expanduser().resolve() / "data/processed/04_clean_corpus.parquet"
    result = census(corpus, args.late_fraction)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(f"Scanned {result['population_rows']} theses, "
          f"late-reference candidates={result['n_with_late_reference_heading_candidate']}")
    print(f"Saved aggregate section audit: {args.output}")
    print("No thesis text or identifiers exported. No source data modified.")


if __name__ == "__main__":
    main()
