# 060-deg-analysis

Generate a DEG analysis plan and submit DESeq2 jobs as a Slurm array.

## Before You Run

Confirm these exist:

```text
050-quantification/counts_matrix.tsv
050-quantification/quant_samples.tsv
```

Optional corrected inputs from step 055:

```text
055-batch-correction/all_projects/counts_batch_corrected.tsv
055-batch-correction/all_projects/batch_correction_samples.tsv
```

Set defaults in `config/pipeline_config.sh`:

```bash
export DEG_TEST_VARIABLES="condition,stage,sex,tissue"
export DEG_DESIGN_COVARIATES="dataset"
export DEG_CONCURRENCY=2
```

## Run

Normally `rnaseq_pipeline.sh` submits this step. To run manually:

```bash
bash scripts/060-deg-analysis/run_deg_analysis_slurm.sh --include-all
```

Without Slurm:

```bash
bash scripts/060-deg-analysis/run_deg_analysis_slurm.sh --include-all --local
```

Include corrected matrices:

```bash
bash scripts/060-deg-analysis/run_deg_analysis_slurm.sh \
  --include-all \
  --include-corrected
```

Preview only:

```bash
bash scripts/060-deg-analysis/run_deg_analysis_slurm.sh \
  --include-all \
  --include-corrected \
  --sbatch-dry-run
bash scripts/060-deg-analysis/run_deg_analysis_slurm.sh \
  --include-all \
  --include-corrected \
  --local \
  --sbatch-dry-run
```

## Outputs

- `060-deg-analysis/work/deg_plan.csv`
- `060-deg-analysis/<PROJECT>/raw/`
- `060-deg-analysis/<PROJECT>/batch_corrected/`
- `060-deg-analysis/all_projects/raw/`
- `060-deg-analysis/all_projects/batch_corrected/`

Main result files:

- `deg_summary.tsv`
- `DEGs_all_results.tsv`
- `DEGs_significant.tsv`
- `contrasts/DEG_<contrast>.tsv`
- `normalized_counts_<variable>.tsv`
- `plots/`

If a design is rank-deficient, the affected contrast is skipped and recorded in
`deg_summary.tsv`.
