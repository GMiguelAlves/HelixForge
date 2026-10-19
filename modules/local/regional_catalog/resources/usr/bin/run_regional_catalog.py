#!/usr/bin/env python3
"""Regional candidate envelopes and spatial support; never infer occupancy FDR."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

VERSION = "1.0.0"


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def write_table(path, fields, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def validate_request(request, directories):
    if request.get("status") != "valid" or request.get("strategy") != "regional_catalog" or request.get("provider") != "regional_catalog_v1" or request.get("provider_version") != VERSION:
        raise ValueError("Expected a validated regional_catalog_v1 1.0.0 request")
    reps = request["replicates"]
    ids = [r["evidence_replicate_id"] for r in reps]
    if len(ids) < 2 or len(set(ids)) != len(ids) or request["replicate_count"] != len(ids):
        raise ValueError("Distinct evidence units are required")
    if any(not re.fullmatch(r"[A-Za-z0-9._-]+", name) for name in ids):
        raise ValueError("Evidence IDs must be unambiguous BEDTools names")
    k = request["support_threshold"]
    if type(k) is not int or not 2 <= k <= len(ids):
        raise ValueError("Explicit integer support threshold required")
    if request["peak_type"] != "broad" or any(r["peak_type"] != "broad" for r in reps):
        raise ValueError("Only broadPeak inputs are supported")
    if any(r["peak_directory"] not in directories for r in reps):
        raise ValueError("Missing staged peak directory")
    return ids, k


def read_atoms(path, names):
    atoms, last = [], None
    allowed = set(names)
    with open(path) as handle:
        for line in handle:
            f = line.rstrip("\n").split("\t")
            if len(f) != 5+len(names):
                raise ValueError("Unexpected multiinter columns")
            c, a, b, n = f[0], int(f[1]), int(f[2]), int(f[3])
            ids = set(f[4].split(","))
            bits = f[5:]
            if a < 0 or b <= a or not ids <= allowed or len(ids) != n or any(x not in {"0", "1"} for x in bits):
                raise ValueError("Invalid atomic interval/support")
            if {name for name, bit in zip(names, bits) if bit == "1"} != ids:
                raise ValueError("Support identities disagree with bit matrix")
            if last and (c < last[0] or (c == last[0] and a < last[2])):
                raise ValueError("Unsorted or overlapping atomic intervals")
            atoms.append((c, a, b, tuple(sorted(ids))))
            last = (c, a, b)
    return atoms


def consolidate(atoms, names, threshold, identifier):
    """Join only touching atoms. No positive gap is filled and no base invented."""
    components, current = [], []
    for atom in atoms:
        if current and (atom[0] != current[-1][0] or atom[1] != current[-1][2]):
            components.append(current)
            current = []
        current.append(atom)
    if current:
        components.append(current)
    catalog, support, core = [], [], []
    for i, component in enumerate(components, 1):
        c, a, b = component[0][0], component[0][1], component[-1][2]
        peak_id = f"{identifier}.regional_catalog.{i:06d}"
        coverage = Counter()
        core_bp = 0
        for chrom, start, end, ids in component:
            for unit in ids:
                coverage[unit] += end-start
            if len(ids) >= threshold:
                core_bp += end-start
                core.append((chrom, start, end, f"{peak_id}.core.{len(core)+1:06d}"))
        units = sorted(coverage)
        catalog.append({"peak_id": peak_id, "chrom": c, "start": a, "end": b,
                        "support": len(units), "support_replicates": ",".join(units),
                        "core_bp": core_bp, "core_fraction": core_bp/(b-a),
                        "below_threshold_bp": b-a-core_bp,
                        "classification": "spatially_supported_candidate" if core_bp else "candidate",
                        "occupancy_status": "not_assessed"})
        for unit in names:
            support.append({"peak_id": peak_id, "replicate_id": unit,
                            "called_bp": coverage[unit], "called_fraction": coverage[unit]/(b-a),
                            "has_call": str(coverage[unit] > 0).lower()})
    return catalog, support, core


def run(request, peak_dirs, output, reports, cpus, memory, task_time, nf_version, environment):
    started = time.time()
    directories = {Path(p).name: Path(p) for p in peak_dirs}
    if len(directories) != len(peak_dirs):
        raise ValueError("Duplicate staged basenames")
    names, threshold = validate_request(request, directories)
    if output.exists() or reports.exists():
        raise ValueError("Refusing to overwrite existing regional outputs")
    output.mkdir(parents=True)
    reports.mkdir(parents=True)
    commands, inputs, merged, evidence = [], [], [], []
    total = 0
    for i, rep in enumerate(request["replicates"]):
        path = directories[rep["peak_directory"]]/rep["peak_file"]
        actual = sha(path)
        if rep.get("peak_sha256") != actual:
            raise ValueError("Source peak checksum mismatch")
        inputs.append({"replicate_id": names[i], "peak_id": rep["peak_id"], "sha256": actual})
        count = 0
        with path.open() as handle:
            for line in handle:
                if not line.strip():
                    continue
                f = line.rstrip("\n").split("\t")
                if len(f) != 9 or int(f[1]) < 0 or int(f[2]) <= int(f[1]):
                    raise ValueError("Invalid broadPeak source")
                evidence.append({"replicate_id": names[i], "peak_id": rep["peak_id"], "original_peak_name": f[3],
                                 "chrom": f[0], "start": f[1], "end": f[2], "score": f[4], "strand": f[5],
                                 "signal_value": f[6], "p_value": f[7], "q_value": f[8], "summit": ""})
                count += 1
        if count != rep["peak_count"]:
            raise ValueError("Source peak count mismatch")
        total += count
        sorted_path, merged_path = reports/f"unit_{i}.sorted.bed", reports/f"unit_{i}.merged.bed"
        for command, dest in ((["bedtools", "sort", "-i", str(path)], sorted_path),
                              (["bedtools", "merge", "-i", str(sorted_path)], merged_path)):
            with dest.open("w") as handle:
                subprocess.run(command, stdout=handle, check=True)
            commands.append(command)
        merged.append(str(merged_path))
    atomic = reports/"multiinter.atomic.tsv"
    if total:
        command = ["bedtools", "multiinter", "-i", *merged, "-names", *names]
        with atomic.open("w") as handle:
            subprocess.run(command, stdout=handle, check=True)
        commands.append(command)
    else:
        atomic.touch()
    atoms = read_atoms(atomic, names)
    catalog, support, cores = consolidate(atoms, names, threshold, request["id"])
    fields = ["peak_id", "chrom", "start", "end", "support", "support_replicates", "core_bp", "core_fraction", "below_threshold_bp", "classification", "occupancy_status"]
    write_table(output/"consolidated_peaks.tsv", fields, catalog)
    write_table(output/"regional_support.tsv", ["peak_id", "replicate_id", "called_bp", "called_fraction", "has_call"], support)
    write_table(output/"replicate_evidence.tsv", ["replicate_id", "peak_id", "original_peak_name", "chrom", "start", "end", "score", "strand", "signal_value", "p_value", "q_value", "summit"], evidence)
    for name, rows in (("consolidated_peaks.bed", catalog), ("supported_regions.bed", [r for r in catalog if r["core_bp"]])):
        (output/name).write_text("".join(f"{r['chrom']}\t{r['start']}\t{r['end']}\t{r['peak_id']}\n" for r in rows))
    (output/"core_supported.bed").write_text("".join(f"{c}\t{a}\t{b}\t{i}\n" for c, a, b, i in cores))
    status = "complete" if catalog else "complete_empty"
    stats = {"status": status, "consolidated_peaks": len(catalog), "replicate_count": len(names),
             "support_threshold": threshold, "candidate_bp": sum(r["end"]-r["start"] for r in catalog),
             "core_bp": sum(b-a for c, a, b, i in cores), "spatially_supported_regions": sum(r["core_bp"] > 0 for r in catalog),
             "reproducible_occupancy_assessed": False}
    (output/"statistics.json").write_text(json.dumps(stats, indent=2)+"\n")
    execution = {"process": "REGIONAL_CATALOG", "commands": commands, "cpus": cpus, "memory_bytes": memory,
                 "time": task_time, "nextflow_version": nf_version, "environment": environment,
                 "elapsed_seconds": time.time()-started}
    artifacts = {key: {"available": True, "path": path, "sha256": sha(output/path)} for key, path in {
        "consolidated_peaks": "consolidated_peaks.tsv", "consolidated_bed": "consolidated_peaks.bed",
        "spatially_supported_bed": "supported_regions.bed", "core_supported_bed": "core_supported.bed",
        "regional_support": "regional_support.tsv", "replicate_evidence": "replicate_evidence.tsv"}.items()}
    manifest = {**{k: request[k] for k in ("id", "strategy", "provider", "provider_version", "dataset", "experiment_id", "condition", "target", "genome_id", "peak_type", "caller", "caller_version", "replicate_mode", "replicate_policy", "replicates", "parameters")},
                "schema_version": "1.0", "type": "consensus", "status": status,
                "statistics": stats, "artifacts": artifacts, "source_peaks": inputs, "execution": execution,
                "semantics": {"consolidated_bed": "candidate_envelopes_not_confirmed_occupancy",
                              "spatial_support": "core with >=k distinct evidence units; tails may have less support",
                              "reproducible_occupancy": "not_assessed", "quantitative_enrichment": "not_assessed",
                              "fdr_of_catalog": "not_estimated", "positive_gap_filling_bp": 0}}
    (output/"manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    (reports/"commands.json").write_text(json.dumps(commands, indent=2)+"\n")
    return manifest, execution


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--request", required=True)
    p.add_argument("--peak-dir", action="append", required=True)
    for name in ("output-dir", "reports", "manifest", "execution", "versions", "task-time", "nextflow-version", "environment"):
        p.add_argument("--"+name, required=True)
    p.add_argument("--cpus", type=int, required=True)
    p.add_argument("--memory-bytes", type=int, required=True)
    a = p.parse_args()
    try:
        request = json.loads(Path(a.request).read_text())
        manifest, execution = run(request, a.peak_dir, Path(a.output_dir), Path(a.reports), a.cpus, a.memory_bytes, a.task_time, a.nextflow_version, a.environment)
        Path(a.manifest).write_text(json.dumps(manifest, indent=2)+"\n")
        Path(a.execution).write_text(json.dumps(execution, indent=2)+"\n")
        version = subprocess.check_output(["bedtools", "--version"], text=True).strip()
        Path(a.versions).write_text(f'"REGIONAL_CATALOG":\n    provider: "{VERSION}"\n    bedtools: "{version}"\n    python: "{sys.version.split()[0]}"\n')
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
