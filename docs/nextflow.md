# Running with Nextflow

The runtime certified for complete scientific execution is Nextflow `25.10.7`,
enforced by the project manifest. This is a temporary exact pin while the
demonstrated task-cache persistence failure is investigated. Java 21 and Java
23 both resumed a one-task probe with 25.10.7, but the identical top-level RNA
workflow did not persist task records; production `-resume` is not certified.

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
nextflow run . -profile slurm --workflow chipseq --chipseq_run_mode post_alignment \
  -c conf/my_cluster.config
nextflow run . -profile slurm --workflow chipseq --chipseq_run_mode peaks \
  --chipseq_peak_type narrow --chipseq_effective_genome_size 2.7e9 \
  -c conf/my_cluster.config
nextflow run . -profile slurm --workflow chipseq --chipseq_run_mode differential_binding \
  --chipseq_consensus_method union --chipseq_db_spec chipseq_db_spec.json \
  -c conf/my_cluster.config
nextflow run . -profile local --workflow chipseq --chipseq_run_mode annotation \
  --chipseq_annotation_peaks peaks.bed \
  --chipseq_annotation_peak_manifest peak_manifest.json \
  --chipseq_annotation_reference genome.fa \
  --chipseq_annotation_reference_manifest reference_manifest.json \
  --chipseq_annotation_gtf annotation.gtf
nextflow run . -profile local --workflow chipseq --chipseq_run_mode tracks \
  --chipseq_native_tracks true \
  --chipseq_tracks_input_manifest tracks_input.json
nextflow run . -profile local --workflow chipseq --chipseq_run_mode report \
  --chipseq_native_report true \
  --chipseq_report_input_manifest chipseq_report_input.json
```

`qc` performs metadata validation, raw FastQC and MultiQC. `alignment` adds
Bowtie2 indexing and per-record alignment. `post_alignment` adds selection,
duplicate, blacklist, integrity and final-QC providers. `peaks` adds validated
per-replicate MACS3 3.0.4 calling and requires explicit peak type and numerical
effective genome size. `full` remains the complete legacy fallback. Use
`--chipseq_native_peak_calling false` to run only the legacy peaks step.
`differential_binding` advances through Peak QC and Consensus into explicit
featureCounts/DESeq2 providers and requires a versioned DB specification. Use
`--chipseq_native_differential_binding false` for the legacy differential step.
`annotation` consumes an already produced Peak Calling or Consensus manifest
and never reruns upstream analysis. Set `--chipseq_native_peak_annotation false`
for the unchanged legacy annotation step.
`tracks` consumes an external final-BAM/reference inventory, creates individual
and optional non-control aggregate BigWigs, and never reruns upstream stages.
Set `--chipseq_native_tracks false` for the unchanged legacy tracks step.
`report` consumes a versioned inventory of existing semantic manifests and
does not rerun upstream stages. Set `--chipseq_native_report false` for the
unchanged legacy report step.

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

The complete native input/QC layer is enabled by default. The legacy download,
metadata, and QC fallback processes are no longer part of the RNA workflow.

`TRIM_QUALITY`, `TRIM_LENGTH`, projects, metadata, scratch paths, and output
names continue to come from the selected RNA-seq `pipeline_config.sh`.

Both native QC flags must remain true; false values fail rather than silently
selecting a legacy path. Input acquisition happens before `nextflow run`.

## Native RNA-seq alignment

The generic Alignment API remains available, but STAR is optional and
experimental. It runs only when explicitly requested through `alignment`,
`both`, or the legacy-compatible `config` mode with `QUANT_METHOD=star`:

```bash
nextflow run . -profile local --workflow rnaseq \
  --rnaseq_analysis_mode quantification \
  --rnaseq_native_alignment false
```

STAR index and alignment parameters, paths, and output names continue to come
from `pipeline_config.sh`. See
[native-rnaseq-alignment.md](native-rnaseq-alignment.md).

## Native RNA-seq quantification

The Quantification API and Salmon provider are the default production path. A provider
selected by Import API must remain native because the legacy path does not emit
the required manifest. An unselected provider may still be disabled in
`config` mode for compatibility.

Choose which independent analytical layers run after QC:

```bash
# Official production path (default)
nextflow run . --workflow rnaseq --rnaseq_analysis_mode quantification

# Preserve legacy QUANT_METHOD behavior explicitly
nextflow run . --workflow rnaseq --rnaseq_analysis_mode config

# STAR only as an explicit stage stop
nextflow run . --workflow rnaseq --rnaseq_run_mode alignment

# Salmon only as an explicit stage stop
nextflow run . --workflow rnaseq --rnaseq_run_mode quantification

# STAR and Salmon in parallel; Import API uses QUANT_METHOD
nextflow run . --workflow rnaseq --rnaseq_analysis_mode both
```

Forced modes require their native provider flags to remain enabled. STAR is
architecturally supported but is not part of the currently certified RNA-seq
production path. A provider
required by `QUANT_METHOD` cannot be disabled when Import or DE is requested,
because no legacy provider manifest fallback exists. Salmon
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
[import_api.md](import_api.md). Production combinations are fixed by
[RNA-seq Import policy](rnaseq_import_policy.md).

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
