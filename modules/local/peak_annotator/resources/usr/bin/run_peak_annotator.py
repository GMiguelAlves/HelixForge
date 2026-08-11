#!/usr/bin/env python3
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_attrs(text):
    attrs = {}
    if "=" in text:
        for part in text.strip().strip(";").split(";"):
            if "=" in part:
                key, value = part.split("=", 1)
                attrs[key.strip()] = value.strip()
    else:
        for key, value in re.findall(r'(\S+)\s+"([^"]+)"', text):
            attrs[key] = value
    return attrs


def gene_id(attrs):
    for key in ("gene_id", "gene", "ID", "Name", "locus_tag", "Parent"):
        if attrs.get(key):
            value = attrs[key].split(",", 1)[0] if key == "Parent" else attrs[key]
            return value.removeprefix("gene:")
    return "unknown_gene"


def read_annotation(path, upstream, downstream):
    genes, exons = {}, defaultdict(list)
    with open(path, encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip() or line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) != 9:
                raise ValueError(f"annotation line {line_number}: expected 9 columns")
            chrom, feature, strand = fields[0], fields[2].lower(), fields[6]
            start, end = int(fields[3]) - 1, int(fields[4])
            identifier = gene_id(parse_attrs(fields[8]))
            row = (chrom, start, end, identifier, strand)
            if feature in {"gene", "transcript", "mrna"}:
                old = genes.get(identifier)
                if old is None:
                    genes[identifier] = row
                else:
                    if old[0] != chrom or old[4] != strand:
                        raise ValueError(f"gene {identifier!r} has inconsistent contig or strand")
                    genes[identifier] = (chrom, min(old[1], start), max(old[2], end), identifier, strand)
            elif feature == "exon":
                exons[identifier].append(row)
    if not genes:
        for identifier, rows in exons.items():
            chrom, strand = rows[0][0], rows[0][4]
            if any(row[0] != chrom or row[4] != strand for row in rows):
                raise ValueError(f"gene {identifier!r} exons have inconsistent contig or strand")
            genes[identifier] = (chrom, min(row[1] for row in rows), max(row[2] for row in rows), identifier, strand)
    if not genes:
        raise ValueError("annotation contains no genes or exons")
    features = {name: defaultdict(list) for name in ("gene", "exon", "intron", "promoter", "downstream")}
    for identifier, gene in genes.items():
        chrom, start, end, _, strand = gene
        features["gene"][chrom].append(gene)
        gene_exons = sorted((row for row in exons.get(identifier, []) if row[0] == chrom), key=lambda row: (row[1], row[2], row[3]))
        features["exon"][chrom].extend(gene_exons)
        cursor = start
        for exon in gene_exons:
            if exon[1] > cursor:
                features["intron"][chrom].append((chrom, cursor, exon[1], identifier, strand))
            cursor = max(cursor, exon[2])
        if gene_exons and cursor < end:
            features["intron"][chrom].append((chrom, cursor, end, identifier, strand))
        if strand == "-":
            promoter = (chrom, max(0, end - downstream), end + upstream, identifier, strand)
            down = (chrom, max(0, start - upstream), start + downstream, identifier, strand)
        else:
            promoter = (chrom, max(0, start - upstream), start + downstream, identifier, strand)
            down = (chrom, max(0, end - downstream), end + upstream, identifier, strand)
        if promoter[2] > promoter[1]:
            features["promoter"][chrom].append(promoter)
        if down[2] > down[1]:
            features["downstream"][chrom].append(down)
    for group in features.values():
        for chrom in group:
            group[chrom].sort(key=lambda row: (row[1], row[2], row[3]))
    return features


def read_peaks(path):
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            fields = line.rstrip("\n").split("\t")
            chrom, start, end = fields[0], int(fields[1]), int(fields[2])
            peak_id = fields[3] if len(fields) > 3 and fields[3] not in {"", "."} else f"{chrom}:{start}-{end}"
            rows.append((peak_id, chrom, start, end))
    return rows


def overlapping(features, chrom, start, end):
    return [row for row in features.get(chrom, ()) if row[1] < end and row[2] > start]


