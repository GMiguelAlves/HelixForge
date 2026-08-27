#!/usr/bin/env python3
"""Validate the frozen GSE52778 selection against official ENA/NCBI/GEO metadata."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import xml.etree.ElementTree as ET


EXPECTED_RUNS = {
    "SRR1039508", "SRR1039509", "SRR1039512", "SRR1039513",
    "SRR1039516", "SRR1039517", "SRR1039520", "SRR1039521",
}
GIB = 1024 ** 3


def read_rows(path: Path, delimiter: str) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def indexed(rows: list[dict[str, str]], key: str, label: str) -> dict[str, dict[str, str]]:
    result = {row[key]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError(f"duplicate {label} identifiers")
    return result


def parse_geo_soft(path: Path) -> dict[str, str]:
    titles: dict[str, str] = {}
    accession: str | None = None
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            line = raw.rstrip("\n")
            if line.startswith("^SAMPLE = "):
                accession = line.split(" = ", 1)[1]
            elif accession and line.startswith("!Sample_title = "):
                titles[accession] = line.split(" = ", 1)[1]
    return titles


def parse_read_descriptor(path: Path) -> tuple[int, int, int]:
    root = ET.parse(path).getroot()
    spot_length = int(root.findtext(".//SPOT_LENGTH", default="0"))
    coordinates = [int(value.text) for value in root.findall(".//READ_SPEC/BASE_COORD")]
    if spot_length <= 0 or len(coordinates) != 2 or coordinates != sorted(coordinates):
        raise ValueError(f"unsupported read descriptor: {path}")
    r1_length = coordinates[1] - coordinates[0]
    r2_length = spot_length - coordinates[1] + 1
    return spot_length, r1_length, r2_length


def paired_ena_files(row: dict[str, str]) -> tuple[dict[str, dict[str, object]], int]:
    urls = row["fastq_ftp"].split(";")
    md5s = row["fastq_md5"].split(";")
    sizes = row["fastq_bytes"].split(";")
    if not (len(urls) == len(md5s) == len(sizes)):
        raise ValueError(f"inconsistent ENA FASTQ fields for {row['run_accession']}")
    files = [{"url": f"https://{url}", "md5": md5, "bytes": int(size)}
             for url, md5, size in zip(urls, md5s, sizes)]
    selected: dict[str, dict[str, object]] = {}
    for mate in ("1", "2"):
        matches = [item for item in files if str(item["url"]).endswith(f"_{mate}.fastq.gz")]
        if len(matches) != 1:
            raise ValueError(f"expected one mate {mate} for {row['run_accession']}")
        selected[mate] = matches[0]
    return selected, len(files) - 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--ena", required=True, type=Path)
    parser.add_argument("--runinfo", required=True, type=Path)
    parser.add_argument("--geo-soft", required=True, type=Path)
    parser.add_argument("--xml-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if not os.environ.get("SLURM_JOB_ID"):
        raise SystemExit("metadata validation must execute inside a Slurm job")
    if args.output_dir.exists():
        raise FileExistsError(args.output_dir)
    args.output_dir.mkdir(parents=True)

    registry = read_rows(args.registry, "\t")
    if len(registry) != 8 or {row["run_accession"] for row in registry} != EXPECTED_RUNS:
        raise ValueError("registry does not contain the frozen eight-run selection")
    if len({row["sample_id"] for row in registry}) != 8:
        raise ValueError("sample IDs must be unique")
    donors = {row["donor"] for row in registry}
    if len(donors) != 4:
        raise ValueError("expected four donors")
    for donor in donors:
        conditions = {row["condition"] for row in registry if row["donor"] == donor}
        if conditions != {"untreated", "dexamethasone"}:
            raise ValueError(f"donor {donor} is not paired across the two conditions")

    ena = indexed(read_rows(args.ena, "\t"), "run_accession", "ENA run")
    runinfo = indexed(read_rows(args.runinfo, ","), "Run", "NCBI run")
    geo_titles = parse_geo_soft(args.geo_soft)
    metadata: list[dict[str, object]] = []
    warnings: list[str] = []
    for expected in registry:
        run = expected["run_accession"]
        if run not in ena or run not in runinfo:
            raise ValueError(f"official metadata is missing {run}")
        ena_row, ncbi = ena[run], runinfo[run]
        checks = {
            "biosample": ena_row["sample_accession"] == expected["biosample"] == ncbi["BioSample"],
            "geo_sample": ena_row["sample_alias"] == expected["geo_sample"] == ncbi["SampleName"],
            "layout": ena_row["library_layout"] == expected["library_layout"] == ncbi["LibraryLayout"] == "PAIRED",
            "platform": ena_row["instrument_platform"] == ncbi["Platform"] == "ILLUMINA",
            "model": ena_row["instrument_model"] == ncbi["Model"] == "Illumina HiSeq 2000",
            "experiment": ena_row["experiment_accession"] == ncbi["Experiment"],
            "spots": int(ena_row["read_count"]) == int(ncbi["spots"]),
            "bases": int(ena_row["base_count"]) == int(ncbi["bases"]),
        }
        failed = [name for name, passed in checks.items() if not passed]
        if failed:
            raise ValueError(f"{run}: official/registry mismatch in {failed}")
        paired, extra_files = paired_ena_files(ena_row)
        for mate, registry_prefix in (("1", "fastq_1"), ("2", "fastq_2")):
            if paired[mate]["url"] != expected[f"{registry_prefix}_url"]:
                raise ValueError(f"{run}: mate {mate} URL differs from registry")
            if paired[mate]["md5"] != expected[f"{registry_prefix}_md5"]:
                raise ValueError(f"{run}: mate {mate} MD5 differs from registry")
            if paired[mate]["bytes"] != int(expected[f"{registry_prefix}_bytes"]):
                raise ValueError(f"{run}: mate {mate} size differs from registry")
        expected_title = f"{expected['donor']}_{'Dex' if expected['condition'] == 'dexamethasone' else 'untreated'}"
        if geo_titles.get(expected["geo_sample"]) != expected_title:
            raise ValueError(f"{run}: GEO title does not confirm donor/condition")
        spot_length, read1_length, read2_length = parse_read_descriptor(args.xml_dir / f"{run}.xml")
        if (read1_length, read2_length) != (63, 63):
            raise ValueError(f"{run}: unexpected deposited paired read lengths")
        if int(ncbi["spots_with_mates"]) == int(ncbi["spots"]) and spot_length != int(ncbi["avgLength"]):
            raise ValueError(f"{run}: ENA spot length differs from NCBI avgLength")
        metadata.append({
            "run_accession": run,
            "geo_sample": expected["geo_sample"],
            "biosample": expected["biosample"],
            "donor": expected["donor"],
            "condition": expected["condition"],
            "library_layout": "PAIRED",
            "read_length_r1": read1_length,
            "read_length_r2": read2_length,
            "ncbi_average_spot_length": int(ncbi["avgLength"]),
            "instrument_platform": ena_row["instrument_platform"],
            "instrument_model": ena_row["instrument_model"],
            "run_spots": int(ncbi["spots"]),
            "paired_spots": int(ncbi["spots_with_mates"]),
            "base_count": int(ncbi["bases"]),
            "sra_size_mb": int(ncbi["size_MB"]),
            "fastq_1_bytes": paired["1"]["bytes"],
            "fastq_2_bytes": paired["2"]["bytes"],
            "paired_fastq_bytes": int(paired["1"]["bytes"]) + int(paired["2"]["bytes"]),
            "extra_unpaired_ena_files_excluded": extra_files,
            "fastq_1_url": paired["1"]["url"],
            "fastq_2_url": paired["2"]["url"],
            "fastq_1_md5": paired["1"]["md5"],
            "fastq_2_md5": paired["2"]["md5"],
        })

    warnings.append(
        "GEO describes 75 bp library sequencing, while the deposited ENA/SRA spot descriptor "
        "contains two 63 bp application reads (spot length 126); the benchmark uses deposited reads."
    )
    fields = list(metadata[0])
    metadata_path = args.output_dir / "gse52778_run_metadata.tsv"
    with metadata_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(metadata)

    paired_bytes = sum(int(row["paired_fastq_bytes"]) for row in metadata)
    sra_size_bytes = sum(int(row["sra_size_mb"]) for row in metadata) * 1024 ** 2
    paired_bases = sum(int(row["paired_spots"]) *
                       (int(row["read_length_r1"]) + int(row["read_length_r2"]))
                       for row in metadata)
    fastq_floor = paired_bases * 2
    fastq_planning = math.ceil(paired_bases * 2.5)
    reference_reserve = 60 * GIB
    work_reserve = 250 * GIB
    results_reserve = 20 * GIB
    subtotal = paired_bytes + reference_reserve + work_reserve + results_reserve
    required = math.ceil(subtotal * 1.25)
    plan = {
        "schema_version": "1.0",
        "status": "METADATA_VALIDATED",
        "strategy": "official ENA paired FASTQ, resumable curl, no SRA conversion",
        "runs": 8,
        "sra_download_alternative_bytes": sra_size_bytes,
        "paired_fastq_download_bytes": paired_bytes,
        "paired_fastq_download_gib": paired_bytes / GIB,
        "paired_spots": sum(int(row["paired_spots"]) for row in metadata),
        "uncompressed_fastq_sequence_quality_floor_bytes": fastq_floor,
        "uncompressed_fastq_planning_bytes": fastq_planning,
        "temporary_uncompressed_fastq_bytes_chosen_strategy": 0,
        "reference_and_salmon_index_reserve_bytes": reference_reserve,
        "nextflow_work_reserve_bytes": work_reserve,
        "results_reserve_bytes": results_reserve,
        "safety_margin_fraction": 0.25,
        "required_scratch_bytes": required,
        "required_scratch_gib": required / GIB,
        "warnings": warnings,
    }
    (args.output_dir / "gse52778_download_plan.json").write_text(
        json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    markdown = f"""# GSE52778 full-data download plan

