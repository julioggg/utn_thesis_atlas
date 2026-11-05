#!/usr/bin/env python3
"""Conservative staged-file guard for this PUBLIC GitHub repository."""
import re
import subprocess
from pathlib import PurePosixPath

SAFE_ROOTS = {"scripts", "docs", "tests", ".github"}
SAFE_FILES = {".gitignore", "README.md", "LICENSE", "CITATION.cff"}
PUBLIC_REPORTS = {"reports/public/hpc_inventory.json", "reports/public/corpus_audit.json",
                  "reports/public/token_length_audit.json",
                  "reports/public/provenance_audit.json"}
FORBIDDEN_EXTENSIONS = {
    ".pdf", ".docx", ".xlsx", ".zip", ".tar", ".gz", ".7z", ".parquet",
    ".npy", ".npz", ".pkl", ".pickle", ".csv", ".tsv", ".jsonl", ".sqlite",
    ".db", ".pt", ".pth", ".pem", ".key", ".h5",
}
SECRET_PATTERNS = [
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{18,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{18,}"),
]

def main():
    r = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"],
                       stdout=subprocess.PIPE, check=True)
    names = [n.decode("utf-8") for n in r.stdout.split(b"\0") if n]
    failures = []
    for name in names:
        path = PurePosixPath(name)
        if (name not in SAFE_FILES and name not in PUBLIC_REPORTS
            and (not path.parts or path.parts[0] not in SAFE_ROOTS)):
            failures.append(f"{name}: outside approved source/documentation paths")
        if path.suffix.lower() in FORBIDDEN_EXTENSIONS:
            failures.append(f"{name}: prohibited extension")
        if any(p in path.parts for p in ("data", "raw", "texts", "pdfs", "metadata", "private")):
            failures.append(f"{name}: data/private path")
        if name in PUBLIC_REPORTS:
            continue  # aggregate reports require manual inspection as well
        blob = subprocess.run(["git", "show", ":" + name],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
        if len(blob) > 3 * 1024 * 1024:
            failures.append(f"{name}: >3MB; manual review needed")
        elif any(regex.search(blob.decode("utf-8", errors="ignore")) for regex in SECRET_PATTERNS):
            failures.append(f"{name}: possible secret")
    if failures:
        for problem in failures:
            print("BLOCKED:", problem)
        raise SystemExit(2)
    print(f"PASS: {len(names)} staged files match conservative path checks.")
    print("This does NOT replace review for personal data, licenses and sensitive information.")

if __name__ == "__main__":
    main()
