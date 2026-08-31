#!/usr/bin/env python3
"""Create HelixForge inputs for the frozen K562 H3K27me3 Real Broad arm."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def shell_quote(value: object) -> str:
    return "'" + str(value).replace("'", "'\"'\"'") + "'"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-root", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    args = parser.parse_args()
    benchmark = args.benchmark_root.resolve()
    run_root = args.run_root.resolve()
    expected = Path("/scratch/Schisto-epigenetics/gustavo/helixforge-chipseq-real-broad-benchmark-20260830")
    if benchmark != expected:
        raise ValueError(f"unexpected benchmark root: {benchmark}")
    run_root.mkdir(parents=True, exist_ok=False)

    fastq_dir = benchmark / "downloads/fastq"
    reference_dir = benchmark / "reference"
    download_manifest = benchmark / "downloads/provenance/download_manifest.json"
    reference_manifest = reference_dir / "reference_manifest.json"
    for path, status in ((download_manifest, "DOWNLOAD_CHECKSUM_VALIDATED"), (reference_manifest, "REFERENCE_READY")):
        if json.loads(path.read_text(encoding="utf-8"))["status"] != status:
            raise ValueError(f"upstream manifest is not ready: {path}")

    definitions = (
        ("K562_INPUT", "ENCFF000BWK", "input", "Input", "1", "true", ""),
        ("K562_H3K27ME3_R1", "ENCFF000BXP", "H3K27me3", "H3K27me3", "1", "false", "ENCFF000BWK"),
        ("K562_H3K27ME3_R2", "ENCFF000BXN", "H3K27me3", "H3K27me3", "2", "false", "ENCFF000BWK"),
    )
    rows = []
    for sample, accession, condition, target, replicate, is_control, control in definitions:
        fastq = fastq_dir / f"{accession}.fastq.gz"
        if not fastq.is_file():
            raise FileNotFoundError(fastq)
        rows.append({
            "sample_id": sample, "run_accession": accession, "fastq_1": fastq.name, "fastq_2": "",
            "layout": "single", "assay": "input" if is_control == "true" else "ChIP-seq",
            "condition": condition, "biological_replicate": replicate, "technical_replicate": "1",
            "antibody": "" if is_control == "true" else "H3K27me3", "target": target,
            "control_id": control, "is_control": is_control, "batch": "ENCODE_legacy_K562",
            "lane": "", "dataset": "encode_k562_h3k27me3_real_broad",
            "organism": "Homo_sapiens", "genome_id": "GRCh38.p14_GENCODE_50",
        })

    metadata = run_root / "metadata.tsv"
    with metadata.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    results = run_root.parent / "results"
    values = {
        "FASTQ_DIR": fastq_dir, "METADATA_FILE": metadata, "GENOME_FASTA": reference_dir / "genome.fa",
        "ANNOTATION_FILE": reference_dir / "annotation.gtf", "BLACKLIST_BED": reference_dir / "blacklist.bed",
        "OUTPUT_DIR": results, "WORK_ROOT": run_root / "work", "REF_DIR": results / "010-reference",
        "QC_DIR": results / "030-qc-fastq", "ALIGN_DIR": results / "050-alignment",
        "FILTER_DIR": results / "060-filtering", "PEAK_DIR": results / "080-peak-calling",
        "BOWTIE2_INDEX_PREFIX": results / "010-reference/bowtie2/genome", "ORGANISM_NAME": "Homo_sapiens",
        "ALIGNER": "bowtie2", "BOWTIE2_BUILD_OPTS": "", "BOWTIE2_OPTS": "--very-sensitive",
        "READ_LAYOUT": "metadata", "ALLOW_MISSING_CONTROLS": "false", "MIN_MAPQ": "30",
        "REMOVE_SECONDARY_SUPPLEMENTARY": "true", "REMOVE_DUPLICATES": "false", "DEDUP_TOOL": "samtools",
        "PEAK_CALLER": "macs3", "PEAK_TYPE": "broad", "MACS_QVALUE": "0.01", "MACS_PVALUE": "",
        "MACS_GENOME_SIZE": "2913022398", "MACS_EXTRA_OPTS": "", "THREADS": "8",
        "MEMORY": "24G", "SLURM_TIME": "12:00:00",
    }
    config = run_root / "pipeline_config.sh"
    config.write_text(
        "#!/usr/bin/env bash\n" + "".join(f"export {key}={shell_quote(value)}\n" for key, value in values.items()),
        encoding="utf-8", newline="\n",
    )
    manifest = {
        "schema_version": "1.0", "type": "helixforge_real_broad_input", "status": "ready",
        "benchmark_root": str(benchmark), "metadata": {"path": str(metadata), "sha256": digest(metadata)},
        "config": {"path": str(config), "sha256": digest(config)},
        "download_manifest": {"path": str(download_manifest), "sha256": digest(download_manifest)},
        "reference_manifest": {"path": str(reference_manifest), "sha256": digest(reference_manifest)},
        "samples": [row["sample_id"] for row in rows],
    }
    (run_root / "helixforge_input_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
