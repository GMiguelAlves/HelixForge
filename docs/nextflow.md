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
- `docker`: uses the pinned images declared by each native QC/alignment module.
- `singularity`: uses the same OCI images for native modules.
- `apptainer`: uses pinned OCI/blob images for native modules.
- `conda`: creates pinned native QC/alignment environments; legacy scripts still
  activate their existing named environments.
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

## Native RNA-seq QC

The complete native QC layer is enabled by default. Disable it to reproduce the
fully legacy QC orchestration path:

```bash
nextflow run . -profile local --workflow rnaseq \
  --rnaseq_native_qc false
```

`TRIM_QUALITY`, `TRIM_LENGTH`, projects, metadata, scratch paths, and output
names continue to come from the selected RNA-seq `pipeline_config.sh`.

`--rnaseq_native_trim_galore false` remains a backward-compatible alias that
also selects the legacy QC path. Partial native QC is intentionally unsupported.

## Native RNA-seq alignment

The generic Alignment API and STAR provider are enabled by default when the
legacy configuration selects `QUANT_METHOD=star`. Select the legacy STAR path:

```bash
nextflow run . -profile local --workflow rnaseq \
  --rnaseq_native_alignment false
```

Salmon is always wrapped in this stage. STAR index and alignment parameters,
paths, and output names continue to come from `pipeline_config.sh`. See
[native-rnaseq-alignment.md](native-rnaseq-alignment.md).
