#!/usr/bin/env python3
"""Run one frozen ChIPs v2.4 synthetic narrow library and record provenance."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--chips", required=True, type=Path)
    parser.add_argument("--chips-source-sha256", required=True)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--peaks", required=True, type=Path)
    parser.add_argument("--sample", required=True, choices=("chip_rep1", "chip_rep2", "input"))
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    simulator = config["simulator"]
    seed_keys = {"chip_rep1": "replicate_1", "chip_rep2": "replicate_2", "input": "input"}
    seed = int(simulator["seeds"][seed_keys[args.sample]])
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    prefix = output_dir / args.sample

    command = [
        str(args.chips.resolve()),
        "simreads",
        "-f",
        str(args.reference.resolve()),
        "-o",
        str(prefix),
        "--numcopies",
        str(simulator["copies"]),
        "--numreads",
        str(simulator["read_pairs_per_library"]),
        "--readlen",
        str(simulator["read_length_bp"]),
        "--paired",
        "--gamma-frag",
        f"{simulator['fragment_gamma_shape']},{simulator['fragment_gamma_scale']}",
        "--pcr_rate",
        str(simulator["pcr_rate"]),
        "--seed",
        str(seed),
        "--thread",
        "1",
    ]
    if args.sample == "input":
        command.extend(["-t", "wce"])
    else:
        command.extend(
            [
                "-p",
                str(args.peaks.resolve()),
                "-t",
                "bed",
                "-c",
                "5",
                "--spot",
                str(simulator["spot"]),
                "--noscale",
            ]
        )

    started = time.time()
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    elapsed = time.time() - started
    (output_dir / f"{args.sample}.stdout.log").write_text(completed.stdout, encoding="utf-8")
    (output_dir / f"{args.sample}.stderr.log").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode:
        raise SystemExit(completed.returncode)

    fastqs = [output_dir / f"{args.sample}_1.fastq", output_dir / f"{args.sample}_2.fastq"]
    if not all(path.is_file() and path.stat().st_size > 0 for path in fastqs):
        raise FileNotFoundError(f"ChIPs did not create paired FASTQs for {args.sample}")
    manifest = {
        "schema_version": "1.0",
        "type": "chips_simulation_library",
        "sample": args.sample,
        "role": "input" if args.sample == "input" else "ChIP",
        "chips_version": "v2.4",
        "chips_commit": simulator["commit"],
        "chips_binary_sha256": sha256(args.chips),
        "chips_source_sha256": args.chips_source_sha256,
        "seed": seed,
        "command": command,
        "parameters": {
            "numcopies": simulator["copies"],
            "numreads": simulator["read_pairs_per_library"],
            "readlen": simulator["read_length_bp"],
            "paired": True,
            "gamma_frag": [simulator["fragment_gamma_shape"], simulator["fragment_gamma_scale"]],
            "pcr_rate": simulator["pcr_rate"],
            "spot": None if args.sample == "input" else simulator["spot"],
            "frac": "ChIPs v2.4 default 0.03713",
            "sequencing_error": "ChIPs v2.4 defaults (sub=0, ins=0, del=0)",
            "noscale": args.sample != "input",
        },
        "reference_sha256": sha256(args.reference),
        "peaks_sha256": None if args.sample == "input" else sha256(args.peaks),
        "elapsed_seconds": round(elapsed, 6),
        "outputs": [
            {"path": path.name, "size_bytes": path.stat().st_size, "sha256": sha256(path)} for path in fastqs
        ],
        "status": "complete",
    }
    (output_dir / f"{args.sample}.simulation.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    main()
