# 040-alignment

Create a sample-level plan from the step 030 QC plan and submit one job per
biological sample.

This step has two modes:

- `QUANT_METHOD=salmon`: runs Salmon against the transcriptome and writes
  `quant.sf`.
- `QUANT_METHOD=star`: runs STAR against the annotated genome index, writes
  sorted BAM files, and writes `ReadsPerGene.out.tab` for gene counts.

## Before You Run

Confirm these exist:

```text
030-qc-fastq/work/<PROJECT>_qc_plan.csv
010-reference/salmon_index/       # Salmon mode
010-reference/star_index_gtf/      # STAR mode
```

Relevant defaults in `config/pipeline_config.sh`:

- `SALMON_INDEX_DIR`
- `QUANT_DIR`
- `SALMON_CONCURRENCY`
- `STAR_QUANT_INDEX_DIR`
- `STAR_QUANT_DIR`
- `STAR_QUANT_CONCURRENCY`
- `STAR_GENECOUNT_COLUMN`
- `STAR_READ_FILES_COMMAND`
- `STAR_EXTRA_ARGS`

## Run

Normally `rnaseq_pipeline.sh` submits this step and chooses the script from
`QUANT_METHOD`.

Run Salmon manually:

```bash
bash scripts/040-alignment/run_alignment_project.sh \
  PRJXXXX \
  "$PWD/030-qc-fastq/work/PRJXXXX_qc_plan.csv"
```

Run STAR manually:

```bash
bash scripts/040-alignment/run_star_quant_project.sh \
  PRJXXXX \
  "$PWD/030-qc-fastq/work/PRJXXXX_qc_plan.csv"
```

Without Slurm, add `--local`:

```bash
bash scripts/040-alignment/run_alignment_project.sh \
  PRJXXXX \
  "$PWD/030-qc-fastq/work/PRJXXXX_qc_plan.csv" \
  --local

bash scripts/040-alignment/run_star_quant_project.sh \
  PRJXXXX \
  "$PWD/030-qc-fastq/work/PRJXXXX_qc_plan.csv" \
  --local
```

Preview only:

```bash
bash scripts/040-alignment/run_alignment_project.sh \
  PRJXXXX \
  "$PWD/030-qc-fastq/work/PRJXXXX_qc_plan.csv" \
  --dry-run

bash scripts/040-alignment/run_star_quant_project.sh \
  PRJXXXX \
  "$PWD/030-qc-fastq/work/PRJXXXX_qc_plan.csv" \
  --dry-run
```

## Outputs

- `040-alignment/work/<PROJECT>_salmon_plan.csv`
- `${QUANT_DIR}/<PROJECT>/<sample_id>/quant.sf`
- `040-alignment/work/<PROJECT>_star_plan.csv`
- `${STAR_QUANT_DIR}/<PROJECT>/<sample_id>/ReadsPerGene.out.tab`
- `${STAR_QUANT_DIR}/<PROJECT>/<sample_id>/Aligned.sortedByCoord.out.bam`
- `${STAR_QUANT_DIR}/<PROJECT>/<sample_id>/Log.final.out`

The old `salmon_quant.sh` lives under `040-alignment/legacy/` and is ignored.
Use scripts under `scripts/040-alignment/` for new manual runs.
