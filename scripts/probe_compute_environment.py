#!/usr/bin/env python3
"""Public-safe probe of available inference tools in the CURRENT HPC environment.

No hostname, username, absolute paths, scheduler job names or credentials saved.
Run inside a CEDIA compute allocation; a login-node result does not describe the
GPU available in a subsequently allocated job.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import platform
import shutil
from pathlib import Path


def probe():
    report = {
        "schema_version": 1,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "scheduler_client_available": {
            "sbatch": shutil.which("sbatch") is not None,
            "srun": shutil.which("srun") is not None,
        },
        "installed_modules": {
            name: importlib.util.find_spec(name) is not None
            for name in ("torch", "transformers", "sentence_transformers", "numpy", "pandas", "pyarrow")
        },
        "torch": {"imported": False},
        "interpretation": "Report describes only the current Python process/container and hardware allocation.",
    }
    if report["installed_modules"]["torch"]:
        try:
            import torch
            cuda = bool(torch.cuda.is_available())
            devices = []
            if cuda:
                for index in range(torch.cuda.device_count()):
                    p = torch.cuda.get_device_properties(index)
                    devices.append({
                        "index": index,
                        "name": p.name,
                        "total_memory_gib": round(p.total_memory / (1024**3), 2),
                    })
            report["torch"] = {
                "imported": True, "version": torch.__version__,
                "compiled_cuda_version": torch.version.cuda,
                "cuda_available": cuda, "devices": devices,
            }
        except Exception as exc:
            report["torch"] = {
                "imported": False, "error_class": type(exc).__name__,
                "error_message_redacted": True,
            }
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, default=Path("docs/audits/compute_probe.json"))
    args = p.parse_args()
    out = probe()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote hardware/software probe to {args.output}")
    print("CUDA available:", out.get("torch", {}).get("cuda_available", False))
    print("No hostname, paths or dataset information exported.")


if __name__ == "__main__":
    main()
