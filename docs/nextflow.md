# Running with Nextflow

## Available workflows

Select one workflow with `--workflow rnaseq`, `chipseq`, `integrative`, or
`all`. The default is `all`.

```bash
nextflow run . -profile local --workflow rnaseq
nextflow run . -profile slurm --workflow chipseq -c conf/my_cluster.config
nextflow run . -profile local --workflow integrative
nextflow run . -profile slurm --workflow all -c conf/my_cluster.config
```

The existing configuration remains authoritative:

```text
pipelines/rnaseq/legacy/config/pipeline_config.sh
pipelines/chipseq/legacy/config/pipeline_config.sh
pipelines/integrative/legacy/config/pipeline_config.sh
```

Override a config without changing workflow code:

```bash
nextflow run . --workflow rnaseq \
  --rnaseq_config /shared/project/config/pipeline_config.sh
```

## Profiles

- `local`: Nextflow local executor.
- `slurm`: one Nextflow task per compatibility step; legacy scripts run locally
  inside the allocation and never submit child jobs.
- `docker`: preparation profile; a container image must still be assigned.
- `singularity`: preparation profile.
- `apptainer`: preparation profile.
- `conda`: preparation profile; legacy scripts still activate their own envs.
- `test`: reduced local settings for stub tests.

## Dry-run modes

`-stub-run` compiles the complete graph and runs only module stub blocks. It is
the safe validation mode for this repository.

`--legacy_dry_run true` launches the wrappers but adds `--dry-run` to the
existing orchestrators. Their normal config validation still applies.

On systems where Python 3 is available only as `python3` (including the tested
WSL installation), preserve the legacy configuration and override the command
for the run:

```bash
PYTHON_BIN=python3 nextflow run . -profile test --workflow chipseq \
  --legacy_dry_run true \
  --chipseq_config pipelines/chipseq/legacy/config/example_pipeline_config.sh
```

## Nextflow reports

Every run enables timeline, trace, execution report, and DAG under
`<outdir>/pipeline_info/`.
