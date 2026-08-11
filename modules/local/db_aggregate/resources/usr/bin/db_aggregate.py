#!/usr/bin/env python3
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def read_tsv(path):
    with open(path, encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return list(reader.fieldnames or []), list(reader)


def write_tsv(path, fields, rows):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--counts", action="append", required=True, type=Path)
    parser.add_argument("--model", action="append", required=True, type=Path)
    parser.add_argument("--contrast", action="append", required=True, type=Path)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    spec = load_json(args.spec)
    output = args.output_dir
    for name in ("counts", "models", "contrasts"):
        (output / name).mkdir(parents=True, exist_ok=True)

    analyses = {}
    for directory in args.counts:
        document = load_json(directory / "manifest.json")
        analysis_id = document["id"]
        if analysis_id in analyses:
            raise ValueError(f"duplicate count analysis id: {analysis_id}")
        target = output / "counts" / analysis_id
        target.mkdir(parents=True)
        for name in ("raw_peak_counts.tsv", "featurecounts_summary.tsv", "count_spec.json", "manifest.json"):
            shutil.copy2(directory / name, target / name)
        analyses[analysis_id] = {"analysis_id": analysis_id, "count_manifest": document,
                                 "raw_counts": {"path": str(target.relative_to(output) / "raw_peak_counts.tsv"), "sha256": sha256(target / "raw_peak_counts.tsv")}}

    for directory in args.model:
        model_spec = load_json(directory / "model_spec.json")
        analysis_id = model_spec["analysis_id"]
        if analysis_id not in analyses or "model" in analyses[analysis_id]:
            raise ValueError(f"missing count or duplicate model for {analysis_id}")
        target = output / "models" / analysis_id
        target.mkdir(parents=True)
        for name in ("dds.rds", "normalized_peak_counts.tsv", "dispersions.tsv", "coefficients.tsv", "model_statistics.json", "model_spec.json", "model_manifest.json"):
            shutil.copy2(directory / name, target / name)
        analyses[analysis_id]["model"] = {"path": str(target.relative_to(output) / "dds.rds"), "sha256": sha256(target / "dds.rds")}
        analyses[analysis_id]["normalized_counts"] = {"path": str(target.relative_to(output) / "normalized_peak_counts.tsv"), "sha256": sha256(target / "normalized_peak_counts.tsv")}

    combined, result_fields, summaries = [], [], []
    contrast_ids = set()
    for directory in args.contrast:
        model_spec = load_json(directory / "model_spec.json")
        contrast_spec = load_json(directory / "contrast_spec.json")
        analysis_id, contrast_id = model_spec["analysis_id"], contrast_spec["id"]
        key = (analysis_id, contrast_id)
        if analysis_id not in analyses or key in contrast_ids:
            raise ValueError(f"missing model or duplicate contrast: {analysis_id}/{contrast_id}")
        contrast_ids.add(key)
        target = output / "contrasts" / analysis_id / contrast_id
        target.mkdir(parents=True)
        for name in ("differential_binding_results.tsv", "ma_plot_data.tsv", "contrast_statistics.json", "contrast_spec.json", "contrast_manifest.json"):
            shutil.copy2(directory / name, target / name)
        fields, rows = read_tsv(target / "differential_binding_results.tsv")
        if not result_fields:
            result_fields = ["analysis_id", *fields]
        elif fields != result_fields[1:]:
            raise ValueError("contrast result schemas disagree")
        combined.extend({"analysis_id": analysis_id, **row} for row in rows)
        statistics = load_json(target / "contrast_statistics.json")
        summaries.append({"analysis_id": analysis_id, "contrast": contrast_id, "samples": statistics["samples"],
                          "peaks": statistics["peaks"], "significant": statistics["significant"], "status": statistics.get("status", "complete")})
        analyses[analysis_id].setdefault("contrasts", []).append({
            "id": contrast_id, "numerator": contrast_spec["numerator"], "denominator": contrast_spec["denominator"],
            "results": {"path": str(target.relative_to(output) / "differential_binding_results.tsv"), "sha256": sha256(target / "differential_binding_results.tsv")},
            "ma_data": {"path": str(target.relative_to(output) / "ma_plot_data.tsv"), "sha256": sha256(target / "ma_plot_data.tsv")},
        })
    if not combined:
        raise ValueError("no Differential Binding contrast results were supplied")
    write_tsv(output / "differential_binding_results.tsv", result_fields, combined)
    summary_fields = ["analysis_id", "contrast", "samples", "peaks", "significant", "status"]
    write_tsv(output / "differential_binding_summary.tsv", summary_fields, summaries)
    manifest = {
        "schema_version": "1.0", "type": "differential_binding", "id": "chipseq.differential_binding",
        "provider": spec["provider"], "test": spec["test"], "design": spec["design"],
        "normalization": spec["normalization"], "filter": spec["filter"],
        "analyses": [analyses[key] for key in sorted(analyses)], "contrasts": len(contrast_ids),
        "artifacts": {"results": {"path": "differential_binding_results.tsv", "sha256": sha256(output / "differential_binding_results.tsv"), "available": True},
                      "summary": {"path": "differential_binding_summary.tsv", "sha256": sha256(output / "differential_binding_summary.tsv"), "available": True}},
        "status": "complete",
    }
    args.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
