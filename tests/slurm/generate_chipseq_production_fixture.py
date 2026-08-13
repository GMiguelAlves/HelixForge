#!/usr/bin/env python3
"""Generate a deterministic reduced paired-end ChIP-seq validation bundle."""

import argparse
import csv
import hashlib
import json
import random
from pathlib import Path


READ_LENGTH = 50
FRAGMENT_LENGTH = 140
GENOME_LENGTH = 9000
SEED = 20260813


def reverse_complement(sequence):
    return sequence.translate(str.maketrans("ACGT", "TGCA"))[::-1]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_fastq(path, reference, starts, record_id, mate):
    with path.open("w", encoding="ascii", newline="\n") as handle:
        for index, start in enumerate(starts, 1):
            fragment = reference[start : start + FRAGMENT_LENGTH]
            sequence = fragment[:READ_LENGTH] if mate == 1 else reverse_complement(fragment[-READ_LENGTH:])
            handle.write(f"@{record_id}_{index:04d}/{mate}\n{sequence}\n+\n{'I' * READ_LENGTH}\n")


def background_positions(count, excluded):
    candidates = [position for position in range(100, GENOME_LENGTH - FRAGMENT_LENGTH - 100, 37)]
    return [position for position in candidates if all(abs(position - center) > 450 for center in excluded)][:count]


def clustered_positions(center, count, offset):
    return [center - 120 + ((index * 17 + offset) % 240) for index in range(count)]


def profiled_positions(profile, offset, background):
    starts = []
    for index, (center, count) in enumerate(profile):
        starts.extend(clustered_positions(center, count, offset + index * 13))
    starts.extend(background)
    return starts


