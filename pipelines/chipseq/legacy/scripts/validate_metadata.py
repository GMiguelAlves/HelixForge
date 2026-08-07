#!/usr/bin/env python3
import argparse
import csv
import gzip
import os
import sys
from collections import Counter, defaultdict


REQUIRED_COLUMNS = [
    "sample_id",
    "fastq_1",
    "fastq_2",
    "layout",
    "assay",
    "mark_or_factor",
    "condition",
    "replicate",
    "batch",
    "treatment",
    "control_id",
    "is_control",
    "organism",
    "genome_id",
]


TRUE_VALUES = {"true", "1", "yes", "y"}
FALSE_VALUES = {"false", "0", "no", "n"}


def fail(messages):
    for msg in messages:
        print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def warn(messages):
    for msg in messages:
        print(f"WARNING: {msg}", file=sys.stderr)


def resolve_path(path, base):
    if not path:
        return ""
    if os.path.isabs(path) or (len(path) > 2 and path[1] == ":"):
        return path
    return os.path.join(base, path)


def parse_bool(value):
    value = (value or "").strip().lower()
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    return None


def open_text(path):
    if path.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8-sig", newline="")
    return open(path, newline="", encoding="utf-8-sig")


def main():
    parser = argparse.ArgumentParser(description="Validate ChIP-seq metadata TSV")
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--fastq-dir", required=True)
    parser.add_argument("--min-replicates", type=int, default=2)
    parser.add_argument("--require-diff-replicates", action="store_true")
    parser.add_argument(
        "--allow-missing-controls",
        action="store_true",
        help="Allow IP samples with empty control_id; peak calling will run without matched input/control.",
    )
    args = parser.parse_args()

    errors = []
    warnings = []

    if not os.path.exists(args.metadata):
        fail([f"Metadata file not found: {args.metadata}"])

    with open_text(args.metadata) as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        header = reader.fieldnames or []
        missing = [c for c in REQUIRED_COLUMNS if c not in header]
        if missing:
            fail([f"Missing required metadata columns: {', '.join(missing)}"])
        rows = [dict(row) for row in reader if any((v or "").strip() for v in row.values())]

    if not rows:
        fail(["Metadata file has no sample rows"])

    sample_ids = [(row.get("sample_id") or "").strip() for row in rows]
    empty_ids = [i + 2 for i, sid in enumerate(sample_ids) if not sid]
    if empty_ids:
        errors.append(f"Empty sample_id at metadata line(s): {', '.join(map(str, empty_ids))}")

    duplicate_ids = sorted([sid for sid, n in Counter(sample_ids).items() if sid and n > 1])
    if duplicate_ids:
        errors.append(f"Duplicated sample_id values: {', '.join(duplicate_ids)}")

    sample_set = set(sample_ids)
    control_rows = {}
    ip_rows = {}

    for idx, row in enumerate(rows, start=2):
        sid = (row.get("sample_id") or "").strip()
        layout = (row.get("layout") or "").strip().lower()
        is_control = parse_bool(row.get("is_control"))

        if layout not in {"single", "paired"}:
            errors.append(f"{sid or 'line ' + str(idx)}: layout must be single or paired")

        if is_control is None:
            errors.append(f"{sid or 'line ' + str(idx)}: is_control must be true or false")
        elif is_control:
            control_rows[sid] = row
        else:
            ip_rows[sid] = row

        fq1 = resolve_path((row.get("fastq_1") or "").strip(), args.fastq_dir)
        fq2 = resolve_path((row.get("fastq_2") or "").strip(), args.fastq_dir)

        if not fq1:
            errors.append(f"{sid}: fastq_1 is required")
        elif not os.path.exists(fq1):
            errors.append(f"{sid}: fastq_1 does not exist: {fq1}")

        if layout == "paired":
            if not fq2:
                errors.append(f"{sid}: fastq_2 is required for paired layout")
            elif not os.path.exists(fq2):
                errors.append(f"{sid}: fastq_2 does not exist: {fq2}")
        elif layout == "single" and fq2:
            warnings.append(f"{sid}: fastq_2 is set but layout is single; it will be ignored")

    for sid, row in ip_rows.items():
        control_id = (row.get("control_id") or "").strip()
        if not control_id:
            if args.allow_missing_controls:
                warnings.append(
                    f"{sid}: control_id is empty; peak calling will run without matched input/control"
                )
            else:
                errors.append(f"{sid}: non-control sample must define control_id")
        elif control_id not in sample_set:
            errors.append(f"{sid}: control_id points to unknown sample: {control_id}")
        elif control_id not in control_rows:
            errors.append(f"{sid}: control_id must point to a sample with is_control=true: {control_id}")
        elif control_id == sid:
            errors.append(f"{sid}: control_id cannot point to itself")

    groups = defaultdict(list)
    for sid, row in ip_rows.items():
        key = (
            (row.get("condition") or "").strip(),
            (row.get("mark_or_factor") or "").strip(),
        )
        groups[key].append(sid)

    low_rep_groups = {
        key: ids for key, ids in groups.items() if len(ids) < args.min_replicates
    }
    if low_rep_groups:
        msg = "; ".join(
            f"condition={k[0]}, mark_or_factor={k[1]} has {len(v)} replicate(s)"
            for k, v in sorted(low_rep_groups.items())
        )
        if args.require_diff_replicates:
            errors.append(f"Insufficient replicates for differential binding: {msg}")
        else:
            warnings.append(f"Some groups have too few replicates for differential binding: {msg}")

    if errors:
        fail(errors)
    warn(warnings)
    print(f"Metadata validation passed: {len(rows)} samples, {len(ip_rows)} IPs, {len(control_rows)} controls")


if __name__ == "__main__":
    main()
