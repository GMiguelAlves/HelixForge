# 030-qc-fastq

Build a metadata-driven QC plan and submit Slurm arrays for raw FastQC,
trimming, run-level FastQC, per-sample FASTQ merge, merged FastQC, and MultiQC.

## Before You Run

Confirm these exist:

```text
025-parse/030-metadata_final/AllProjects_metadata_new.csv
${SCRATCH_ROOT}/<PROJECT>/fastq_ftp
```

The metadata must include `dataset`, `sample_id`, and `run_accession`.

Relevant defaults in `config/pipeline_config.sh`:

- `SCRATCH_ROOT`
- `QC_RUN_CONCURRENCY`
- `QC_SAMPLE_CONCURRENCY`
- `TRIM_QUALITY`
- `TRIM_LENGTH`

## Run

Normally `rnaseq_pipeline.sh` submits this step. To run one project manually:

```bash
bash scripts/030-qc-fastq/run_qc_project.sh PRJXXXX
```

Without Slurm:

```bash
bash scripts/030-qc-fastq/run_qc_project.sh PRJXXXX --local
```

Preview only:

```bash
bash scripts/030-qc-fastq/run_qc_project.sh PRJXXXX --dry-run
bash scripts/030-qc-fastq/run_qc_project.sh PRJXXXX --local --dry-run
```

## Outputs

- `030-qc-fastq/work/<PROJECT>_qc_plan.csv`
- `${SCRATCH_ROOT}/<PROJECT>/fastqc_raw/`
- `${SCRATCH_ROOT}/<PROJECT>/trimmed_runs/`
- `${SCRATCH_ROOT}/<PROJECT>/trimmed_merged/`
- `${SCRATCH_ROOT}/<PROJECT>/fastqc_trimmed_runs/`
- `${SCRATCH_ROOT}/<PROJECT>/fastqc_merged/`
- `${SCRATCH_ROOT}/<PROJECT>/multiqc_030/`

The old single-purpose scripts live under `030-qc-fastq/legacy/` and are
ignored. Use `scripts/030-qc-fastq/run_qc_project.sh` for new manual runs.