- Runs: 8
- NCBI SRA/SRA-Lite alternative: {sra_size_bytes / GIB:.2f} GiB
- Selected official ENA paired FASTQ transfer: {paired_bytes / GIB:.2f} GiB
- Paired spots retained: {plan['paired_spots']:,}
- FASTQ uncompressed sequence+quality lower bound: {fastq_floor / GIB:.2f} GiB
- Conservative uncompressed FASTQ planning estimate: {fastq_planning / GIB:.2f} GiB
- Temporary uncompressed FASTQ for chosen strategy: 0 GiB
- Reference and Salmon index reserve: 60 GiB
- Nextflow work reserve: 250 GiB
- Results reserve: 20 GiB
- Safety margin: 25%
- Required scratch planning envelope: {required / GIB:.2f} GiB

The selected strategy downloads the exact paired ENA exports already frozen in
`airway_samples.tsv`. Additional orphan/unpaired exports are excluded. Transfer
uses resumable partial files, official MD5 validation, local SHA-256 and paired
FASTQ structural validation. SRA conversion is not used, avoiding the
simultaneous SRA and uncompressed FASTQ footprint.

## Metadata warning

GEO describes 75 bp sequencing, while the deposited ENA/SRA descriptors contain
two 63 bp application reads (126 bp per paired spot). The frozen accessions,
GSMs, donors, conditions, layout, platform, file sizes and MD5 values all match.
The benchmark evaluates the deposited paired FASTQs and records this distinction.
"""
    (args.output_dir / "gse52778_download_plan.md").write_text(markdown, encoding="utf-8")

    sources = [args.registry, args.ena, args.runinfo, args.geo_soft]
    sources.extend(sorted(args.xml_dir.glob("*.xml")))
    with (args.output_dir / "source_checksums.sha256").open("w", encoding="utf-8") as handle:
        for path in sources:
            handle.write(f"{sha256(path)}  {path}\n")
    validation = {
        "schema_version": "1.0",
        "status": "METADATA_VALIDATED",
        "slurm_job_id": os.environ["SLURM_JOB_ID"],
        "selected_runs": sorted(EXPECTED_RUNS),
        "samples": 8,
        "donors": 4,
        "conditions": {"untreated": 4, "dexamethasone": 4},
        "official_sources": ["ENA Portal API", "ENA Browser XML", "NCBI RunInfo", "GEO SOFT"],
        "warnings": warnings,
    }
    (args.output_dir / "metadata_validation.json").write_text(
        json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": "METADATA_VALIDATED", "runs": 8,
                      "download_gib": round(paired_bytes / GIB, 3),
                      "required_scratch_gib": round(required / GIB, 3)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
