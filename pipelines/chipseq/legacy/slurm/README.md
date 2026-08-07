# Slurm And Local Execution Notes

The ChIP-seq pipeline follows the same execution style as the RNA-seq pipeline.
It can be launched from a Slurm login node or in local mode for small tests.
Slurm is recommended for production-sized datasets.

## Standard Run

```bash
bash chipseq_pipeline.sh --all --dry-run
bash chipseq_pipeline.sh --all
```

## Local Run

```bash
bash chipseq_pipeline.sh --all --local --dry-run
bash chipseq_pipeline.sh --all --local
```

Local mode does not call `sbatch`. Jobs are executed sequentially in the current
session, with `SLURM_CPUS_PER_TASK` simulated from `LOCAL_CPUS_PER_TASK`.

## Logs

The orchestrator creates `000-logs/<step>/` directories and submits jobs with
`sbatch --chdir=<step-dir>`. Slurm stdout/stderr are written to:

```text
000-logs/<step>/<sample-or-target>.out
000-logs/<step>/<sample-or-target>.err
```

For sample-level steps, the default Slurm mode is one job array per step:

```text
chipseq_align_array  --array=1-N%ALIGN_CONCURRENCY
chipseq_filter_array --array=1-N%FILTER_CONCURRENCY
chipseq_peaks_array  --array=1-N%PEAKS_CONCURRENCY
```

Each array task redirects its real output to the sample-specific log files above.
The scheduler may also create lightweight `array_<job>_<task>.out/.err` files.

## Dependencies

In the full workflow, downstream steps use `--dependency=afterok`. When arrays
are enabled, downstream steps depend on the whole upstream array, so alignment
waits for trimming, filtering waits for alignment, and peak calling waits for
all filtered IP/control BAMs to be available.

## Cluster-Specific Settings

Keep these in `config/user_settings.sh`:

- `PIPELINE_EXECUTOR=slurm`
- `THREADS`
- `MEMORY`
- `SLURM_TIME`
- `SLURM_PARTITION`
- `SLURM_ACCOUNT`
- `SLURM_QOS`
- `SLURM_SAMPLE_SUBMISSION_MODE=array`
- `CONDA_BASE`
- `PIPELINE_COMPRESS_RESULTS`
- `PIPELINE_STORAGE_MODE`

Only edit step scripts when the cluster requires hard-coded module commands or
site-specific behavior that cannot be expressed as variables.