def write_tsv(path, columns, rows):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\t".join(columns) + "\n")
        for row in rows:
            handle.write("\t".join(str(row.get(column, "")) for column in columns) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--peaks", required=True)
    parser.add_argument("--annotation", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--execution", required=True)
    parser.add_argument("--versions", required=True)
    parser.add_argument("--cpus", type=int, required=True)
    parser.add_argument("--memory-bytes", type=int, required=True)
    parser.add_argument("--task-time", required=True)
    parser.add_argument("--nextflow-version", required=True)
    args = parser.parse_args()
    started = int(time.time())
    try:
        with open(args.request, encoding="utf-8") as handle:
            request = json.load(handle)
        if request.get("status") not in {"valid", "stub"} or request.get("provider") != "python_interval_v1":
            raise ValueError("PEAK_ANNOTATOR requires a validated python_interval_v1 request")
        parameters = request["parameters"]
        features = read_annotation(args.annotation, parameters["promoter_upstream"], parameters["promoter_downstream"])
        peaks = read_peaks(args.peaks)
        output = Path(args.output_dir)
        reports = output / "provider_reports"
        reports.mkdir(parents=True, exist_ok=True)
        annotated, associations = [], []
        record_id = request.get("record_id") or ""
        for peak_id, chrom, start, end in peaks:
            category, hits = "intergenic", []
            for candidate in parameters["feature_priority"]:
                candidate_hits = overlapping(features[candidate], chrom, start, end)
                if candidate_hits:
                    category, hits = candidate, candidate_hits
                    break
            identifiers = sorted({row[3] for row in hits})
            if parameters["gene_assignment"] == "first" and identifiers:
                identifiers = identifiers[:1]
            included = not (category == "intergenic" and parameters["intergenic_policy"] == "drop")
            annotated.append({
                "peak_id": peak_id, "chrom": chrom, "start": start, "end": end,
                "category": category, "gene_ids": ";".join(identifiers),
                "gene_count": len(identifiers), "distance_to_tss": "",
                "record_id": record_id, "source_id": request["source_id"],
                "included": str(included).lower(),
            })
            for identifier in identifiers:
                associations.append({
                    "peak_id": peak_id, "gene_id": identifier, "category": category,
                    "distance_to_tss": "", "record_id": record_id,
                    "source_id": request["source_id"],
                })
        annotated_path = output / "annotated_peaks.tsv"
        association_path = output / "peak_gene_associations.tsv"
        write_tsv(annotated_path, ("peak_id", "chrom", "start", "end", "category", "gene_ids", "gene_count", "distance_to_tss", "record_id", "source_id", "included"), annotated)
        write_tsv(association_path, ("peak_id", "gene_id", "category", "distance_to_tss", "record_id", "source_id"), associations)
        feature_rows = []
        for name in ("gene", "exon", "intron", "promoter", "downstream"):
            feature_rows.append({"feature": name, "count": sum(len(rows) for rows in features[name].values())})
        write_tsv(reports / "annotation_features.tsv", ("feature", "count"), feature_rows)
        write_tsv(reports / "category_counts.tsv", ("category", "count"), ({"category": key, "count": value} for key, value in sorted(Counter(row["category"] for row in annotated).items())))
        ended = int(time.time())
        execution = {
            "schema_version": "1.0", "id": request["id"], "process": "PEAK_ANNOTATOR",
            "provider": request["provider"], "provider_version": request["provider_version"],
            "command": " ".join(sys.argv), "cpus": args.cpus,
            "memory_bytes": args.memory_bytes, "time": args.task_time,
            "nextflow_version": args.nextflow_version, "started_epoch": started,
            "ended_epoch": ended, "elapsed_seconds": ended - started,
        }
        with open(args.execution, "w", encoding="utf-8") as handle:
            json.dump(execution, handle, indent=2, sort_keys=True); handle.write("\n")
        with open(args.versions, "w", encoding="utf-8") as handle:
            handle.write(f'"PEAK_ANNOTATOR":\n    python: "{sys.version.split()[0]}"\n    provider: "python_interval_v1"\n')
        status = "complete" if annotated else "complete_empty"
        manifest = {
            "schema_version": "1.0", "type": "peak_annotation", "id": request["id"],
            "source_type": request["source_type"], "source_id": request["source_id"],
            "record_id": request.get("record_id"), "record_ids": request["record_ids"],
            "sample_ids": request["sample_ids"], "dataset": request.get("dataset"),
            "experiment_id": request.get("experiment_id"), "target": request.get("target"),
            "genome_id": request["genome_id"], "build": request["build"],
            "organism": request.get("organism"), "provider": request["provider"],
            "provider_version": request["provider_version"], "parameters": parameters,
            "inputs": request["inputs"], "artifacts": {
                "annotated_peaks": {"available": True, "path": "annotated_peaks.tsv", "sha256": sha256(annotated_path)},
                "peak_gene_associations": {"available": True, "path": "peak_gene_associations.tsv", "sha256": sha256(association_path)},
                "provider_reports": {"available": True, "path": "provider_reports"},
            }, "execution": execution, "provenance": {
                "source_manifest_sha256": request["inputs"]["peak_manifest"]["sha256"],
                "reference_manifest_sha256": request["inputs"]["reference_manifest"]["sha256"],
                "annotation_sha256": request["inputs"]["annotation"]["sha256"],
            }, "status": status,
        }
        with open(args.manifest, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True); handle.write("\n")
        with open(output / "manifest.json", "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True); handle.write("\n")
    except (ValueError, KeyError, json.JSONDecodeError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
