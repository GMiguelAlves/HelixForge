#!/usr/bin/env python3
"""Compare deterministic null-generator runs and freeze validated null sets."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path

from evaluate_real_narrow import sha256


FILES_TO_COMPARE = ("null_sets.tsv.gz", "strata_audit.tsv", "null_set_audit.tsv")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if "SLURM_JOB_ID" not in os.environ:
        raise RuntimeError("null freezing must run in a Slurm allocation")
    root = args.benchmark_root.resolve()
    expected = Path("/scratch/Schisto-epigenetics/gustavo/helixforge-chipseq-real-narrow-benchmark-20260830")
    if root != expected or args.output_dir.exists():
        raise ValueError("unexpected benchmark root or existing frozen-null output")

    run_a, run_b = root / "null_validation/run_a", root / "null_validation/run_b"
    manifests = [json.loads((run / "manifest.json").read_text(encoding="utf-8")) for run in (run_a, run_b)]
    if any(manifest["status"] != "validated" for manifest in manifests):
        raise RuntimeError("both null-generator runs must pass validation")

    comparisons = {}
    for filename in FILES_TO_COMPARE:
        first, second = sha256(run_a / filename), sha256(run_b / filename)
        comparisons[filename] = {"run_a_sha256": first, "run_b_sha256": second, "identical": first == second}
    if not all(item["identical"] for item in comparisons.values()):
        raise RuntimeError("deterministic null-generator outputs are not byte-identical")

    args.output_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".real-narrow-null-frozen.", dir=args.output_dir.parent))
    try:
        for filename in FILES_TO_COMPARE:
            shutil.copy2(run_a / filename, stage / filename)
        manifest = {
            "schema_version": "1.0",
            "status": "frozen",
            "phase": "VALIDATED_NULL_FREEZE",
            "master_seed": manifests[0]["master_seed"],
            "null_sets": manifests[0]["null_sets"],
            "rn3": {"calculated": False},
            "source_runs": {
                "run_a_slurm_job_id": manifests[0]["slurm_job_id"],
                "run_b_slurm_job_id": manifests[1]["slurm_job_id"],
            },
            "comparisons": comparisons,
            "null_sets_sha256": comparisons["null_sets.tsv.gz"]["run_a_sha256"],
            "freeze_slurm_job_id": os.environ["SLURM_JOB_ID"],
        }
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        with (stage / "checksums.sha256").open("w", encoding="ascii", newline="\n") as handle:
            for path in sorted(item for item in stage.iterdir() if item.is_file() and item.name != "checksums.sha256"):
                handle.write(f"{sha256(path)}  {path.name}\n")
        os.replace(stage, args.output_dir)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    print(json.dumps({"status": "frozen", "null_sets_sha256": manifest["null_sets_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

