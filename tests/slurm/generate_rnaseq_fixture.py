#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import random
from pathlib import Path


SAMPLES = ("control_1", "control_2", "treated_1", "treated_2")
DNA = "ACGT"


def reverse_complement(sequence: str) -> str:
    return sequence.translate(str.maketrans("ACGT", "TGCA"))[::-1]


def transcript_sequence(index: int) -> str:
    rng = random.Random(20260811 + index)
    return "".join(rng.choice(DNA) for _ in range(320))


def read_counts(path: Path, increment: bool) -> tuple[list[str], dict[str, dict[str, int]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        genes = []
        counts = {sample: {} for sample in SAMPLES}
        for row in reader:
            gene = row["gene_id"]
            genes.append(gene)
            for sample in SAMPLES:
                counts[sample][gene] = int(row[sample])
    if increment:
        counts["control_1"][genes[0]] += 1
    return genes, counts


def gzip_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            compressed.write(text.encode("ascii"))


def write_fastqs(input_root: Path, genes: list[str], counts: dict[str, dict[str, int]]) -> None:
    sequences = {gene: transcript_sequence(i) for i, gene in enumerate(genes, start=1)}
    for sample in SAMPLES:
        run = f"RUN_{sample}"
        r1_records = []
        r2_records = []
        pair = 0
        for gene in genes:
            sequence = sequences[gene]
            r1 = sequence[20:70]
            r2 = reverse_complement(sequence[250:300])
            for _ in range(counts[sample][gene]):
                pair += 1
                name = f"@{sample}:{gene}:{pair}"
                quality = "I" * len(r1)
                r1_records.append(f"{name}/1\n{r1}\n+\n{quality}\n")
                r2_records.append(f"{name}/2\n{r2}\n+\n{quality}\n")
        raw_dir = input_root / "SYNTHETIC" / "fastq_ftp"
        gzip_text(raw_dir / f"{sample}_{run}_R1.fastq.gz", "".join(r1_records))
        gzip_text(raw_dir / f"{sample}_{run}_R2.fastq.gz", "".join(r2_records))


def write_reference(reference_root: Path, genes: list[str], mutate: bool) -> None:
    reference_root.mkdir(parents=True, exist_ok=True)
    fasta = []
    gtf = []
    gff = ["##gff-version 3\n"]
    for index, gene in enumerate(genes, start=1):
        sequence = transcript_sequence(index)
        if mutate and gene == genes[-1]:
            replacement = "A" if sequence[150] != "A" else "C"
            sequence = sequence[:150] + replacement + sequence[151:]
        transcript = f"tx{index:03d}"
        start = (index - 1) * 400 + 1
        end = start + len(sequence) - 1
        fasta.append(f">{transcript}\n{sequence}\n")
        gtf.append(
            f'chrSynthetic\thelixforge\ttranscript\t{start}\t{end}\t.\t+\t.\t'
            f'gene_id "{gene}"; transcript_id "{transcript}";\n'
        )
        gff.append(
            f"chrSynthetic\thelixforge\tgene\t{start}\t{end}\t.\t+\t.\t"
            f"ID={gene};Name={gene}\n"
        )
    (reference_root / "transcriptome.fa").write_text("".join(fasta), encoding="ascii")
    (reference_root / "annotation.gtf").write_text("".join(gtf), encoding="ascii")
    (reference_root / "annotation.gff3").write_text("".join(gff), encoding="ascii")


def write_tables(case_root: Path, genes: list[str], counts: dict[str, dict[str, int]]) -> None:
    metadata = case_root / "metadata.csv"
    with metadata.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["dataset", "sample_id", "file_prefix", "run_accession", "condition", "batch"],
        )
        writer.writeheader()
        for sample in SAMPLES:
            writer.writerow(
                {
                    "dataset": "SYNTHETIC",
                    "sample_id": sample,
                    "file_prefix": sample,
                    "run_accession": f"RUN_{sample}",
                    "condition": sample.split("_", 1)[0],
                    "batch": "B1" if sample.endswith("1") else "B2",
                }
            )

    expected = case_root / "expected_counts.tsv"
    with expected.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["gene_id", *SAMPLES])
        for gene in genes:
            writer.writerow([gene, *(counts[sample][gene] for sample in SAMPLES)])


