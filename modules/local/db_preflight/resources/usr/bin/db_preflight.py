#!/usr/bin/env python3
import argparse
import csv
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys


SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
TRUE_VALUES = {"true", "1", "yes", "y"}


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path, label):
    if not os.path.isfile(path) or os.path.getsize(path) == 0:
        raise ValueError(f"{label} is missing or empty: {path}")
    with open(path, encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def read_plan(path):
    with open(path, encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        rows = list(reader)
    if not rows or "record_id" not in (reader.fieldnames or []):
        raise ValueError("peak plan is empty or lacks record_id")
    result = {}
    for row in rows:
        identifier = (row.get("record_id") or "").strip()
        if not identifier or identifier in result:
            raise ValueError(f"empty or duplicate peak-plan record_id: {identifier!r}")
        result[identifier] = {key: (value or "").strip() for key, value in row.items()}
    return result


def index_files(paths, label):
    result = {}
    for path in paths:
        name = os.path.basename(path)
        if name in result:
            raise ValueError(f"duplicate staged {label} basename: {name}")
        result[name] = path
    return result


def consensus_inputs(directories, manifests):
    dirs_by_id = {}
    for directory in directories:
        embedded = os.path.join(directory, "manifest.json")
        if not os.path.isfile(embedded):
            raise ValueError(f"Consensus result directory lacks manifest.json: {directory}")
        document = load_json(embedded, "embedded Consensus manifest")
        identifier = str(document.get("id", ""))
        if not identifier or identifier in dirs_by_id:
            raise ValueError(f"empty or duplicate Consensus directory id: {identifier!r}")
        dirs_by_id[identifier] = directory
    result = []
    seen = set()
    for path in manifests:
        document = load_json(path, "Consensus manifest")
        identifier = str(document.get("id", ""))
        provider_type = document.get("type")
        strategy = document.get("strategy")
        valid_provider = (
            (provider_type == "consensus" and strategy in {"union", "intersection", "replicate_support"})
            or (provider_type == "idr" and strategy == "idr")
        )
        if not valid_provider:
            raise ValueError(f"{path}: Differential Binding requires a completed Consensus/IDR manifest")
        if document.get("status") not in {"complete", "complete_empty"}:
            raise ValueError(f"{identifier}: Consensus/IDR result is unavailable ({document.get('status')})")
        if identifier in seen or identifier not in dirs_by_id:
            raise ValueError(f"duplicate or unmatched Consensus manifest id: {identifier!r}")
        seen.add(identifier)
        artifact = document.get("artifacts", {}).get("consolidated_bed", {})
        if not artifact.get("available"):
            raise ValueError(f"{identifier}: consolidated BED is unavailable")
        bed = os.path.join(dirs_by_id[identifier], os.path.basename(artifact.get("path", "consolidated_peaks.bed")))
        if not os.path.isfile(bed):
            raise ValueError(f"{identifier}: consolidated BED is missing")
        if artifact.get("sha256") and sha256(bed) != artifact["sha256"]:
            raise ValueError(f"{identifier}: consolidated BED checksum mismatch")
        result.append((document, path, bed))
    if not result:
        raise ValueError("no usable Consensus manifests were supplied")
    return result


def final_bam_inputs(bams, bais, manifests):
    bam_index, bai_index = index_files(bams, "BAM"), index_files(bais, "BAI")
    result = {}
    for path in manifests:
        document = load_json(path, "final BAM manifest")
        identifier = str(document.get("id", ""))
        if document.get("type") != "bam_final" or not identifier or identifier in result:
            raise ValueError(f"invalid or duplicate final BAM manifest id: {identifier!r}")
        bam_name = os.path.basename(document.get("artifact") or f"{identifier}.filtered.bam")
        bai_name = os.path.basename(document.get("index") or f"{bam_name}.bai")
        if bam_name not in bam_index or bai_name not in bai_index:
            raise ValueError(f"{identifier}: final BAM or index is missing")
        bam, bai = bam_index[bam_name], bai_index[bai_name]
        if document.get("sha256") and sha256(bam) != document["sha256"]:
            raise ValueError(f"{identifier}: final BAM checksum mismatch")
        if document.get("index_sha256") and sha256(bai) != document["index_sha256"]:
            raise ValueError(f"{identifier}: final BAI checksum mismatch")
        result[identifier] = {"document": document, "manifest": path, "bam": bam, "bai": bai,
                              "bam_file": bam_name, "bai_file": bai_name}
    return result


def validate_spec(spec):
    if spec.get("schema_version") != "1.0":
        raise ValueError("Differential Binding specification schema_version must be 1.0")
    if spec.get("provider") != "deseq2" or spec.get("test") != "wald":
        raise ValueError("v1 supports provider=deseq2 and test=wald only")
    if spec.get("normalization") != "deseq2_median_of_ratios":
        raise ValueError("DESeq2 models require normalization=deseq2_median_of_ratios")
    peak_universe = spec.get("peak_universe", {})
    if peak_universe.get("method") != "union":
        raise ValueError("v1 supports peak_universe.method=union only")
    counting = spec.get("counting", {})
    required_counting = {"provider": "featurecounts", "overlap_policy": "any",
                         "allow_multi_overlap": False, "allow_multimapping": False, "fractional": False}
    for field, expected in required_counting.items():
        if counting.get(field) != expected:
            raise ValueError(f"v1 counting requires {field}={str(expected).lower()}")
    try:
        strandedness, min_mapq = int(counting.get("strandedness", 0)), int(counting.get("min_mapq", 0))
    except (TypeError, ValueError):
        raise ValueError("counting strandedness and min_mapq must be integers")
    if strandedness not in {0, 1, 2} or min_mapq < 0:
        raise ValueError("counting strandedness must be 0/1/2 and min_mapq non-negative")
    design = spec.get("design", {})
    formula = " ".join(str(design.get("formula", "")).split())
    covariates = design.get("covariates", [])
    if design.get("variable") != "condition" or formula not in {"~ condition", "~ batch + condition"}:
        raise ValueError("v1 design must be ~ condition or ~ batch + condition with variable=condition")
    if covariates != ([] if formula == "~ condition" else ["batch"]):
        raise ValueError("design covariates must exactly match the supported formula")
    filter_spec = spec.get("filter", {})
    if filter_spec.get("method") not in {"none", "minimum_count"}:
        raise ValueError("filter method must be none or minimum_count")
    if filter_spec.get("method") == "minimum_count":
        if int(filter_spec.get("min_count", -1)) < 0 or int(filter_spec.get("min_samples", 0)) < 1:
            raise ValueError("minimum_count requires min_count >= 0 and min_samples >= 1")
    parameters = spec.get("parameters", {})
    if int(parameters.get("min_replicates", 0)) < 2:
        raise ValueError("parameters.min_replicates must be at least 2")
    alpha = float(parameters.get("alpha", 0))
    if not 0 < alpha <= 1:
        raise ValueError("parameters.alpha must be > 0 and <= 1")
    contrasts, ids = spec.get("contrasts", []), set()
    if not contrasts:
        raise ValueError("at least one explicit contrast is required")
    for contrast in contrasts:
        identifier = str(contrast.get("id", ""))
        if not SAFE_ID.fullmatch(identifier) or identifier in ids:
            raise ValueError(f"invalid or duplicate contrast id: {identifier!r}")
        ids.add(identifier)
        if contrast.get("factor") != "condition" or not contrast.get("numerator") or not contrast.get("denominator"):
            raise ValueError(f"contrast {identifier}: factor/numerator/denominator are invalid")
        if contrast["numerator"] == contrast["denominator"]:
            raise ValueError(f"contrast {identifier}: numerator equals denominator")
    return spec


def matrix_rank(matrix, tolerance=1e-10):
    values = [list(map(float, row)) for row in matrix]
    rows, columns, rank, pivot_row = len(values), len(values[0]), 0, 0
    for column in range(columns):
        pivot = max(range(pivot_row, rows), key=lambda row: abs(values[row][column]), default=None)
        if pivot is None or abs(values[pivot][column]) <= tolerance:
            continue
        values[pivot_row], values[pivot] = values[pivot], values[pivot_row]
        scale = values[pivot_row][column]
        values[pivot_row] = [value / scale for value in values[pivot_row]]
        for row in range(rows):
            if row == pivot_row:
                continue
            factor = values[row][column]
            values[row] = [left - factor * right for left, right in zip(values[row], values[pivot_row])]
        rank += 1
        pivot_row += 1
        if pivot_row == rows:
            break
    return rank


def validate_design(samples, design):
    columns = [[1.0] for _ in samples]
    terms = []
    for field in (["batch"] if "batch" in design.get("covariates", []) else []) + ["condition"]:
        values = [sample.get(field, "") for sample in samples]
        if any(not value for value in values):
            raise ValueError(f"design field {field} contains a missing value")
        levels = sorted(set(values))
        if len(levels) < 2:
            if field == "batch":
                raise ValueError("batch covariate has fewer than two levels")
            raise ValueError("condition has fewer than two levels")
        for level in levels[1:]:
            terms.append(f"{field}:{level}")
            for row, value in zip(columns, values):
                row.append(1.0 if value == level else 0.0)
    if matrix_rank(columns) != len(columns[0]):
        raise ValueError(f"design is rank deficient for terms {terms}")


def read_bed(path):
    intervals = []
    with open(path, encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 3:
                raise ValueError(f"{path} line {line_number}: expected at least BED3")
            try:
                start, end = int(fields[1]), int(fields[2])
            except ValueError:
                raise ValueError(f"{path} line {line_number}: invalid coordinates")
            if not fields[0] or start < 0 or end <= start:
                raise ValueError(f"{path} line {line_number}: invalid BED interval")
            intervals.append((fields[0], start, end))
    return intervals


def merge_universe(paths, analysis_id, output):
    intervals = sorted(interval for path in paths for interval in read_bed(path))
    if not intervals:
        raise ValueError(f"analysis {analysis_id}: selected peak universe is empty")
    merged = []
    for chrom, start, end in intervals:
        if merged and merged[-1][0] == chrom and start <= merged[-1][2]:
            merged[-1] = (chrom, merged[-1][1], max(end, merged[-1][2]))
        else:
            merged.append((chrom, start, end))
    with open(output, "w", encoding="utf-8") as handle:
        for index, (chrom, start, end) in enumerate(merged, 1):
            handle.write(f"{chrom}\t{start}\t{end}\t{analysis_id}.peak.{index:06d}\n")
    return len(intervals), len(merged)


def safe_analysis_id(values):
    return ".".join(re.sub(r"[^A-Za-z0-9._-]+", "_", str(value)) for value in values)


def build_analyses(consensus, bams, plan, spec, output_root):
    groups = defaultdict(list)
    for document, manifest, bed in consensus:
        key = tuple(document.get(field) for field in ("dataset", "experiment_id", "target", "genome_id", "peak_type", "caller", "caller_version"))
        if any(value in {None, ""} for value in key):
            raise ValueError(f"Consensus manifest {document.get('id')} has incomplete analysis identity")
        groups[key].append((document, manifest, bed))
    directories = {name: output_root / name for name in ("analysis_requests", "peak_universes", "sample_tables", "count_specs", "model_specs", "contrast_specs")}
    for directory in directories.values():
        directory.mkdir(parents=True, exist_ok=True)
    summaries = []
    for key, entries in sorted(groups.items()):
        dataset, experiment_id, target, genome_id, peak_type, caller, caller_version = key
        analysis_id = safe_analysis_id((dataset, experiment_id, target, genome_id, peak_type))
        samples_by_record = {}
        source_conditions = set()
        for document, _manifest, _bed in entries:
            if document.get("replicate_mode") != "biological" or document.get("replicate_policy") != "require_premerged":
                raise ValueError(f"analysis {analysis_id}: Differential Binding requires premerged biological replicates")
            source_conditions.add(document.get("condition"))
            for replicate in document.get("replicates", []):
                record_id = replicate.get("record_id")
                if not record_id or record_id in samples_by_record:
                    raise ValueError(f"analysis {analysis_id}: missing or duplicate record_id {record_id!r}")
                if record_id not in plan or record_id not in bams:
                    raise ValueError(f"analysis {analysis_id}: sample {record_id} has no matching plan/final BAM")
                row, bam = plan[record_id], bams[record_id]
                if bam["document"].get("sample_id") not in {None, "", row.get("sample_id")}:
                    raise ValueError(f"analysis {analysis_id}: sample {record_id} final BAM sample_id mismatch")
                for field, expected in (("sample_id", replicate.get("sample_id")), ("condition", replicate.get("condition")),
                                        ("biological_replicate", replicate.get("biological_replicate")),
                                        ("technical_replicate", replicate.get("technical_replicate"))):
                    if row.get(field) != str(expected or ""):
                        raise ValueError(f"analysis {analysis_id}: sample {record_id} metadata disagrees on {field}")
                if row.get("genome_id") != genome_id or row.get("target") != target:
                    raise ValueError(f"analysis {analysis_id}: sample {record_id} target/genome mismatch")
                samples_by_record[record_id] = {
                    "record_id": record_id, "sample_id": row["sample_id"], "condition": row["condition"],
                    "biological_replicate": row["biological_replicate"], "technical_replicate": row["technical_replicate"],
                    "batch": row.get("batch", ""), "layout": row["layout"],
                    "bam_file": bam["bam_file"], "bai_file": bam["bai_file"],
                    "bam_manifest": os.path.basename(bam["manifest"]),
                    "bam_sha256": sha256(bam["bam"]), "bai_sha256": sha256(bam["bai"]),
                    "duplicate_policy": bam["document"].get("duplicate_policy"),
                    "blacklist_policy": bam["document"].get("blacklist_policy"),
                }
        samples = sorted(samples_by_record.values(), key=lambda item: (item["condition"], item["biological_replicate"], item["sample_id"]))
        sample_ids = [sample["sample_id"] for sample in samples]
        if len(set(sample_ids)) != len(sample_ids):
            raise ValueError(f"analysis {analysis_id}: duplicate sample_id values are not statistical replicates")
        replicate_keys = [(sample["condition"], sample["biological_replicate"]) for sample in samples]
        if len(set(replicate_keys)) != len(replicate_keys):
            raise ValueError(f"analysis {analysis_id}: technical records are not premerged by biological replicate")
        layouts = {sample["layout"] for sample in samples}
        if len(layouts) != 1:
            raise ValueError(f"analysis {analysis_id}: mixed sequencing layouts are unsupported in one count model")
        expected_unit = "fragments" if layouts == {"paired"} else "reads"
        if spec["counting"].get("unit") != expected_unit:
            raise ValueError(f"analysis {analysis_id}: counting.unit must be {expected_unit}")
        conditions = {sample["condition"] for sample in samples}
        if source_conditions != conditions:
            raise ValueError(f"analysis {analysis_id}: Consensus conditions and sample conditions disagree")
        min_replicates = int(spec["parameters"]["min_replicates"])
        condition_counts = {condition: sum(sample["condition"] == condition for sample in samples) for condition in conditions}
        for contrast in spec["contrasts"]:
            for level in (contrast["numerator"], contrast["denominator"]):
                if level not in conditions:
                    raise ValueError(f"analysis {analysis_id}: contrast {contrast['id']} level {level!r} is absent")
                if condition_counts[level] < min_replicates:
                    raise ValueError(f"analysis {analysis_id}: condition {level} has fewer than {min_replicates} biological replicates")
        validate_design(samples, spec["design"])
        peak_bed = directories["peak_universes"] / f"{analysis_id}.bed"
        initial_peaks, merged_peaks = merge_universe([entry[2] for entry in entries], analysis_id, peak_bed)
        sample_table = directories["sample_tables"] / f"{analysis_id}.tsv"
        sample_fields = ["sample_id", "record_id", "condition", "biological_replicate", "technical_replicate", "batch", "layout"]
        with sample_table.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=sample_fields, delimiter="\t", lineterminator="\n", extrasaction="ignore")
            writer.writeheader(); writer.writerows(samples)
        count_spec = {
            "schema_version": "1.0", "analysis_id": analysis_id, "provider": "featurecounts",
            "dataset": dataset, "experiment_id": experiment_id, "target": target,
            "genome_id": genome_id, "peak_type": peak_type, "caller": caller, "caller_version": caller_version,
            "peak_universe": {**spec["peak_universe"], "initial_intervals": initial_peaks, "merged_intervals": merged_peaks,
                              "source_manifests": [{"id": document["id"], "sha256": sha256(manifest)} for document, manifest, _bed in entries]},
            "counting": spec["counting"], "samples": samples,
        }
        model_spec = {
            "schema_version": "1.0", "analysis_id": analysis_id, "model_id": f"{analysis_id}.deseq2",
            "provider": "deseq2", "test": "wald", "design": spec["design"], "filter": spec["filter"],
            "normalization": spec["normalization"], "parameters": spec["parameters"],
            "genome_id": genome_id, "peak_type": peak_type, "target": target,
        }
        count_path = directories["count_specs"] / f"{analysis_id}.count.json"
        model_path = directories["model_specs"] / f"{analysis_id}.model.json"
        count_path.write_text(json.dumps(count_spec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        model_path.write_text(json.dumps(model_spec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        contrast_files = []
        for order, contrast in enumerate(spec["contrasts"], 1):
            document = {"analysis_id": analysis_id, "model_id": model_spec["model_id"], **contrast,
                        "alpha": spec["parameters"]["alpha"], "lfc_threshold": spec["parameters"].get("lfc_threshold", 0), "order": order}
            path = directories["contrast_specs"] / f"{analysis_id}--{contrast['id']}.json"
            path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            contrast_files.append(path.name)
        request = {
            "schema_version": "1.0", "type": "differential_binding_request", "analysis_id": analysis_id,
            "dataset": dataset, "experiment_id": experiment_id, "target": target, "genome_id": genome_id,
            "peak_type": peak_type, "conditions": sorted(conditions), "samples": samples,
            "peak_bed": peak_bed.name, "sample_table": sample_table.name,
            "count_spec": count_path.name, "model_spec": model_path.name, "contrast_specs": contrast_files,
            "provenance": {"spec_sha256": sha256(spec["_path"]), "peak_bed_sha256": sha256(peak_bed),
                           "sample_table_sha256": sha256(sample_table)}, "status": "valid",
        }
        (directories["analysis_requests"] / f"{analysis_id}.json").write_text(json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        summaries.append({"analysis_id": analysis_id, "target": target, "genome_id": genome_id, "peak_type": peak_type,
                          "conditions": ",".join(sorted(conditions)), "samples": len(samples), "peaks": merged_peaks,
                          "contrasts": len(contrast_files), "status": "valid"})
    return summaries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--consensus-dir", action="append", required=True)
    parser.add_argument("--consensus-manifest", action="append", required=True)
    parser.add_argument("--bam", action="append", required=True)
    parser.add_argument("--bai", action="append", required=True)
    parser.add_argument("--bam-manifest", action="append", required=True)
    parser.add_argument("--peak-plan", required=True)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    try:
        spec = validate_spec(load_json(args.spec, "Differential Binding specification"))
        spec["_path"] = args.spec
        consensus = consensus_inputs(args.consensus_dir, args.consensus_manifest)
        bams = final_bam_inputs(args.bam, args.bai, args.bam_manifest)
        plan = read_plan(args.peak_plan)
        output_root = Path(args.output_dir)
        summaries = build_analyses(consensus, bams, plan, spec, output_root)
        if not summaries:
            raise ValueError("no Differential Binding analyses were planned")
        fields = list(summaries[0])
        with (output_root / "db_preflight_summary.tsv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
            writer.writeheader(); writer.writerows(summaries)
        report = {"schema_version": "1.0", "type": "differential_binding_preflight", "status": "valid",
                  "analyses": len(summaries), "contrasts": len(summaries) * len(spec["contrasts"]), "rows": summaries}
        print(json.dumps(report, indent=2, sort_keys=True))
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as error:
        print(json.dumps({"schema_version": "1.0", "type": "differential_binding_preflight", "status": "invalid", "error": str(error)}, indent=2), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
