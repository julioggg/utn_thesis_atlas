#!/usr/bin/env python3
"""Review-analyses utilities. No dependencies beyond numpy/pandas in the functions.

These helpers must never write source handles, advisor names, full text,
student records or embedding vectors to public audit JSON.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path

FIVE_FACULTIES = (
    "Facultad de Ingeniería en Ciencias Aplicadas",
    "Facultad de Educación Ciencia y Tecnología",
    "Facultad de Ciencias Administrativas y Económicas",
    "Facultad de Ciencias de la Salud",
    "Facultad de Ingeniería en Ciencias Agropecuarias y Ambientales",
)

def summary(values):
    import numpy as np
    a = np.asarray(values, dtype="float64").ravel()
    a = a[np.isfinite(a)]
    if a.size == 0:
        return {"n": 0}
    return {
        "n": int(a.size), "min": round(float(a.min()), 6),
        "p05": round(float(np.percentile(a, 5)), 6),
        "median": round(float(np.median(a)), 6),
        "p95": round(float(np.percentile(a, 95)), 6),
        "max": round(float(a.max()), 6),
        "mean": round(float(a.mean()), 6),
    }

def bh_adjust(pvalues):
    """Benjamini-Hochberg, preserving original order."""
    import numpy as np
    vals = np.asarray(pvalues, dtype="float64")
    if len(vals) == 0:
        return []
    if not np.isfinite(vals).all() or (vals < 0).any() or (vals > 1).any():
        raise ValueError("Invalid p values")
    order = np.argsort(vals, kind="stable")
    out = np.empty(len(vals), dtype="float64")
    last = 1.0
    for pos in range(len(vals) - 1, -1, -1):
        idx = int(order[pos])
        last = min(last, vals[idx] * len(vals) / (pos + 1))
        out[idx] = last
    return [round(float(x), 9) for x in out]

def normalized_entropy(counts):
    import numpy as np
    x = np.asarray(counts, dtype="float64")
    if np.any(x < 0) or x.ndim != 1:
        raise ValueError("Counts should be a nonnegative vector")
    if x.sum() <= 0:
        return 0.
    p = x[x > 0] / x.sum()
    return float(-(p * np.log(p)).sum() / math.log(len(x))) if len(x) > 1 else 0.

def read_original_embeddings(root, n):
    import numpy as np
    from audit_embedding_comparison import check_row_alignment
    n_verified, alignment = check_row_alignment(root)
    if n_verified != n:
        raise ValueError("Embedding index and analytical corpus sizes differ")
    x = np.load(root / "data/processed/05_embeddings.npy", mmap_mode="r", allow_pickle=False)
    if x.shape != (n, 1024):
        raise ValueError("Original embedding array must be N x 1024 and aligned")
    return x, alignment

def normalize_codes(values):
    """Normalize SDG number without guessing codes from arbitrary titles."""
    import re
    codes = []
    for label in values:
        match = re.search(r"\b(?:ODS|SDG)\s*0?([1-9]|1[0-7])\b", str(label), re.IGNORECASE)
        codes.append("ODS " + str(int(match.group(1))) if match else "[invalid]")
    return codes

def ensure_public_output(path, workspace):
    target = Path(path).expanduser().resolve()
    root = (Path(workspace).resolve() / "docs/audits").resolve()
    if not target.is_relative_to(root):
        raise ValueError("Public-candidate report must be written under docs/audits")
    target.parent.mkdir(parents=True, exist_ok=True)
    return target

def private_output(path, workspace):
    target = Path(path).expanduser().resolve()
    root = (Path(workspace).resolve() / "data").resolve()
    if not target.is_relative_to(root):
        raise ValueError("Private outputs must stay under revision/data")
    target.mkdir(parents=True, exist_ok=True)
    return target

def write_public(report, target, workspace):
    """No raw text, identifiers or vectors may be placed in 'report'."""
    target = ensure_public_output(target, workspace)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target

def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def z_two_sided(z):
    return math.erfc(abs(float(z)) / math.sqrt(2))