def make_spec(path):
    document = {
        "schema_version": "1.0",
        "provider": "deseq2",
        "test": "wald",
        "peak_universe": {"method": "union"},
        "counting": {
            "provider": "featurecounts",
            "unit": "fragments",
            "strandedness": 0,
            "min_mapq": 0,
            "overlap_policy": "any",
            "allow_multi_overlap": False,
            "allow_multimapping": False,
            "fractional": False,
            "require_both_ends_mapped": True,
            "exclude_chimeric": True,
        },
        "design": {"formula": "~ condition", "variable": "condition", "covariates": []},
        "contrasts": [
            {
                "id": "treated_vs_control",
                "factor": "condition",
                "numerator": "treated",
                "denominator": "control",
            }
        ],
        "filter": {"method": "minimum_count", "min_count": 5, "min_samples": 2},
        "normalization": "deseq2_median_of_ratios",
        "parameters": {"alpha": 0.05, "lfc_threshold": 1.0, "min_replicates": 2},
    }
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", required=True, type=Path)
    args = parser.parse_args()
    root = args.case_root.resolve()
    fixture = root / "fixture"
    fastq_dir = fixture / "fastq"
    reference_dir = fixture / "reference"
    fastq_dir.mkdir(parents=True, exist_ok=False)
    reference_dir.mkdir(parents=True, exist_ok=False)

    generator = random.Random(SEED)
    reference = "".join(generator.choice("ACGT") for _ in range(GENOME_LENGTH))
    fasta = reference_dir / "genome.fa"
    with fasta.open("w", encoding="ascii", newline="\n") as handle:
        handle.write(">chrSynthetic\n")
        for start in range(0, len(reference), 80):
            handle.write(reference[start : start + 80] + "\n")

    annotation = reference_dir / "annotation.gtf"
    annotation.write_text(
        'chrSynthetic\tfixture\tgene\t901\t1900\t.\t+\t.\tgene_id "gene_control"; gene_name "GENE_CONTROL";\n'
        'chrSynthetic\tfixture\texon\t901\t1300\t.\t+\t.\tgene_id "gene_control"; gene_name "GENE_CONTROL";\n'
        'chrSynthetic\tfixture\texon\t1501\t1900\t.\t+\t.\tgene_id "gene_control"; gene_name "GENE_CONTROL";\n'
        'chrSynthetic\tfixture\tgene\t2801\t3900\t.\t+\t.\tgene_id "gene_treated"; gene_name "GENE_TREATED";\n'
        'chrSynthetic\tfixture\texon\t2801\t3300\t.\t+\t.\tgene_id "gene_treated"; gene_name "GENE_TREATED";\n'
        'chrSynthetic\tfixture\texon\t3501\t3900\t.\t+\t.\tgene_id "gene_treated"; gene_name "GENE_TREATED";\n'
        'chrSynthetic\tfixture\tgene\t4101\t4900\t.\t-\t.\tgene_id "gene_response_1"; gene_name "GENE_RESPONSE_1";\n'
        'chrSynthetic\tfixture\texon\t4101\t4500\t.\t-\t.\tgene_id "gene_response_1"; gene_name "GENE_RESPONSE_1";\n'
        'chrSynthetic\tfixture\tgene\t5701\t6500\t.\t+\t.\tgene_id "gene_response_2"; gene_name "GENE_RESPONSE_2";\n'
        'chrSynthetic\tfixture\texon\t5701\t6200\t.\t+\t.\tgene_id "gene_response_2"; gene_name "GENE_RESPONSE_2";\n',
        encoding="utf-8",
    )
    blacklist = reference_dir / "blacklist.bed"
    blacklist.write_text("chrSynthetic\t7000\t7100\n", encoding="utf-8")

    centers = (1300, 3000, 4600, 6200)
    background = background_positions(120, centers)
    records = [
        ("input_rep1", "input", "input", "1", True, "", background),
        ("control_rep1", "control", "H3K27ac", "1", False, "input_rep1", profiled_positions(zip(centers, (90, 70, 35, 25)), 1, background[:20])),
        ("control_rep2", "control", "H3K27ac", "2", False, "input_rep1", profiled_positions(zip(centers, (80, 60, 40, 30)), 5, background[20:45])),
        ("treated_rep1", "treated", "H3K27ac", "1", False, "input_rep1", profiled_positions(zip(centers, (35, 60, 105, 85)), 3, background[45:65])),
        ("treated_rep2", "treated", "H3K27ac", "2", False, "input_rep1", profiled_positions(zip(centers, (40, 55, 90, 75)), 9, background[65:90])),
    ]

    metadata_rows = []
    checksums = []
    for record_id, condition, target, replicate, is_control, control_id, starts in records:
        starts = list(dict.fromkeys(starts))
        r1 = fastq_dir / f"{record_id}_R1.fastq"
        r2 = fastq_dir / f"{record_id}_R2.fastq"
        write_fastq(r1, reference, starts, record_id, 1)
        write_fastq(r2, reference, starts, record_id, 2)
        checksums.extend([(r1.name, sha256(r1)), (r2.name, sha256(r2))])
        metadata_rows.append(
            {
                "sample_id": record_id,
                "run_accession": record_id,
                "fastq_1": r1.name,
                "fastq_2": r2.name,
                "layout": "paired",
                "assay": "input" if is_control else "ChIP-seq",
                "condition": condition,
                "biological_replicate": replicate,
                "technical_replicate": "1",
                "antibody": "" if is_control else "synthetic-antibody",
                "target": target,
                "control_id": control_id,
                "is_control": str(is_control).lower(),
                "batch": "batch1",
                "lane": "L001",
                "dataset": "synthetic_chipseq_validation",
                "organism": "synthetic",
                "genome_id": "synthetic_v1",
            }
        )

    metadata = fixture / "metadata.tsv"
    with metadata.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(metadata_rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(metadata_rows)

    reference_manifest = {
        "schema_version": "1.0",
        "type": "reference_bundle",
        "id": "synthetic.reference",
        "genome_id": "synthetic_v1",
        "build": "synthetic_v1",
        "organism": "synthetic",
        "artifacts": {
            "reference": {"available": True, "path": fasta.name, "sha256": sha256(fasta)},
            "annotation": {"available": True, "path": annotation.name, "sha256": sha256(annotation)},
            "blacklist": {"available": True, "path": blacklist.name, "sha256": sha256(blacklist)},
        },
        "status": "complete",
    }
    (reference_dir / "reference_manifest.json").write_text(
        json.dumps(reference_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    make_spec(root / "db_spec.json")

    results = root / "results"
    config = root / "pipeline_config.sh"
    values = {
        "FASTQ_DIR": fastq_dir,
        "METADATA_FILE": metadata,
        "GENOME_FASTA": fasta,
        "ANNOTATION_FILE": annotation,
        "BLACKLIST_BED": blacklist,
        "OUTPUT_DIR": results,
        "WORK_ROOT": results,
        "REF_DIR": results / "010-reference",
        "QC_DIR": results / "030-qc-fastq",
        "ALIGN_DIR": results / "050-alignment",
        "FILTER_DIR": results / "060-filtering",
        "PEAK_DIR": results / "080-peak-calling",
        "BOWTIE2_INDEX_PREFIX": results / "010-reference/bowtie2/genome",
    }
    lines = ["#!/usr/bin/env bash"] + [f"export {key}='{value}'" for key, value in values.items()]
    lines.extend(
        [
            "export ORGANISM_NAME='synthetic'",
            "export ALIGNER='bowtie2'",
            "export BOWTIE2_BUILD_OPTS=''",
            "export BOWTIE2_OPTS='--very-sensitive'",
            "export READ_LAYOUT='metadata'",
            "export ALLOW_MISSING_CONTROLS='false'",
            "export MIN_MAPQ='0'",
            "export REMOVE_SECONDARY_SUPPLEMENTARY='true'",
            "export REMOVE_DUPLICATES='false'",
            "export DEDUP_TOOL='samtools'",
            "export PEAK_CALLER='macs3'",
            "export PEAK_TYPE='narrow'",
            "export MACS_QVALUE='0.5'",
            "export MACS_PVALUE=''",
            f"export MACS_GENOME_SIZE='{GENOME_LENGTH}'",
            "export MACS_EXTRA_OPTS=''",
            "export THREADS='1'",
            "export MEMORY='2G'",
            "export SLURM_TIME='00:15:00'",
        ]
    )
    config.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (root / "input_checksums.tsv").write_text(
        "artifact\tsha256\n" + "".join(f"{name}\t{digest}\n" for name, digest in checksums), encoding="utf-8"
    )
    print(f"generated {len(records)} records and {sum(len(row[-1]) for row in records)} raw fragment declarations")


if __name__ == "__main__":
    main()
