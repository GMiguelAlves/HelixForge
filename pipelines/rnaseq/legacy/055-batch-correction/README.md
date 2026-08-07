# 055-batch-correction

Optional step to assess and correct batch effects.

## Before You Run

Confirm these exist:

```text
050-quantification/counts_matrix.tsv
050-quantification/quant_samples.tsv
```

Set defaults in `config/pipeline_config.sh`:

```bash
export BATCH_COLUMN="dataset"
export BATCH_COVARIATES="condition,stage,tissue,sex"
```

Use covariates only when they are present in the sample table and biologically
important to preserve.

## Assess Batch

```bash
bash scripts/055-batch-correction/run_batch_assessment_slurm.sh --all
```

Without Slurm:

```bash
bash scripts/055-batch-correction/run_batch_assessment_slurm.sh --all --local
```

Override defaults for one run:

```bash
bash scripts/055-batch-correction/run_batch_assessment_slurm.sh \
  --all \
  --batch-column sequencing_batch \
  --covariates condition,stage
```

## Correct Batch

```bash
bash scripts/055-batch-correction/run_batch_correction_slurm.sh \
  --all \
  --skip-if-single-batch
```

Without Slurm:

```bash
bash scripts/055-batch-correction/run_batch_correction_slurm.sh \
  --all \
  --skip-if-single-batch \
  --local
```

## Outputs

- `055-batch-correction/all_projects/assessment/`
- `055-batch-correction/all_projects/counts_batch_corrected.tsv`
- `055-batch-correction/all_projects/batch_correction_samples.tsv`

Check the assessment before using corrected matrices in DEG.
