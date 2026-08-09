#!/usr/bin/env python3
import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict


TRUE_VALUES = {"true", "1", "yes", "y"}
FALSE_VALUES = {"false", "0", "no", "n"}
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def clean(value):
    return (value or "").strip()


def parse_bool(value, field, record):
    normalized = clean(value).lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ValueError(f"record {record}: {field} must be a boolean, got {value!r}")


def read_settings(path):
    with open(path, encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return {clean(row.get("key")): clean(row.get("value")) for row in reader}


def resolve_file(value, base, label, record, required=True):
    value = clean(value)
    if not value:
        if required:
            raise ValueError(f"record {record}: missing {label}")
        return ""
    path = value if os.path.isabs(value) else os.path.join(base, value)
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise ValueError(f"record {record}: {label} does not exist: {path}")
    return path


def load_rows(metadata, settings):
    fastq_dir = settings.get("FASTQ_DIR") or os.path.dirname(os.path.abspath(metadata))
    layout_override = clean(settings.get("READ_LAYOUT", "metadata")).lower()
    if layout_override not in {"metadata", "single", "paired"}:
        raise ValueError(f"READ_LAYOUT must be metadata, single, or paired: {layout_override}")

    with open(metadata, encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if not reader.fieldnames:
            raise ValueError("metadata has no header")
        required = {"sample_id", "fastq_1", "layout", "condition", "is_control", "genome_id"}
        missing = sorted(required - set(reader.fieldnames))
        if missing:
            raise ValueError("metadata missing required column(s): " + ", ".join(missing))
        source_rows = list(reader)

    if not source_rows:
        raise ValueError("metadata contains no records")

    normalized = []
    ids = set()
    for row_number, source in enumerate(source_rows, start=2):
        sample_id = clean(source.get("sample_id"))
        if not sample_id:
            raise ValueError(f"row {row_number}: sample_id is empty")
        run_accession = clean(source.get("run_accession"))
        lane = clean(source.get("lane"))
        technical = clean(source.get("technical_replicate")) or "1"
        record_id = run_accession or (f"{sample_id}.lane_{lane}" if lane else sample_id)
        if not SAFE_ID.fullmatch(record_id):
            raise ValueError(f"record {record_id!r}: id must contain only letters, numbers, '.', '_' or '-'")
        if record_id in ids:
            raise ValueError(f"duplicate execution record id: {record_id}")
        ids.add(record_id)

        layout = layout_override if layout_override != "metadata" else clean(source.get("layout")).lower()
        if layout not in {"single", "paired"}:
            raise ValueError(f"record {record_id}: layout must be single or paired")
        fastq_1 = resolve_file(source.get("fastq_1"), fastq_dir, "fastq_1", record_id)
        fastq_2 = resolve_file(source.get("fastq_2"), fastq_dir, "fastq_2", record_id, layout == "paired")
        if layout == "single" and fastq_2:
            raise ValueError(f"record {record_id}: single-end record must not define fastq_2")
        if fastq_2 and fastq_1 == fastq_2:
            raise ValueError(f"record {record_id}: fastq_1 and fastq_2 resolve to the same file")

        is_control = parse_bool(source.get("is_control"), "is_control", record_id)
        target = clean(source.get("target")) or clean(source.get("mark_or_factor"))
        if not is_control and not target:
            raise ValueError(f"record {record_id}: IP record requires target or mark_or_factor")
        biological = clean(source.get("biological_replicate")) or clean(source.get("replicate"))
        if not biological:
            raise ValueError(f"record {record_id}: biological_replicate or replicate is required")

        normalized.append({
            "record_id": record_id,
            "sample_id": sample_id,
            "run_accession": run_accession,
            "lane": lane,
            "dataset": clean(source.get("dataset")) or "default",
            "condition": clean(source.get("condition")),
            "biological_replicate": biological,
            "technical_replicate": technical,
            "layout": layout,
            "single_end": str(layout == "single").lower(),
            "assay": clean(source.get("assay")),
            "is_control": str(is_control).lower(),
            "control_id": clean(source.get("control_id")) or clean(source.get("control")),
            "target": target,
            "antibody": clean(source.get("antibody")),
            "batch": clean(source.get("batch")),
            "treatment": clean(source.get("treatment")),
            "genome_id": clean(source.get("genome_id")),
            "organism": clean(source.get("organism")) or clean(settings.get("ORGANISM_NAME")),
            "fastq_1": fastq_1,
            "fastq_2": fastq_2,
        })
    return normalized


def validate_relationships(rows, allow_missing_controls):
    by_sample = defaultdict(list)
    for row in rows:
        by_sample[row["sample_id"]].append(row)

    identity_fields = (
        "dataset", "condition", "biological_replicate", "is_control",
        "control_id", "target", "antibody", "genome_id", "organism",
    )
    for sample_id, records in by_sample.items():
        if len(records) == 1:
            continue
        if any(not record["run_accession"] and not record["lane"] for record in records):
            raise ValueError(
                f"duplicate sample_id {sample_id}: repeated samples require a unique run_accession or lane"
            )
        first = records[0]
        for record in records[1:]:
            incompatible = [field for field in identity_fields if record[field] != first[field]]
            if incompatible:
                raise ValueError(
                    f"sample {sample_id}: technical records disagree on {', '.join(incompatible)}"
                )
        technical_keys = {(r["run_accession"], r["lane"], r["technical_replicate"]) for r in records}
        if len(technical_keys) != len(records):
            raise ValueError(f"sample {sample_id}: duplicate technical replicate identity")

    controls = []
    for row in rows:
        is_control = row["is_control"] == "true"
        if is_control:
            if row["control_id"]:
                raise ValueError(f"control record {row['record_id']} must not reference control_id")
            continue
        control_id = row["control_id"]
        if not control_id:
            if allow_missing_controls:
                continue
            raise ValueError(f"IP record {row['record_id']} has no control_id")
        matches = by_sample.get(control_id, [])
        if not matches:
            raise ValueError(f"IP record {row['record_id']} references missing control {control_id}")
        if any(match["is_control"] != "true" for match in matches):
            raise ValueError(f"IP record {row['record_id']} references non-control sample {control_id}")
        for control in matches:
            for field in ("dataset", "genome_id", "organism"):
                if row[field] and control[field] and row[field] != control[field]:
                    raise ValueError(
                        f"IP record {row['record_id']} and control {control_id} disagree on {field}"
                    )
        controls.append({"record_id": row["record_id"], "sample_id": row["sample_id"], "control_id": control_id})
    return controls


def write_tsv(path, rows, fields):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--settings", required=True)
    parser.add_argument("--normalized", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--controls", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    try:
        settings = read_settings(args.settings)
        rows = load_rows(args.metadata, settings)
        allow_missing = clean(settings.get("ALLOW_MISSING_CONTROLS")).lower() in TRUE_VALUES
        controls = validate_relationships(rows, allow_missing)

        native_mode = clean(settings.get("NATIVE_RUN_MODE")).lower()
        alignment_enabled = native_mode in {"alignment", "post_alignment"}
        bam_processing_enabled = native_mode == "post_alignment"
        reference = resolve_file(
            settings.get("GENOME_FASTA"), os.getcwd(), "GENOME_FASTA", "reference", alignment_enabled
        )
        annotation = resolve_file(
            settings.get("ANNOTATION_FILE"), os.getcwd(), "ANNOTATION_FILE", "reference", False
        )
        blacklist = (
            resolve_file(settings.get("BLACKLIST_BED"), os.getcwd(), "BLACKLIST_BED", "reference", False)
            if bam_processing_enabled
            else clean(settings.get("BLACKLIST_BED"))
        )
        index_prefix = clean(settings.get("BOWTIE2_INDEX_PREFIX"))
        if alignment_enabled and not index_prefix:
            raise ValueError("BOWTIE2_INDEX_PREFIX is required for the Bowtie2 provider")
        if bam_processing_enabled and not clean(settings.get("FILTER_DIR")):
            raise ValueError("FILTER_DIR is required for native post-alignment processing")

        normalized_fields = list(rows[0].keys())
        write_tsv(args.normalized, rows, normalized_fields)

        plan_rows = []
        for row in rows:
            plan_rows.append({
                **row,
                "genome_fasta": reference,
                "annotation_file": annotation,
                "blacklist_bed": blacklist,
                "qc_dir": clean(settings.get("QC_DIR")),
                "align_dir": clean(settings.get("ALIGN_DIR")),
                "filter_dir": clean(settings.get("FILTER_DIR")),
                "index_prefix": index_prefix,
                "bowtie2_build_opts": clean(settings.get("BOWTIE2_BUILD_OPTS")),
                "bowtie2_opts": clean(settings.get("BOWTIE2_OPTS")),
                "min_mapq": clean(settings.get("MIN_MAPQ")) or "30",
                "remove_secondary_supplementary": clean(settings.get("REMOVE_SECONDARY_SUPPLEMENTARY")) or "true",
                "remove_duplicates": clean(settings.get("REMOVE_DUPLICATES")) or "false",
                "dedup_tool": clean(settings.get("DEDUP_TOOL")) or "samtools",
            })
        plan_fields = normalized_fields + [
            "genome_fasta", "annotation_file", "blacklist_bed", "qc_dir", "align_dir", "filter_dir",
            "index_prefix", "bowtie2_build_opts", "bowtie2_opts", "min_mapq",
            "remove_secondary_supplementary", "remove_duplicates", "dedup_tool",
        ]
        write_tsv(args.plan, plan_rows, plan_fields)
        write_tsv(args.controls, controls, ["record_id", "sample_id", "control_id"])

        report = {
            "schema_version": "0.1",
            "status": "valid",
            "records": len(rows),
            "samples": len({row["sample_id"] for row in rows}),
            "controls": sum(row["is_control"] == "true" for row in rows),
            "ip_records": sum(row["is_control"] == "false" for row in rows),
            "datasets": sorted({row["dataset"] for row in rows}),
            "genome_ids": sorted({row["genome_id"] for row in rows}),
            "biological_replicates": sorted({row["biological_replicate"] for row in rows}),
        }
        with open(args.report, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
            handle.write("\n")
        print(f"validated {len(rows)} records and {len(controls)} IP/control relationships")
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
