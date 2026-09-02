#!/usr/bin/env python3
"""Prepare frozen RNA-seq and mark-specific ChIP-seq inputs for GSE133183."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shlex
import tempfile
from pathlib import Path


RNA_SAMPLES = {"GSM4817464", "GSM4817465", "GSM4817466", "GSM4817467"}
MARKS = ("H3K27me3", "H3K27ac")
CONDITIONS = ("DMSO", "GSK343")
GENOME_ID = "GRCh38.p14_GENCODE_50"


def rows(path: Path, delimiter: str = "\t") -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def quoted(value: object) -> str:
    return shlex.quote(str(value))


def write_table(path: Path, records: list[dict[str, str]], delimiter: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]), delimiter=delimiter, lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def artifact(path: Path, declared_path: Path | None = None) -> dict[str, object]:
    return {
        "path": str(declared_path or path),
        "sha256": sha256(path),
        "size_bytes": path.stat().st_size,
    }


def prepare_rnaseq(
    root: Path,
    declared_root: Path,
    repo: Path,
    metadata: list[dict[str, str]],
    fastqs: dict[tuple[str, str], Path],
    reference: dict[str, Path],
    reference_manifest: Path,
    inventory: Path,
    conda_base: Path,
) -> None:
    root.mkdir()
    selected = [row for row in metadata if row["geo_sample"] in RNA_SAMPLES]
    if len(selected) != 4:
        raise ValueError("RNA-seq arm must contain exactly four frozen samples")
    observed = {(row["condition"], row["biological_replicate"]) for row in selected}
    if observed != {(condition, replicate) for condition in CONDITIONS for replicate in ("1", "2")}:
        raise ValueError(f"invalid RNA-seq balance: {sorted(observed)}")

    sample_rows = []
    for row in sorted(selected, key=lambda item: item["geo_sample"]):
        sample = row["geo_sample"]
        sample_rows.append({
            "dataset": "gse133183_k562",
            "sample_id": sample,
            "file_prefix": sample,
            "run_accession": row["run_accession"],
            "condition": row["condition"],
            "replicate": row["biological_replicate"],
            "batch": "not_applicable",
            "stage": "K562",
            "tissue": "K562",
            "sex": "unknown",
            "fastq_1": str(fastqs[(sample, "1")]),
            "fastq_2": str(fastqs[(sample, "2")]),
        })
    metadata_file = root / "metadata.csv"
    write_table(metadata_file, sample_rows, ",")

    pipeline_root = declared_root / "pipeline"
    settings = root / "user_settings.sh"
    settings.write_text("\n".join([
        "#!/usr/bin/env bash",
        "export PIPELINE_NAME='helixforge_rnaseq_gse133183_integrative_input'",
        f"export ORGANISM_NAME='{GENOME_ID}'",
        "export PIPELINE_PROJECTS='gse133183_k562'",
        f"export SCRATCH_ROOT={quoted(declared_root / 'scratch')}",
        f"export CONDA_BASE={quoted(conda_base)}",
        f"export REF_GENOME_FA={quoted(reference['genome_fasta'])}",
        f"export REF_TRANSCRIPTS_FA={quoted(reference['transcriptome'])}",
        f"export REF_GTF={quoted(reference['annotation_gtf'])}",
        "export REF_GFF3=''",
        f"export METADATA_FINAL={quoted(declared_root / 'metadata.csv')}",
        f"export METADATA_FINAL_NEW={quoted(declared_root / 'metadata.csv')}",
        f"export SCRIPTS_DIR={quoted(repo / 'pipelines/rnaseq')}",
        f"export SALMON_INDEX_DIR={quoted(pipeline_root / '010-reference/salmon_index')}",
        f"export QUANT_DIR={quoted(pipeline_root / '040-alignment/quants')}",
        "export QUANT_METHOD='salmon'",
        "export PIPELINE_EXECUTOR='local'",
        "export THREADS=4",
        "export TRIM_QUALITY=20",
        "export TRIM_LENGTH=20",
        "export SALMON_KMER_SIZE=31",
        "export RUN_SALMON_INDEX=1",
        "export RUN_STAR_INDEX=0",
        "export RUN_STAR_GTF_INDEX=0",
        "export RUN_BATCH_CORRECTION=0",
        "export RUN_GENE_REPORT=1",
        "export BATCH_COLUMN='batch'",
        "export DEG_DESIGN_COVARIATES=''",
        "export RNA_TOOLS_ENV='rna-tools'",
        "export PYTHON_ENV='python-list'",
        "export R_ANALYSIS_ENV='r-analysis'",
        "",
    ]), encoding="utf-8", newline="\n")
    pipeline_config = root / "pipeline_config.sh"
    pipeline_config.write_text("\n".join([
        "#!/usr/bin/env bash",
        f"export PROJECT_DIR={quoted(pipeline_root)}",
        f"export USER_SETTINGS_FILE={quoted(declared_root / 'user_settings.sh')}",
        f"source {quoted(repo / 'pipelines/rnaseq/config/pipeline_config.sh')}",
        "",
    ]), encoding="utf-8", newline="\n")
    analysis_spec = {
        "schema_version": "1.0",
        "analysis_id": "gse133183_k562",
        "scope": "all_projects",
        "correction": "raw",
        "provider": "deseq2",
        "test": "wald",
        "target_dir": str(pipeline_root / "060-deg-analysis/gsk343_vs_dmso"),
        "design": {"variable": "condition", "covariates": [], "formula": "~ condition"},
        "contrasts": [{
            "id": "condition__GSK343_vs_DMSO",
            "factor": "condition",
            "numerator": "GSK343",
            "denominator": "DMSO",
            "description": "GSK343 versus DMSO",
            "direction": "GSK343/DMSO",
        }],
        "filter": {"method": "total_count", "operator": ">", "threshold": 10},
        "parameters": {"alpha": 0.05, "lfc_threshold": 1.0, "min_replicates": 2, "non_integer_counts": "round"},
    }
    analysis_file = root / "analysis_spec.json"
    write_json(analysis_file, analysis_spec)
    genes = root / "report_genes.txt"
    genes.write_text("FGF18\nUBTD2\nFBXW11\nIGF2\nHBB\nHBZ\nHBE1\n", encoding="utf-8", newline="\n")
    resolved = {
        "workflow": "rnaseq", "run_mode": "full", "analysis_mode": "quantification",
        "quantification_provider": "salmon", "alignment_provider": "disabled",
        "import_policy": "production_v1", "library_protocol": "full_length",
        "countsFromAbundance": "lengthScaledTPM", "design": "~ condition",
        "contrast": "condition__GSK343_vs_DMSO", "alpha": 0.05, "lfc_threshold": 1.0,
        "trim_quality": 20, "trim_length": 20, "salmon_kmer_size": 31,
    }
    resolved_file = root / "resolved_parameters.json"
    write_json(resolved_file, resolved)
    write_json(root / "input_manifest.json", {
        "schema_version": "1.0", "type": "gse133183_rnaseq_input", "status": "READY",
        "role": "INPUT_GENERATION_FOR_INTEGRATIVE_BENCHMARK", "samples": [row["sample_id"] for row in sample_rows],
        "artifacts": {
            "metadata": artifact(metadata_file, declared_root / metadata_file.name),
            "pipeline_config": artifact(pipeline_config, declared_root / pipeline_config.name),
            "user_settings": artifact(settings, declared_root / settings.name),
            "analysis_spec": artifact(analysis_file, declared_root / analysis_file.name),
            "resolved_parameters": artifact(resolved_file, declared_root / resolved_file.name),
            "reference_manifest": artifact(reference_manifest),
            "fastq_inventory": artifact(inventory),
        },
    })


def prepare_chipseq(
    root: Path,
    declared_root: Path,
    mark: str,
    metadata: list[dict[str, str]],
    fastqs: dict[tuple[str, str], Path],
    reference: dict[str, Path],
    reference_manifest: Path,
    inventory: Path,
) -> None:
    root.mkdir()
    selected = [row for row in metadata if row["mark"] in {mark, "IgG"} and row["assay"] == "ChIP-seq"]
    marks = [row for row in selected if row["mark"] == mark]
    controls = [row for row in selected if row["mark"] == "IgG"]
    if len(marks) != 4 or len(controls) != 4:
        raise ValueError(f"{mark} arm requires four mark and four IgG samples")
    by_geo = {row["geo_sample"]: row for row in selected}
    sample_rows = []
    for row in sorted(selected, key=lambda item: (item["mark"] == "IgG", item["condition"], item["biological_replicate"])):
        sample = row["geo_sample"]
        is_control = row["mark"] == "IgG"
        control_geo = row["control_geo_sample"]
        if not is_control and control_geo not in by_geo:
            raise ValueError(f"missing matched IgG for {sample}: {control_geo}")
        sample_rows.append({
            "sample_id": sample, "run_accession": row["run_accession"],
            "fastq_1": fastqs[(sample, "1")].name, "fastq_2": fastqs[(sample, "2")].name,
            "layout": "paired", "assay": "input" if is_control else "ChIP-seq",
            "condition": row["condition"], "biological_replicate": row["biological_replicate"],
            "technical_replicate": "1", "antibody": "" if is_control else mark,
            "target": "IgG" if is_control else mark,
            "control_id": "" if is_control else by_geo[control_geo]["run_accession"],
            "is_control": str(is_control).lower(), "batch": "GSE133183", "lane": "",
            "dataset": f"gse133183_{mark.lower()}", "organism": "Homo_sapiens", "genome_id": GENOME_ID,
        })
    metadata_file = root / "metadata.tsv"
    write_table(metadata_file, sample_rows, "\t")
    results = declared_root / "results"
    peak_type = "broad" if mark == "H3K27me3" else "narrow"
    values = {
        "FASTQ_DIR": fastqs[(selected[0]["geo_sample"], "1")].parent,
        "METADATA_FILE": declared_root / "metadata.tsv", "GENOME_FASTA": reference["genome_fasta"],
        "ANNOTATION_FILE": reference["annotation_gtf"], "BLACKLIST_BED": reference["blacklist"],
        "OUTPUT_DIR": results, "WORK_ROOT": declared_root / "work", "REF_DIR": results / "010-reference",
        "QC_DIR": results / "030-qc-fastq", "ALIGN_DIR": results / "050-alignment",
        "FILTER_DIR": results / "060-filtering", "PEAK_DIR": results / "080-peak-calling",
        "BOWTIE2_INDEX_PREFIX": results / "010-reference/bowtie2/genome",
        "ORGANISM_NAME": "Homo_sapiens", "ALIGNER": "bowtie2", "BOWTIE2_BUILD_OPTS": "",
        "BOWTIE2_OPTS": "--very-sensitive", "READ_LAYOUT": "metadata", "ALLOW_MISSING_CONTROLS": "false",
        "MIN_MAPQ": "30", "REMOVE_SECONDARY_SUPPLEMENTARY": "true", "REMOVE_DUPLICATES": "false",
        "DEDUP_TOOL": "samtools", "PEAK_CALLER": "macs3", "PEAK_TYPE": peak_type,
        "MACS_QVALUE": "0.01", "MACS_PVALUE": "", "MACS_GENOME_SIZE": "2913022398",
        "MACS_EXTRA_OPTS": "", "THREADS": "8", "MEMORY": "24G", "SLURM_TIME": "12:00:00",
    }
    config = root / "pipeline_config.sh"
    config.write_text("#!/usr/bin/env bash\n" + "".join(f"export {key}={quoted(value)}\n" for key, value in values.items()), encoding="utf-8", newline="\n")
    spec = {
        "schema_version": "1.0", "provider": "deseq2", "test": "wald",
        "peak_universe": {"method": "union"},
        "counting": {"provider": "featurecounts", "unit": "fragments", "strandedness": 0,
            "min_mapq": 30, "overlap_policy": "any", "allow_multi_overlap": False,
            "allow_multimapping": False, "fractional": False, "require_both_ends_mapped": True,
            "exclude_chimeric": True},
        "design": {"formula": "~ condition", "variable": "condition", "covariates": []},
        "contrasts": [{"id": "GSK343_vs_DMSO", "factor": "condition", "numerator": "GSK343",
            "denominator": "DMSO", "description": f"{mark}: GSK343 versus DMSO"}],
        "filter": {"method": "minimum_count", "min_count": 10, "min_samples": 2},
        "normalization": "deseq2_median_of_ratios",
        "parameters": {"alpha": 0.05, "lfc_threshold": 1.0, "min_replicates": 2},
    }
    spec_file = root / "db_spec.json"
    write_json(spec_file, spec)
    resolved_file = root / "resolved_parameters.json"
    write_json(resolved_file, {
        "workflow": "chipseq", "run_mode": "full", "target": mark, "peak_type": peak_type,
        "peak_caller": "macs3", "peak_q_value": 0.01, "peak_format": "BAMPE",
        "consensus_method": "union", "min_replicates": 2, "min_mapq": 30,
        "remove_duplicates": False, "design": "~ condition", "contrast": "GSK343_vs_DMSO",
    })
    write_json(root / "input_manifest.json", {
        "schema_version": "1.0", "type": f"gse133183_chipseq_{mark.lower()}_input", "status": "READY",
        "role": "INPUT_GENERATION_FOR_INTEGRATIVE_BENCHMARK", "target": mark,
        "samples": [row["sample_id"] for row in sample_rows],
        "artifacts": {
            "metadata": artifact(metadata_file, declared_root / metadata_file.name),
            "pipeline_config": artifact(config, declared_root / config.name),
            "db_spec": artifact(spec_file, declared_root / spec_file.name),
            "resolved_parameters": artifact(resolved_file, declared_root / resolved_file.name),
            "reference_manifest": artifact(reference_manifest),
            "fastq_inventory": artifact(inventory),
        },
    })


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--fastq-inventory", required=True, type=Path)
    parser.add_argument("--reference-manifest", required=True, type=Path)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--conda-base", required=True, type=Path)
    args = parser.parse_args()
    if not os.environ.get("SLURM_JOB_ID"):
        raise SystemExit("upstream input preparation must execute inside a Slurm job")
    if args.output_root.exists():
        raise FileExistsError(f"output root already exists: {args.output_root}")

    metadata = rows(args.metadata)
    inventory_rows = rows(args.fastq_inventory)
    reference_data = json.loads(args.reference_manifest.read_text(encoding="utf-8"))
    if reference_data.get("status") != "REFERENCE_READY":
        raise ValueError("reference manifest is not REFERENCE_READY")
    reference = {entry["role"]: Path(entry["path"]) for entry in reference_data["artifacts"]}
    for role in ("genome_fasta", "annotation_gtf", "transcriptome", "blacklist"):
        if role not in reference or not reference[role].is_file():
            raise FileNotFoundError(f"missing reference role: {role}")
    fastqs = {(row["geo_sample"], row["mate"]): Path(row["path"]) for row in inventory_rows}
    if len(fastqs) != 32 or any(not path.is_file() for path in fastqs.values()):
        raise ValueError("validated FASTQ inventory must resolve to 32 files")

    args.output_root.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".gse133183-cases.", dir=args.output_root.parent))
    try:
        prepare_rnaseq(stage / "rnaseq", args.output_root / "rnaseq", args.repo.resolve(), metadata, fastqs, reference,
                       args.reference_manifest.resolve(), args.fastq_inventory.resolve(), args.conda_base.resolve())
        prepare_chipseq(stage / "chipseq_h3k27me3", args.output_root / "chipseq_h3k27me3", "H3K27me3", metadata, fastqs, reference,
                        args.reference_manifest.resolve(), args.fastq_inventory.resolve())
        prepare_chipseq(stage / "chipseq_h3k27ac", args.output_root / "chipseq_h3k27ac", "H3K27ac", metadata, fastqs, reference,
                        args.reference_manifest.resolve(), args.fastq_inventory.resolve())
        write_json(stage / "cases_manifest.json", {
            "schema_version": "1.0", "type": "gse133183_upstream_cases", "status": "READY",
            "role": "INPUT_GENERATION_FOR_INTEGRATIVE_BENCHMARK",
            "cases": ["rnaseq", "chipseq_h3k27me3", "chipseq_h3k27ac"],
            "slurm_job_id": os.environ["SLURM_JOB_ID"],
        })
        stage.replace(args.output_root)
    except Exception:
        import shutil
        shutil.rmtree(stage, ignore_errors=True)
        raise
    print(json.dumps({"status": "READY", "cases": 3, "rna_samples": 4, "chip_samples_per_mark": 8}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