def write_configuration(repo_root: Path, case_root: Path, conda_base: Path) -> None:
    pipeline_root = case_root / "pipeline"
    reference_root = case_root / "reference"
    settings = case_root / "user_settings.sh"
    settings.write_text(
        "#!/usr/bin/env bash\n"
        "export PIPELINE_NAME='helixforge_rnaseq_production_validation'\n"
        "export ORGANISM_NAME='synthetic_controlled_fixture'\n"
        "export PIPELINE_PROJECTS='SYNTHETIC'\n"
        f"export SCRATCH_ROOT='{case_root / 'inputs'}'\n"
        f"export CONDA_BASE='{conda_base}'\n"
        f"export REF_TRANSCRIPTS_FA='{reference_root / 'transcriptome.fa'}'\n"
        f"export REF_GTF='{reference_root / 'annotation.gtf'}'\n"
        f"export REF_GFF3='{reference_root / 'annotation.gff3'}'\n"
        f"export METADATA_FINAL='{case_root / 'metadata.csv'}'\n"
        f"export METADATA_FINAL_NEW='{case_root / 'metadata.csv'}'\n"
        f"export SCRIPTS_DIR='{repo_root / 'pipelines/rnaseq/legacy/scripts'}'\n"
        f"export SALMON_INDEX_DIR='{pipeline_root / '010-reference/salmon_index'}'\n"
        f"export QUANT_DIR='{pipeline_root / '040-alignment/quants'}'\n"
        "export QUANT_METHOD='salmon'\n"
        "export PIPELINE_EXECUTOR='local'\n"
        "export THREADS=1\n"
        "export TRIM_QUALITY=20\n"
        "export TRIM_LENGTH=20\n"
        "export SALMON_KMER_SIZE=31\n"
        "export RUN_SALMON_INDEX=1\n"
        "export RUN_STAR_INDEX=0\n"
        "export RUN_STAR_GTF_INDEX=0\n"
        "export RUN_BATCH_CORRECTION=0\n"
        "export RUN_GENE_REPORT=0\n"
        "export RNA_TOOLS_ENV='rna-tools'\n"
        "export PYTHON_ENV='python-list'\n"
        "export R_ANALYSIS_ENV='r-analysis'\n",
        encoding="utf-8",
    )
    config = case_root / "pipeline_config.sh"
    config.write_text(
        "#!/usr/bin/env bash\n"
        f"export PROJECT_DIR='{pipeline_root}'\n"
        f"export USER_SETTINGS_FILE='{settings}'\n"
        f"source '{repo_root / 'pipelines/rnaseq/legacy/config/pipeline_config.sh'}'\n",
        encoding="utf-8",
    )
    spec = {
        "schema_version": "1.0",
        "analysis_id": "rnaseq_production_validation",
        "scope": "all_projects",
        "correction": "raw",
        "provider": "deseq2",
        "test": "wald",
        "target_dir": str(pipeline_root / "060-deg-analysis/native"),
        "design": {"variable": "condition", "covariates": [], "formula": "~ condition"},
        "contrasts": [
            {
                "id": "condition__control_vs_treated",
                "factor": "condition",
                "numerator": "control",
                "denominator": "treated",
                "description": "control versus treated",
                "direction": "control/treated",
            }
        ],
        "filter": {"method": "total_count", "operator": ">", "threshold": 10},
        "parameters": {"alpha": 0.05, "lfc_threshold": 1, "min_replicates": 2, "non_integer_counts": "round"},
    }
    (case_root / "analysis_spec.json").write_text(
        json.dumps(spec, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(case_root: Path, variant: str) -> None:
    tracked = [case_root / "reference/transcriptome.fa", case_root / "metadata.csv", case_root / "expected_counts.tsv"]
    document = {"variant": variant, "files": {str(path.relative_to(case_root)): sha256(path) for path in tracked}}
    (case_root / "fixture_manifest.json").write_text(
        json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
    )


def change_contrast(case_root: Path) -> None:
    path = case_root / "analysis_spec.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    contrast = document["contrasts"][0]
    contrast.update(
        {
            "id": "condition__treated_vs_control",
            "numerator": "treated",
            "denominator": "control",
            "description": "treated versus control",
            "direction": "treated/control",
        }
    )
    path.write_text(
        json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--case-root", required=True, type=Path)
    parser.add_argument("--conda-base", required=True, type=Path)
    parser.add_argument(
        "--variant", choices=("baseline", "fastq", "transcriptome", "contrast"), default="baseline"
    )
    args = parser.parse_args()

    counts_path = args.repo_root / "tests/fixtures/native_de/counts_matrix.tsv"
    genes, counts = read_counts(counts_path, increment=args.variant in {"fastq", "transcriptome"})
    args.case_root.mkdir(parents=True, exist_ok=True)

    if args.variant in {"baseline", "fastq"}:
        write_fastqs(args.case_root / "inputs", genes, counts)
        write_tables(args.case_root, genes, counts)
    if args.variant in {"baseline", "transcriptome"}:
        write_reference(args.case_root / "reference", genes, mutate=args.variant == "transcriptome")
    if args.variant == "baseline":
        write_configuration(args.repo_root, args.case_root, args.conda_base)
    if args.variant == "contrast":
        change_contrast(args.case_root)
    write_manifest(args.case_root, args.variant)


if __name__ == "__main__":
    main()
