#!/usr/bin/env python3
"""Create HelixForge metadata/context files for the frozen synthetic narrow dataset."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def shell_quote(value: object) -> str:
    return "'" + str(value).replace("'", "'\"'\"'") + "'"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    args = parser.parse_args()
    dataset = args.dataset_root.resolve()
    run_root = args.run_root.resolve()
    run_root.mkdir(parents=True, exist_ok=False)
    fastq_dir = dataset / "fastq"
    reference_dir = dataset / "reference"

    rows = []
    definitions = (
        ("input", "input", "input", "1", "true", ""),
        ("chip_rep1", "synthetic_narrow", "synthetic_factor", "1", "false", "input"),
        ("chip_rep2", "synthetic_narrow", "synthetic_factor", "2", "false", "input"),
    )
    for sample, condition, target, replicate, is_control, control_id in definitions:
        r1 = fastq_dir / f"{sample}_1.fastq"
        r2 = fastq_dir / f"{sample}_2.fastq"
        if not r1.is_file() or not r2.is_file():
            raise FileNotFoundError(f"FASTQ pair missing for {sample}")
        rows.append(
            {
                "sample_id": sample,
                "run_accession": sample,
                "fastq_1": r1.name,
                "fastq_2": r2.name,
                "layout": "paired",
                "assay": "input" if is_control == "true" else "ChIP-seq",
                "condition": condition,
                "biological_replicate": replicate,
                "technical_replicate": "1",
                "antibody": "" if is_control == "true" else "synthetic-antibody",
                "target": target,
                "control_id": control_id,
                "is_control": is_control,
                "batch": "synthetic_batch_1",
                "lane": "L001",
                "dataset": "chipseq-synthetic-narrow-v1",
                "organism": "synthetic",
                "genome_id": "synthetic_chip_v1",
            }
        )

    metadata = run_root / "metadata.tsv"
    with metadata.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    # The input contract lives in ``<run>/input`` while Nextflow publishes to
    # ``<run>/results``.  Keep metadata paths aligned with the real publish root.
    results = run_root.parent / "results"
    values = {
        "FASTQ_DIR": fastq_dir,
        "METADATA_FILE": metadata,
        "GENOME_FASTA": reference_dir / "synthetic_chip_v1.fa",
        "ANNOTATION_FILE": reference_dir / "synthetic_chip_v1.annotation.gtf",
        "BLACKLIST_BED": "",
        "OUTPUT_DIR": results,
        "WORK_ROOT": run_root / "work",
        "REF_DIR": results / "010-reference",
        "QC_DIR": results / "030-qc-fastq",
        "ALIGN_DIR": results / "050-alignment",
        "FILTER_DIR": results / "060-filtering",
        "PEAK_DIR": results / "080-peak-calling",
        "BOWTIE2_INDEX_PREFIX": results / "010-reference/bowtie2/genome",
        "ORGANISM_NAME": "synthetic",
        "ALIGNER": "bowtie2",
        "BOWTIE2_BUILD_OPTS": "",
        "BOWTIE2_OPTS": "--very-sensitive",
        "READ_LAYOUT": "metadata",
        "ALLOW_MISSING_CONTROLS": "false",
        "MIN_MAPQ": "30",
        "REMOVE_SECONDARY_SUPPLEMENTARY": "true",
        "REMOVE_DUPLICATES": "false",
        "DEDUP_TOOL": "samtools",
        "PEAK_CALLER": "macs3",
        "PEAK_TYPE": "narrow",
        "MACS_QVALUE": "0.01",
        "MACS_PVALUE": "",
        "MACS_GENOME_SIZE": "54000000",
        "MACS_EXTRA_OPTS": "",
        "THREADS": "8",
        "MEMORY": "24G",
        "SLURM_TIME": "12:00:00",
    }
    config = run_root / "pipeline_config.sh"
    config.write_text(
        "#!/usr/bin/env bash\n" + "".join(f"export {key}={shell_quote(value)}\n" for key, value in values.items()),
        encoding="utf-8",
        newline="\n",
    )

    manifest = {
        "schema_version": "1.0",
        "type": "helixforge_synthetic_narrow_input",
        "dataset_root": str(dataset),
        "metadata": {"path": str(metadata), "sha256": sha256(metadata)},
        "config": {"path": str(config), "sha256": sha256(config)},
        "reference": {
            "fasta": str(values["GENOME_FASTA"]),
            "sha256": sha256(Path(values["GENOME_FASTA"])),
            "effective_genome_size": 54000000,
        },
        "samples": [row["sample_id"] for row in rows],
        "status": "ready",
    }
    (run_root / "helixforge_input_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    main()
