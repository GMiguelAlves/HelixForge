# Slurm And Local Execution Notes

The RNA-seq pipeline can be launched from a Slurm login node or from a local
machine. Slurm is still recommended for production-sized datasets.

## Standard Run

```bash
bash rnaseq_pipeline.sh --all --dry-run
bash rnaseq_pipeline.sh --all
```

## Local Run

```bash
bash rnaseq_pipeline.sh --all --local --dry-run
bash rnaseq_pipeline.sh --all --local
```

Local mode does not call `sbatch` or `squeue`. Steps that normally use Slurm
arrays run sequentially on the current machine by simulating
`SLURM_ARRAY_TASK_ID`.

## Logs

The orchestrator creates the step-specific `logs/` directories before
submission and uses `sbatch --chdir=<step-dir>` so Slurm output lands beside
the corresponding step results.

## Dependencies

In the full workflow, downstream steps use `--dependency=afterok`.
Coordinator jobs for QC, Salmon, and DEG wait for their child array jobs by
default through `PIPELINE_WAIT_FOR_CHILD_JOBS=1`.

## Cluster-Specific Settings

If your cluster requires account, partition, QoS, or module loading, add those
settings to `config/user_settings.sh` when they can be expressed as variables.
Only edit step scripts when the cluster requires hard-coded `#SBATCH` lines or
module commands.
