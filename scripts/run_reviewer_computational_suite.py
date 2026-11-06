#!/usr/bin/env python3
"""One-command reviewer computational-suite runner on private CEDIA HPC.

No direct remote access is assumed; you MUST run this in Singularity with the
already configured audit environment and access to original project files.
Stages are independent. Sensitive stdout/stderr remain in ignored data/.
Only safe stage status and completed aggregate-report names are summarized
under docs/audits. NEVER automatically commit or push private outputs.
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

from reviewer_shared import private_output, write_public

STAGES={
    "stats":("reviewer_stage1_stats.py","reviewer_stage1_statistics.json"),
    "geometry":("reviewer_stage2_geometry.py","reviewer_stage2_geometry_trends.json"),
    "stability":("reviewer_stage3_stability.py","reviewer_stage3_stability.json"),
    "figures":("reviewer_rebuild_figures.py","reviewer_figure_reconciliation.json"),
    "inventory":("reviewer_descriptor_inventory.py","descriptor_source_inventory.json"),
    "template":("reviewer_prepare_descriptors.py","descriptor_template_status.json"),
    "alternate":("reviewer_alternate_encoder_pilot.py","reviewer_alternate_encoder_pilot.json"),
    "descriptors":("reviewer_descriptor_sensitivity.py","reviewer_descriptor_sensitivity.json"),
    "keywords":("reviewer_keyword_baseline.py","reviewer_keyword_baseline.json"),
}
DEFAULT=("stats","geometry","stability","figures","inventory","alternate")


def parse_stages(argument):
    selection=list(STAGES) if argument.strip().lower()=="all" else [
        s.strip() for s in argument.split(",") if s.strip()
    ]
    if not selection or len(selection)!=len(set(selection)) or any(s not in STAGES for s in selection):
        raise ValueError("Invalid stage list, duplicates or unknown stages")
    return selection


def verified_manifest(path):
    if not path.is_file():
        return False
    try:
        data=json.loads(path.read_text(encoding="utf-8"))
        return data.get("verified") is True
    except (ValueError, OSError):
        return False


def run_stage(stage, root, workspace, private_logs, allow_download, resume=False):
    script,filename=STAGES[stage]
    public=workspace/"docs/audits"/filename
    if resume and public.is_file():
        return {"stage":stage,"status":"skipped_existing_report","report_file":filename}
    manifest=(workspace/"data/revision_private/descriptor_inventory/"
              "verified_descriptors_PRIVATE.json")
    if stage in {"descriptors","keywords"} and not verified_manifest(manifest):
        return {
            "stage":stage,"status":"blocked_pending_verified_descriptor_manifest",
            "report_file":None,
        }
    if stage=="template" and manifest.is_file():
        return {
            "stage":stage,"status":"skipped_existing_private_manifest_do_not_overwrite",
            "report_file":None,
        }
    cmd=[sys.executable,str(workspace/"scripts"/script),
         "--project-root",str(root)]
    if stage=="figures":
        cmd.append("--render-figures")
    if stage=="alternate":
        cmd.extend(["--documents","36"])
        if allow_download:
            cmd.append("--allow-download")
    if stage=="descriptors":
        cmd.append("--local-files-only")
    if stage=="inventory":
        cmd.extend(["--output",str(public)])
    if stage=="template":
        cmd.extend(["--report",str(public)])
    else:
        if stage!="inventory":
            cmd.extend(["--output",str(public)])
    start=time.perf_counter()
    completed=subprocess.run(cmd,cwd=workspace,stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT,text=True,check=False)
    elapsed=round(time.perf_counter()-start,3)
    log=private_logs/(stage+".log")
    log.write_text(completed.stdout,encoding="utf-8")
    if completed.returncode:
        return {
            "stage":stage,"status":"failed_see_private_log",
            "exit_code":completed.returncode,"elapsed_seconds":elapsed,
            "private_log_name":stage+".log","report_file":None,
        }
    if not public.is_file():
        return {
            "stage":stage,"status":"failed_missing_expected_aggregate",
            "elapsed_seconds":elapsed,"private_log_name":stage+".log",
            "report_file":None,
        }
    # Do not include contents from the child report in this suite status.
    return {
        "stage":stage,"status":"completed_aggregate_saved",
        "elapsed_seconds":elapsed,"report_file":filename,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root",type=Path,required=True)
    p.add_argument("--stages",default=",".join(DEFAULT))
    p.add_argument("--allow-model-download",action="store_true")
    p.add_argument("--resume",action="store_true",
                   help="Skip stage if its aggregate JSON already exists. Use only for trusted results.")
    p.add_argument("--suite-id",default="reviewer_suite_v1")
    p.add_argument("--output",type=Path,
                   default=Path("docs/audits/reviewer_suite_run_status.json"))
    args=p.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,48}",args.suite_id):
        p.error("Invalid suite ID")
    try:
        stages=parse_stages(args.stages)
    except ValueError as err:
        p.error(str(err))
    workspace=Path(__file__).resolve().parent.parent
    root=args.project_root.expanduser().resolve()
    if not (root/"data/processed/07_alignment_pdot_ods_needs.parquet").is_file():
        p.error("Original private 07 alignment parquet not accessible")
    logs=private_output(
        workspace/"data/revision_private/computational_suite"/args.suite_id,
        workspace
    )
    progress=[]
    for stage in stages:
        print(f"Running stage: {stage}",flush=True)
        status=run_stage(stage,root,workspace,logs,args.allow_model_download,args.resume)
        progress.append(status)
        print(f"  {status['status']}",flush=True)
    report={
        "schema_version":1,
        "status":"computational_suite_attempted_not_human_validation",
        "stages_requested":stages,
        "stage_results":progress,
        "n_success":sum(x["status"]=="completed_aggregate_saved" for x in progress),
        "n_blocked":sum(x["status"].startswith("blocked_") for x in progress),
        "n_failed":sum(x["status"].startswith("failed_") for x in progress),
        "private_logs_only":True,
        "human_annotations_or_F1_generated":False,
        "notes":[
            "Private logs and all row-level outputs stay under ignored CEDIA data/.",
            "Review each aggregate report manually before publishing to public GitHub.",
            "This suite analyzes the original embeddings and prepared alternatives; not yet an approved final 7830-thesis fulltext regeneration.",
            "Descriptor sensitivity and lexical baseline remain blocked without the original source-verified taxonomies.",
            "Any failure must be investigated from private logs; do not report failed stages as completed.",
        ]
    }
    write_public(report,args.output,workspace)
    print("Computational suite status:",args.output)
    if report["n_failed"]:
        print("Some stages failed; inspect private logs before continuing.",file=sys.stderr)
        raise SystemExit(2)


if __name__=="__main__":
    main()
