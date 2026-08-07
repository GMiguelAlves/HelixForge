# Slurm execution

`integrative_pipeline.sh` uses `sbatch --dependency=afterok` in Slurm mode.
Runtime values are configured in `config/pipeline_config.sh`:

- `THREADS`
- `MEMORY`
- `SLURM_TIME`
- `SLURM_ACCOUNT`
- `ENV_BACKEND`
- `CONDA_ENV`
- `CONTAINER_IMAGE`

Example:

```bash
bash integrative_pipeline.sh --all --mode slurm
```

Use `--dry-run` to inspect submissions without creating jobs.
