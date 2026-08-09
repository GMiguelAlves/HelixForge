#!/usr/bin/env python3
import argparse
import base64
import csv
import json
import math
import os
import re
import shlex
import sys
from collections import defaultdict


TRUE = {"true", "1", "yes", "y"}
SAFE = re.compile(r"[^A-Za-z0-9._-]+")
MANAGED_OPTIONS = {
    "-t", "--treatment", "-c", "--control", "-f", "--format", "-g", "--gsize",
    "-n", "--name", "--outdir", "-q", "--qvalue", "-p", "--pvalue", "--broad",
    "--keep-dup", "-B", "--bdg", "--trackline",
}


def clean(value):
    return "" if value is None else str(value).strip()


def read_tsv(path):
    with open(path, encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if not reader.fieldnames:
            raise ValueError("ChIP-seq plan has no header")
        rows = list(reader)
        if not rows:
            raise ValueError("ChIP-seq plan contains no records")
        return reader.fieldnames, rows


def write_tsv(path, fields, rows):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def positive_probability(value, name):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be numeric, got {value!r}")
    if not math.isfinite(parsed) or not 0 < parsed <= 1:
        raise ValueError(f"{name} must be > 0 and <= 1, got {value!r}")
    return parsed


def positive_genome_size(value):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise ValueError(
            f"effective_genome_size must be an explicit positive number; organism aliases and 'auto' are not accepted, got {value!r}"
        )
    if not math.isfinite(parsed) or parsed <= 0:
        raise ValueError(f"effective_genome_size must be > 0, got {value!r}")
    return value


def safe_component(value, label):
    normalized = SAFE.sub("_", clean(value)).strip("._-")
    if not normalized:
        raise ValueError(f"{label} cannot be normalized to a safe output identifier")
    return normalized


def choose(spec, key, row, row_key, default=""):
    if key in spec and spec[key] is not None:
        return clean(spec[key])
    return clean(row.get(row_key)) or clean(default)


def validate_additional_args(value):
    try:
        tokens = shlex.split(value)
    except ValueError as error:
        raise ValueError(f"additional_args cannot be parsed: {error}")
    for token in tokens:
        option = token.split("=", 1)[0]
        managed_short = not option.startswith("--") and any(
            option.startswith(prefix) for prefix in ("-t", "-c", "-f", "-g", "-n", "-q", "-p")
        )
        if option in MANAGED_OPTIONS or managed_short:
            raise ValueError(f"additional_args cannot override managed MACS3 option {option}")
    return value


def resolve_control(row, controls_by_record, controls_by_sample):
    control_id = clean(row.get("control_id"))
    if not control_id:
        return None
    candidates = controls_by_record.get(control_id, []) or controls_by_sample.get(control_id, [])
    if not candidates:
        raise ValueError(f"record {row['record_id']}: control_id {control_id!r} does not identify a control")
    if len(candidates) > 1:
        records = ", ".join(candidate["record_id"] for candidate in candidates)
        raise ValueError(
            f"record {row['record_id']}: control_id {control_id!r} is ambiguous ({records}); use an explicit control record_id"
        )
    control = candidates[0]
    for field in ("dataset", "genome_id", "organism", "layout"):
        if clean(row.get(field)) and clean(control.get(field)) and clean(row[field]) != clean(control[field]):
            raise ValueError(
                f"record {row['record_id']} and control {control['record_id']} disagree on {field}"
            )
    return control


def build_peak_plan(rows, spec):
    controls = [row for row in rows if clean(row.get("is_control")).lower() in TRUE]
    controls_by_record = defaultdict(list)
    controls_by_sample = defaultdict(list)
    for control in controls:
        controls_by_record[control["record_id"]].append(control)
        controls_by_sample[control["sample_id"]].append(control)

    peak_rows = []
    peak_ids = set()
    output_targets = set()
    replicate_keys = set()
    for row in rows:
        if clean(row.get("is_control")).lower() in TRUE:
            continue
        record_id = clean(row.get("record_id"))
        caller = choose(spec, "caller", row, "peak_caller", "macs3").lower()
        if caller != "macs3":
            raise ValueError(f"record {record_id}: unsupported peak caller {caller!r}; Peak Calling API v1 supports macs3")
        caller_version = choose(spec, "caller_version", row, "caller_version", "3.0.4")
        peak_type = choose(spec, "peak_type", row, "peak_type").lower()
        if peak_type not in {"narrow", "broad"}:
            raise ValueError(f"record {record_id}: peak_type must be explicitly narrow or broad, got {peak_type!r}")

        effective_size = choose(spec, "effective_genome_size", row, "macs_genome_size")
        positive_genome_size(effective_size)

        p_override = clean(spec.get("p_value")) if spec.get("p_value") is not None else ""
        if p_override:
            p_value = positive_probability(p_override, "p_value")
            q_value = ""
            cutoff_type, cutoff = "p_value", p_value
        else:
            q_raw = choose(spec, "q_value", row, "macs_qvalue")
            p_raw = clean(row.get("macs_pvalue"))
            if p_raw and q_raw:
                raise ValueError(f"record {record_id}: q_value and p_value are mutually exclusive")
            if p_raw and not q_raw:
                p_value = positive_probability(p_raw, "p_value")
                q_value = ""
                cutoff_type, cutoff = "p_value", p_value
            else:
                q_value = positive_probability(q_raw, "q_value")
                p_value = ""
                cutoff_type, cutoff = "q_value", q_value

        layout = clean(row.get("layout")).lower()
        expected_format = "BAMPE" if layout == "paired" else "BAM"
        input_format = choose(spec, "format", row, "peak_format", expected_format).upper()
        if input_format != expected_format:
            raise ValueError(
                f"record {record_id}: format {input_format!r} is incompatible with layout {layout!r}; expected {expected_format}"
            )
        duplicate_policy = choose(spec, "duplicate_policy", row, "peak_duplicate_policy", "all").lower()
        if duplicate_policy not in {"all", "auto"} and not duplicate_policy.isdigit():
            raise ValueError(f"record {record_id}: duplicate_policy must be all, auto, or a positive integer")
        if duplicate_policy.isdigit() and int(duplicate_policy) < 1:
            raise ValueError(f"record {record_id}: duplicate_policy integer must be >= 1")
        additional_args = validate_additional_args(choose(spec, "additional_args", row, "macs_extra_opts"))

        control = resolve_control(row, controls_by_record, controls_by_sample)
        target = clean(row.get("target"))
        peak_id = ".".join([
            safe_component(record_id, "record_id"), safe_component(target, "target"), peak_type, caller
        ])
        peak_root = choose(spec, "output_dir", row, "peak_dir")
        if not peak_root:
            raise ValueError(f"record {record_id}: peak output directory is missing")
        result_path = os.path.join(peak_root, f"{peak_id}.peak_calling")
        replicate_key = (
            clean(row.get("sample_id")), clean(row.get("biological_replicate")),
            clean(row.get("technical_replicate")), target,
        )
        if replicate_key in replicate_keys:
            raise ValueError(f"record {record_id}: duplicate sample/replicate/target identity {replicate_key}")
        if peak_id in peak_ids or result_path in output_targets:
            raise ValueError(f"record {record_id}: peak output collision for {peak_id}")
        replicate_keys.add(replicate_key)
        peak_ids.add(peak_id)
        output_targets.add(result_path)

        peak_rows.append({
            **row,
            "peak_id": peak_id,
            "control_record_id": control["record_id"] if control else "",
            "caller": caller,
            "caller_version": caller_version,
            "peak_type": peak_type,
            "effective_genome_size": effective_size,
            "cutoff_type": cutoff_type,
            "cutoff": str(cutoff),
            "q_value": str(q_value),
            "p_value": str(p_value),
            "format": input_format,
            "paired_end_handling": "fragments" if input_format == "BAMPE" else "tags",
            "duplicate_policy": duplicate_policy,
            "additional_args": additional_args,
            "peak_target_dir": peak_root,
        })
    if not peak_rows:
        raise ValueError("peak calling plan contains no treatment/IP records")
    return peak_rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--spec-base64", required=True)
    parser.add_argument("--validated-plan", required=True)
    parser.add_argument("--peak-plan", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    try:
        spec = json.loads(base64.b64decode(args.spec_base64).decode("utf-8"))
        fields, rows = read_tsv(args.plan)
        peak_rows = build_peak_plan(rows, spec)
        write_tsv(args.validated_plan, fields, rows)
        extra = [field for field in peak_rows[0] if field not in fields]
        write_tsv(args.peak_plan, fields + extra, peak_rows)
        report = {
            "schema_version": "1.0", "type": "peak_calling_context", "status": "valid",
            "caller": sorted({row["caller"] for row in peak_rows}),
            "peak_types": sorted({row["peak_type"] for row in peak_rows}),
            "treatments": len(peak_rows),
            "with_control": sum(bool(row["control_record_id"]) for row in peak_rows),
            "without_control": sum(not row["control_record_id"] for row in peak_rows),
        }
        with open(args.report, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
            handle.write("\n")
        print(f"validated {len(peak_rows)} independent peak-calling requests")
    except (ValueError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
