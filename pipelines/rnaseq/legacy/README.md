# RNA-seq Pipeline

This repository contains a modular RNA-seq pipeline designed for reproducible
analysis on Slurm/HPC systems or on a local workstation. It is organism
agnostic: genome FASTA, transcript FASTA, GFF3/GTF annotation, project
accessions, metadata parser YAML files, scratch paths, Conda environments, and
analysis defaults are configured by the user.

The pipeline starts from ENA/SRA FASTQ links and produces parsed metadata,
FastQC/MultiQC reports, trimmed and merged FASTQs, Salmon or STAR gene-count
quantification, gene-level count and TPM/CPM matrices, optional batch-corrected
matrices, DESeq2 outputs, and an optional candidate gene report.

## Directory Layout

- `config/`: central configuration, example config, and metadata template
- `scripts/`: active executables for every pipeline step, validation utilities, and shared functions
- `slurm/`: Slurm notes
- `envs/`: Conda environment templates
- `examples/`: minimal example skeleton
- `000-logs/`: high-level Slurm logs created by the orchestrator
- `010-reference/`: reference FASTA/GFF/GTF files and Salmon/STAR indexes
- `020-data-download/`: FASTQ download configs and link files
- `025-parse/`: ENA metadata download, project YAML parsers, and merged metadata
- `030-qc-fastq/`: FastQC, trimming, merged FASTQs, and MultiQC
- `040-alignment/`: Salmon or STAR plans and quantification outputs
- `050-quantification/`: imported count and expression matrices
- `055-batch-correction/`: optional batch assessment/correction
- `060-deg-analysis/`: DESeq2 plans, contrasts, plots, and summaries
- `090-search-gene/`: optional candidate gene/group report

## Requirements

Create the required Conda environments from `envs/` or provide equivalent tools
on `PATH`.

Core tools for both modes:

- Python 3 with pandas
- R with tximport, DESeq2, rtracklayer, ggplot2, and related packages
- FastQC and MultiQC
- Trim Galore
- Salmon for the default transcript quantification mode
- STAR and gffread for STAR genome-alignment quantification or STAR indexes
- wget

Additional tools for Slurm mode:

- `sbatch` and `squeue`

## Configure

For most users, edit only `config/user_settings.sh`:

```bash
cp config/user_settings_template.sh config/user_settings.sh
nano config/user_settings.sh
```

Required user-specific inputs:

- `ORGANISM_NAME`
- `PIPELINE_PROJECTS`
- `SCRATCH_ROOT`
- `CONDA_BASE`
- reference URLs or local reference file paths

Choose where jobs run:

```bash
export PIPELINE_EXECUTOR="slurm"   # default
export PIPELINE_EXECUTOR="local"   # no sbatch/squeue
```

Choose the quantification method:

```bash
export QUANT_METHOD="salmon"  # default; outputs TPM
export QUANT_METHOD="star"    # genome alignment; outputs STAR counts and CPM
```

Use Salmon when you have a transcript FASTA. Use STAR when you want genome
alignment, sorted BAM files, STAR `ReadsPerGene.out.tab`, and genomic
coordinates in the final report from the GFF/GTF annotation.

`config/pipeline_config.sh` contains advanced defaults, directory variables,
and helper functions. Most users should leave it alone after creating
`config/user_settings.sh`.

Run commands from the repository root. The numbered directories are for inputs,
logs, work files, and results. Active scripts are centralized under `scripts/`.

For each project, create:

```text
020-data-download/datasets/<PROJECT>/config.yaml
025-parse/020-metadata_parsers/<PROJECT>/configs/<PROJECT>.yaml
```

## Metadata

The final parsed metadata must contain:

```text
dataset sample_id run_accession
```

Recommended columns for downstream analyses:

```text
condition stage tissue sex batch replicate
```

Use `config/metadata_template.tsv` as a minimal contract reference. Project
YAML files in `025-parse/020-metadata_parsers/<PROJECT>/configs/` are
responsible for creating these columns.

Validate an existing metadata table:

```bash
python scripts/validate_metadata.py \
  --metadata 025-parse/030-metadata_final/AllProjects_metadata_new.csv
```

## Run

Complete run with Slurm dependencies:

```bash
bash rnaseq_pipeline.sh --all
```

Complete run locally, without Slurm:

```bash
bash rnaseq_pipeline.sh --all --local
```

Inspect the job graph without submitting:

```bash
bash rnaseq_pipeline.sh --all --dry-run
bash rnaseq_pipeline.sh --all --local --dry-run
```

Run one or more coarse steps:

```bash
bash rnaseq_pipeline.sh --step reference
bash rnaseq_pipeline.sh --step metadata --step qc
bash rnaseq_pipeline.sh --step salmon --step tximport --step deg
bash rnaseq_pipeline.sh --step star --step tximport --step report
```

Supported steps:

```text
reference download metadata qc salmon star tximport batch deg report
```

`main.sh` is kept as a compatibility wrapper around `rnaseq_pipeline.sh`; new
runs should use `rnaseq_pipeline.sh` directly.

## Workflow

Full execution order:

```text
reference
download + metadata -> qc
qc + reference -> salmon
qc + reference -> star (when QUANT_METHOD=star)
salmon/star -> quantification import
quantification import -> batch (optional)
quantification import or batch -> deg
deg -> report (optional)
```

In Slurm mode, sample/project-level steps are submitted independently where
possible and downstream steps use `--dependency=afterok`. In local mode, the
same steps run in dependency order on the current machine; Slurm arrays are
simulated sequentially with `SLURM_ARRAY_TASK_ID`.

## Outputs

Key files and directories:

- `010-reference/salmon_index/`
- `${SCRATCH_ROOT}/<PROJECT>/fastq_ftp/`
- `025-parse/030-metadata_final/AllProjects_metadata_new.csv`
- `${SCRATCH_ROOT}/<PROJECT>/multiqc_030/`
- `040-alignment/quants/<PROJECT>/<sample_id>/quant.sf`
- `040-alignment/star_quant/<PROJECT>/<sample_id>/ReadsPerGene.out.tab`
- `040-alignment/star_quant/<PROJECT>/<sample_id>/Aligned.sortedByCoord.out.bam`
- `050-quantification/counts_matrix.tsv`
- `050-quantification/tpm_matrix.tsv`
- `050-quantification/star_cpm_matrix.tsv`
- `050-quantification/quant_samples.tsv`
- `055-batch-correction/all_projects/counts_batch_corrected.tsv`
- `060-deg-analysis/all_projects/raw/DEGs_all_results.tsv`
- `090-search-gene/results/gene_set_report.html`

## Recovering Failed Jobs

1. Inspect `000-logs/` and the step-specific `logs/` directory.
2. Fix the cause, such as a missing FASTQ, bad YAML parser, missing reference,
   missing Conda environment, or insufficient Slurm memory/time.
3. Rerun the failed coarse step:

```bash
bash rnaseq_pipeline.sh --step <step>
```

## Notes

- Use Slurm mode on the remote HPC server for production-sized datasets.
- Use local mode for small datasets, smoke tests, teaching, and machines
  without `sbatch`.
- Large generated data should not be committed.
- Bundled project-specific folders are examples or legacy inputs. Only
  `PIPELINE_PROJECTS` controls what is submitted.

