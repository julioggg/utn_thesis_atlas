#!/usr/bin/env bash
# Single auditable CEDIA entrypoint. Builds and publishes ONLY aggregate assets.
# NEVER stages original thesis data, private annotations, model arrays, or PDFs.
set -euo pipefail

REPO="$HOME/utn_thesis_atlas_revision"
PROJECT="$HOME/utn_thesis_atlas"
cd "$REPO"

if [ -n "$(git diff --cached --name-only)" ]; then
  echo "ERROR: Existing staged changes; refuse potentially unsafe automatic push." >&2
  exit 2
fi
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "ERROR: Git working tree has modifications; preserve them before running." >&2
  exit 2
fi
git pull --ff-only origin main

# Use the existing audited CEDIA environment; never install packages to
# the original model workspace or silently update its model dependencies.
if [ -f "$HOME/.venvs/utn-atlas-audit/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$HOME/.venvs/utn-atlas-audit/bin/activate"
else
  echo "ERROR: Existing CEDIA audit Python virtual environment is missing." >&2
  exit 2
fi

SNAPSHOT="data/revision_private/manuscript_release_v1/model_snapshot_PRIVATE.parquet"
AUDIT="docs/revision_assets/v1/model_snapshot_audit.json"
if [[ ! -f "$SNAPSHOT" && ! -f "$AUDIT" ]]; then
  python scripts/reviewer_freeze_manuscript_snapshot.py \
    --project-root "$PROJECT" --variant fulltext_centered
elif [[ -f "$SNAPSHOT" && -f "$AUDIT" ]]; then
  echo "Existing snapshot and audit found; verifying frozen SHA in builder."
else
  echo "ERROR: Partial snapshot detected. Do not overwrite; investigate first." >&2
  exit 2
fi

python scripts/reviewer_build_manuscript_assets.py
echo "=== Validating English, aggregate, 600+ DPI release ==="
python - <<'PY'
import json
import pathlib
import struct

base=pathlib.Path("docs/revision_assets/v1")
manifest=json.loads((base/"RELEASE_MANIFEST.json").read_text())
assert manifest["status"]=="release_candidate_aggregate_no_row_level_data"
assert manifest["n_figure_panels"]>=8
assert manifest["n_tables"]>=9
assert manifest["raster_png_dpi"]>=600
actual={str(p.relative_to(base)) for p in base.rglob("*") if p.is_file()}
expected=set(manifest["files_sha256"])|{"RELEASE_MANIFEST.json"}
assert actual==expected, ("Unexpected public files", actual^expected)
for p in base.glob("figures/*.png"):
    b=p.read_bytes()[:180]
    assert b[:8]==b"\x89PNG\r\n\x1a\n"
    pos=b.find(b"pHYs")
    assert pos!=-1, "PNG is missing its physically declared dpi"
    x,y,unit=struct.unpack(">IIB", b[pos+4:pos+13])
    assert unit==1 and x/39.3701>=599 and y/39.3701>=599
for key in ("Table_01_Corpus_Profile.csv","Table_02_SDG_Top1_Affinities.csv",
            "Table_03_PDOT_Top1_Affinities.csv","Table_04_Local_Needs_Separate_Measures.csv",
            "Table_05_Five_Faculty_Association.csv",
            "Table_06_Classifier_Accuracy_and_MacroF1.csv",
            "Table_07_Human_Interrater_Agreement.csv",
            "Table_08_Topic_Share_Change.csv"):
    assert (base/"tables"/key).exists(),key
print("Verified",len(list(base.glob("figures/*.png"))),
      "publication PNG figures at >=600dpi and",
      len(list(base.glob("tables/*.csv"))),"aggregate tables.")
print("All generated files are inside",base)
PY

# Force-add only the exact, vetted aggregate publication directory, because
# repository .gitignore intentionally blocks *.csv and *.pdf globally.
git add -f -- docs/revision_assets/v1
staged="$(git diff --cached --name-only)"
if [ -z "$staged" ]; then
  echo "No changes in public aggregate exhibits; nothing to commit."
  exit 0
fi
if echo "$staged" | grep -Ev '^docs/revision_assets/v1/' >/dev/null; then
  echo "ERROR: Refusing any staged path outside vetted public aggregate release." >&2
  git reset -q
  exit 3
fi

# Avoid repository-size/privacy surprises: only static aggregate formats allowed.
while IFS= read -r file; do
  case "$file" in
    docs/revision_assets/v1/*.json|docs/revision_assets/v1/*.md|\
    docs/revision_assets/v1/figures/*.png|docs/revision_assets/v1/figures/*.pdf|\
    docs/revision_assets/v1/figures/*.svg|\
    docs/revision_assets/v1/tables/*.csv|docs/revision_assets/v1/tables/*.md)
      ;;
    *) echo "ERROR: File not allowlisted for public commit: $file" >&2
       git reset -q; exit 3 ;;
  esac
  size="$(wc -c < "$file")"
  if [ "$size" -gt 30000000 ]; then
    echo "ERROR: Very large release file requires manual review: $file" >&2
    git reset -q; exit 3
  fi
done <<< "$staged"

git diff --cached --check
git commit -m "Publish vetted 600+ dpi English manuscript figures, aggregate tables and numbers lock"
git push origin main
echo
echo "SUCCESS — public aggregate manuscript assets:"
echo "https://github.com/julioggg/utn_thesis_atlas/tree/main/docs/revision_assets/v1"
echo "Never upload private source Excel, thesis text or model NPZ to this public repository."
