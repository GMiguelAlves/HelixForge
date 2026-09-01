#!/usr/bin/env python3
"""Validate the frozen GSE133183 sample selection against official metadata."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
from typing import Any


GIB = 1024 ** 3
EXPECTED_GSMS = {f"GSM{number}" for number in range(4817452, 4817468)}


def read_rows(path: Path, delimiter: str) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_geo_soft(path: Path) -> dict[str, dict[str, Any]]:
    samples: dict[str, dict[str, Any]] = {}
    accession: str | None = None
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            line = raw.rstrip("\n")
            if line.startswith("^SAMPLE = "):
                accession = line.split(" = ", 1)[1]
                samples[accession] = {"characteristics": []}
            elif accession and line.startswith("!Sample_title = "):
                samples[accession]["title"] = line.split(" = ", 1)[1]
            elif accession and line.startswith("!Sample_library_strategy = "):
                samples[accession]["library_strategy"] = line.split(" = ", 1)[1]
            elif accession and line.startswith("!Sample_relation = SRA: "):
                samples[accession]["sra_relation"] = line.split("SRA: ", 1)[1]
            elif accession and line.startswith("!Sample_characteristics_ch1 = "):
                samples[accession]["characteristics"].append(line.split(" = ", 1)[1])
    return samples


def split_ena_files(row: dict[str, str]) -> list[dict[str, Any]]:
    urls = [value for value in row["fastq_ftp"].split(";") if value]
    md5s = [value for value in row["fastq_md5"].split(";") if value]
    sizes = [value for value in row["fastq_bytes"].split(";") if value]
    if not urls or not (len(urls) == len(md5s) == len(sizes)):
        raise ValueError(f"{row['run_accession']}: inconsistent ENA FASTQ fields")
    files: list[dict[str, Any]] = []
    for index, (url, md5, size) in enumerate(zip(urls, md5s, sizes), start=1):
        mate = "0"
        if url.endswith("_1.fastq.gz"):
            mate = "1"
        elif url.endswith("_2.fastq.gz"):
            mate = "2"
        files.append({
            "mate": mate,
            "url": url if url.startswith("http") else f"https://{url}",
            "md5": md5,
            "bytes": int(size),
            "file_index": index,
        })
    if row["library_layout"].upper() == "PAIRED" and {item["mate"] for item in files} != {"1", "2"}:
        raise ValueError(f"{row['run_accession']}: paired layout lacks exactly two mate FASTQs")
    return files


def normalized_strategy(value: str) -> str:
    return value.lower().replace("-", "").replace("_", "")


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write an empty table: {path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection", required=True, type=Path)
    parser.add_argument("--ena-dir", required=True, type=Path)
    parser.add_argument("--runinfo", required=True, type=Path)
    parser.add_argument("--geo-soft", required=True, type=Path)
    parser.add_argument("--reference-sources", required=True, type=Path)
    parser.add_argument("--scratch-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if not os.environ.get("SLURM_JOB_ID"):
        raise SystemExit("metadata validation must execute inside a Slurm job")
    if args.output_dir.exists():
        raise FileExistsError(args.output_dir)
    args.output_dir.mkdir(parents=True)

    selection_rows = read_rows(args.selection, "\t")
    selection = {row["geo_sample"]: row for row in selection_rows}
    if len(selection_rows) != 16 or set(selection) != EXPECTED_GSMS:
        raise ValueError("selection is not the frozen 16-GSM GSE133183 design")
    assay_counts = {
        "RNA-seq": sum(row["assay"] == "RNA-seq" for row in selection_rows),
        "H3K27me3": sum(row["mark"] == "H3K27me3" for row in selection_rows),
        "H3K27ac": sum(row["mark"] == "H3K27ac" for row in selection_rows),
        "IgG": sum(row["mark"] == "IgG" for row in selection_rows),
    }
    if assay_counts != {"RNA-seq": 4, "H3K27me3": 4, "H3K27ac": 4, "IgG": 4}:
        raise ValueError(f"unexpected assay balance: {assay_counts}")

    geo = parse_geo_soft(args.geo_soft)
    runinfo_rows = read_rows(args.runinfo, ",")
    runinfo_by_run = {row["Run"]: row for row in runinfo_rows}
    metadata: list[dict[str, Any]] = []
    downloads: list[dict[str, Any]] = []
    selected_runs: set[str] = set()
    for gsm in sorted(selection):
        expected = selection[gsm]
        ena_path = args.ena_dir / f"{gsm}.tsv"
        ena_rows = read_rows(ena_path, "\t")
        if not ena_rows:
            raise ValueError(f"DATASET_AVAILABILITY_CONFLICT: ENA returned no run for {gsm}")
        if gsm not in geo:
            raise ValueError(f"DATASET_AVAILABILITY_CONFLICT: GEO SOFT lacks {gsm}")
        geo_row = geo[gsm]
        if normalized_strategy(geo_row.get("library_strategy", "")) != normalized_strategy(expected["expected_library_strategy"]):
            raise ValueError(f"DATASET_AVAILABILITY_CONFLICT: GEO strategy mismatch for {gsm}")
        title = str(geo_row.get("title", ""))
        required_title_tokens = [expected["condition"], f"rep{expected['biological_replicate']}"]
        if expected["mark"] != "NOT_APPLICABLE":
            required_title_tokens.append(expected["mark"])
        if any(token.lower() not in title.lower() for token in required_title_tokens):
            raise ValueError(f"DATASET_AVAILABILITY_CONFLICT: GEO title mismatch for {gsm}: {title}")

        for ena in ena_rows:
            run = ena["run_accession"]
            if run in selected_runs:
                raise ValueError(f"duplicate selected ENA run: {run}")
            selected_runs.add(run)
            if ena["sample_alias"] != gsm:
                raise ValueError(f"DATASET_AVAILABILITY_CONFLICT: ENA alias mismatch for {gsm}")
            if normalized_strategy(ena["library_strategy"]) != normalized_strategy(expected["expected_library_strategy"]):
                raise ValueError(f"DATASET_AVAILABILITY_CONFLICT: ENA strategy mismatch for {gsm}")
            if ena["library_layout"].upper() not in {"PAIRED", "SINGLE"}:
                raise ValueError(f"unsupported library layout for {run}")
            if ena["instrument_platform"].upper() != "ILLUMINA":
                raise ValueError(f"unexpected platform for {run}: {ena['instrument_platform']}")
            ncbi = runinfo_by_run.get(run)
            if ncbi is None:
                raise ValueError(f"DATASET_AVAILABILITY_CONFLICT: NCBI RunInfo lacks {run}")
            if ncbi.get("SampleName") != gsm or ncbi.get("BioSample") != ena["sample_accession"]:
                raise ValueError(f"DATASET_AVAILABILITY_CONFLICT: ENA/NCBI sample mismatch for {run}")
            if normalized_strategy(ncbi.get("LibraryStrategy", "")) != normalized_strategy(expected["expected_library_strategy"]):
                raise ValueError(f"DATASET_AVAILABILITY_CONFLICT: NCBI strategy mismatch for {run}")

            files = split_ena_files(ena)
            read_count = int(ena["read_count"])
            base_count = int(ena["base_count"])
            layout_divisor = 2 if ena["library_layout"].upper() == "PAIRED" else 1
            read_length = base_count / read_count / layout_divisor if read_count else 0.0
            metadata.append({
                "geo_sample": gsm,
                "run_accession": run,
                "biosample": ena["sample_accession"],
                "experiment_accession": ena["experiment_accession"],
                "assay": expected["assay"],
                "mark": expected["mark"],
                "condition": expected["condition"],
                "biological_replicate": expected["biological_replicate"],
                "control_geo_sample": expected["control_geo_sample"],
                "library_strategy": ena["library_strategy"],
                "library_source": ena["library_source"],
                "library_selection": ena["library_selection"],
                "library_layout": ena["library_layout"],
                "instrument_platform": ena["instrument_platform"],
                "instrument_model": ena["instrument_model"],
                "read_count": read_count,
                "base_count": base_count,
                "estimated_read_length": f"{read_length:.3f}",
                "fastq_file_count": len(files),
                "fastq_bytes": sum(item["bytes"] for item in files),
                "first_public": ena["first_public"],
                "last_updated": ena["last_updated"],
                "geo_title": title,
            })
            for item in files:
                downloads.append({
                    "geo_sample": gsm,
                    "run_accession": run,
                    "assay": expected["assay"],
                    "mark": expected["mark"],
                    "condition": expected["condition"],
                    "biological_replicate": expected["biological_replicate"],
                    "mate": item["mate"],
                    "url": item["url"],
                    "md5": item["md5"],
                    "bytes": item["bytes"],
                })

    write_tsv(args.output_dir / "dataset_metadata.tsv", metadata)
    write_tsv(args.output_dir / "download_manifest.tsv", downloads)
    total_fastq_bytes = sum(int(row["bytes"]) for row in downloads)
    total_bases = sum(int(row["base_count"]) for row in metadata)
    uncompressed_fastq = math.ceil(total_bases * 2.5)
    reference_reserve = 100 * GIB
    results_reserve = 50 * GIB
    work_reserve = math.ceil(uncompressed_fastq * 2.0 + total_fastq_bytes * 2.0)
    required = math.ceil((total_fastq_bytes + uncompressed_fastq + reference_reserve + results_reserve + work_reserve) * 1.25)
    disk = shutil.disk_usage(args.scratch_root)
    plan = {
        "schema_version": "1.0",
        "status": "SPACE_AVAILABLE" if disk.free >= required else "RESOURCE_BLOCKED",
        "selected_samples": len(selection),
        "selected_runs": len(metadata),
        "selected_fastq_files": len(downloads),
        "paired_fastq_download_bytes": total_fastq_bytes,
        "paired_fastq_download_gib": total_fastq_bytes / GIB,
        "total_deposited_bases": total_bases,
        "uncompressed_fastq_planning_bytes": uncompressed_fastq,
        "uncompressed_fastq_planning_gib": uncompressed_fastq / GIB,
        "reference_and_index_reserve_bytes": reference_reserve,
        "workflow_work_reserve_bytes": work_reserve,
        "results_reserve_bytes": results_reserve,
        "safety_margin_fraction": 0.25,
        "required_scratch_bytes": required,
        "required_scratch_gib": required / GIB,
        "available_scratch_bytes": disk.free,
        "available_scratch_gib": disk.free / GIB,
        "planning_formula": "1.25 * (compressed FASTQ + 2.5 bytes/base FASTQ estimate + 100 GiB references + 50 GiB results + 2x FASTQ estimate + 2x compressed work reserve)",
        "download_strategy": "official ENA FASTQ with resume and official MD5 validation; no SRA conversion",
    }
    (args.output_dir / "storage_plan.json").write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    references = read_rows(args.reference_sources, "\t")
    if any(not row["frozen_md5"] or "VERIFY" in row["frozen_md5"] for row in references):
        raise ValueError("reference inventory contains an unresolved checksum")
    validation = {
        "schema_version": "1.0",
        "status": "METADATA_VALIDATED" if plan["status"] == "SPACE_AVAILABLE" else "RESOURCE_BLOCKED",
        "slurm_job_id": os.environ["SLURM_JOB_ID"],
        "geo_series": "GSE133183",
        "sra_study": "SRP211748",
        "bioproject": "PRJNA550207",
        "selected_gsms": sorted(selection),
        "selected_runs": sorted(selected_runs),
        "assay_counts": assay_counts,
        "conditions": {condition: sum(row["condition"] == condition for row in selection_rows) for condition in ("DMSO", "GSK343")},
        "official_sources": ["GEO family SOFT", "ENA Portal API", "NCBI RunInfo"],
        "scientific_results_inspected": False,
    }
    (args.output_dir / "metadata_validation.json").write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    source_paths = [args.selection, args.runinfo, args.geo_soft, args.reference_sources, *sorted(args.ena_dir.glob("*.tsv"))]
    with (args.output_dir / "source_checksums.sha256").open("w", encoding="utf-8") as handle:
        for path in source_paths:
            handle.write(f"{sha256(path)}  {path}\n")
    print(json.dumps({
        "status": validation["status"],
        "samples": len(selection),
        "runs": len(metadata),
        "download_gib": round(total_fastq_bytes / GIB, 3),
        "required_scratch_gib": round(required / GIB, 3),
        "available_scratch_gib": round(disk.free / GIB, 3),
    }, sort_keys=True))
    return 0 if plan["status"] == "SPACE_AVAILABLE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
