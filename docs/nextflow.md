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

Native ChIP-seq foundation modes are selected independently:

```bash
nextflow run . -profile local --workflow chipseq --chipseq_run_mode qc
nextflow run . -profile slurm --workflow chipseq --chipseq_run_mode alignment \
  -c conf/my_cluster.config
```

`qc` performs metadata validation, raw FastQC and MultiQC. `alignment` adds
Bowtie2 indexing and per-record alignment. `peaks` and `full` use the complete
legacy fallback in foundation 0.1; use `--chipseq_native_foundation false` to
force that fallback explicitly.

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
- `docker`: uses the pinned images declared by each native QC, alignment,
  quantification, and import module.
- `singularity`: uses the same OCI images for native modules.
- `apptainer`: uses pinned OCI/blob images for native modules.
- `conda`: creates pinned native QC/alignment/quantification/import environments;
  legacy scripts still activate their existing named environments.
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

STAR index and alignment parameters, paths, and output names continue to come
from `pipeline_config.sh`. See
[native-rnaseq-alignment.md](native-rnaseq-alignment.md).

## Native RNA-seq quantification

The Quantification API and Salmon provider are enabled by default. A provider
selected by Import API must remain native because the legacy path does not emit
the required manifest. An unselected provider may still be disabled in
`config` mode for compatibility.

Choose which independent analytical layers run after QC:

```bash
# Preserve QUANT_METHOD behavior (default)
nextflow run . --workflow rnaseq --rnaseq_analysis_mode config

# STAR only; import and differential analysis are not launched
nextflow run . --workflow rnaseq --rnaseq_analysis_mode alignment

# Salmon plus the native Import API
nextflow run . --workflow rnaseq --rnaseq_analysis_mode quantification

# STAR and Salmon in parallel; Import API uses QUANT_METHOD
nextflow run . --workflow rnaseq --rnaseq_analysis_mode both
```

Forced modes require their native provider flags to remain enabled. Salmon
version, index/quantification parameters, paths, and output names remain
controlled by `pipeline_config.sh`. See
[native-rnaseq-quantification.md](native-rnaseq-quantification.md).

## Native RNA-seq import

The generic Import API is enabled by default and consumes only manifests and
semantic channels from STAR or Salmon. `QUANT_METHOD` remains authoritative for
provider selection. The old `RNASEQ_IMPORT_STEP` fallback has been removed;
`--rnaseq_native_import false` is rejected for modes that perform import.

Outputs retain the legacy names under `QUANTIFICATION_DIR`: counts, TPM/CPM,
sample metadata, and `tx2gene.tsv`. Salmon additionally emits effective length
and a `SummarizedExperiment`. See
[native-rnaseq-import.md](native-rnaseq-import.md) and
[import_api.md](import_api.md).

## RNA-seq stage modes

`--rnaseq_run_mode` defines the last requested native layer and works with
Nextflow `-resume`: `qc`, `alignment`, `quantification`, `import`, `de`, or
`full`. The default is `full`. `--rnaseq_native_de false` explicitly restores
the preserved DEG wrapper; it is never selected implicitly.

```bash
nextflow run . --workflow rnaseq --rnaseq_run_mode de -resume
```

DESeq2 model fitting and each Wald contrast are separate cache boundaries.
Changing only a contrast does not refit the model.
