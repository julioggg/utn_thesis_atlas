#!/usr/bin/env python3
"""Check each visible NVIDIA MIG compute instance in a separate CUDA process.

For NVIDIA R535/R525, a single CUDA process may enumerate only one MIG compute
instance, even when 'nvidia-smi -L' displays more than one. This diagnostic
uses one short-lived Python child per MIG and writes aggregate device status;
it does not publish MIG UUIDs or HPC paths.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


CHILD = r"""
import json
try:
    import torch
    ok = bool(torch.cuda.is_available())
    devices = int(torch.cuda.device_count())
    record = {"torch_version": torch.__version__,
              "torch_cuda_version": torch.version.cuda,
              "cuda_available": ok,
              "visible_cuda_devices": devices}
    if ok:
        p = torch.cuda.get_device_properties(0)
        record["gpu_name"] = p.name
        record["visible_memory_gib"] = round(p.total_memory / (1024**3), 2)
        record["sum_test"] = float(torch.ones(8, device="cuda").sum().item())
except Exception as e:
    record = {"cuda_available": False, "error_class": type(e).__name__}
print("MIG_PROBE_RESULT=" + json.dumps(record, sort_keys=True))
"""


def detect_mig_uuids(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"UUID:\s*(MIG-[A-Za-z0-9-]+)", text)))


def probe():
    try:
        smi = subprocess.run(["nvidia-smi", "-L"], text=True, capture_output=True,
                             check=True, timeout=20)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {"status": "nvidia_smi_not_available", "error_class": type(exc).__name__}
    migs = detect_mig_uuids(smi.stdout)
    result = {
        "schema_version": 1, "visible_mig_count_in_nvidia_smi": len(migs),
        "per_instance": [], "uuid_values_redacted": True,
        "note": "One separate child process per MIG; a single R535 CUDA process cannot enumerate two MIG compute instances.",
    }
    if not migs:
        result["status"] = "no_mig_instances_listed"
        return result
    for i, mig_uuid in enumerate(migs):
        env = dict(os.environ, CUDA_VISIBLE_DEVICES=mig_uuid)
        try:
            child = subprocess.run([sys.executable, "-c", CHILD],
                                   capture_output=True, text=True, env=env, timeout=120)
            marker = next((line.removeprefix("MIG_PROBE_RESULT=")
                           for line in reversed(child.stdout.splitlines())
                           if line.startswith("MIG_PROBE_RESULT=")), None)
            row = json.loads(marker) if marker else {
                "cuda_available": False, "error_class": "NoProbeResult",
                "exit_code": child.returncode,
            }
        except (subprocess.TimeoutExpired, ValueError, json.JSONDecodeError) as exc:
            row = {"cuda_available": False, "error_class": type(exc).__name__}
        result["per_instance"].append({"mig_slot": i, **row})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("docs/audits/mig_probe.json"))
    a = parser.parse_args()
    report = probe()
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print(f"Sanitized MIG probe written to {a.output}")
    for item in report.get("per_instance", []):
        print(f"Slot {item['mig_slot']}: CUDA={item.get('cuda_available')}; "
              f"device_count={item.get('visible_cuda_devices', 0)}; "
              f"memory_GiB={item.get('visible_memory_gib', 'unknown')}")


if __name__ == "__main__":
    main()
