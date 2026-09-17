# Running with Nextflow

The runtime certified for complete scientific execution and resume is Nextflow
`25.10.7` with Java 21, enforced by the project manifest. Invoke it through the
official `nextflow` launcher. Direct `java -jar nextflow-*-one.jar` execution
is unsupported because it bypasses JVM options required for task-cache
serialization.

## Safe resume preflight

For costly production runs, capture a cache receipt after the original run
while the task database and work directory are still present:

```bash
bin/helixforge-resume-guard capture \
  --run-name RUN_NAME \
  --receipt /persistent/audit/resume-receipt.json \
  --work-dir /shared/work
```

Before resuming, use the same launch directory, `NXF_CACHE_DIR` and Nextflow
runtime to verify that the live task inventory still matches the receipt:

```bash
bin/helixforge-resume-guard check \
  --run-name RUN_NAME \
  --receipt /persistent/audit/resume-receipt.json \
  --work-dir /shared/work

nextflow run . -resume RUN_NAME [the original arguments]
```

The check validates non-empty successful task records, stable hash/name
identities, work-directory containment and `.exitcode=0`. It fails before job
submission when persistence is absent or partial. A receipt contains relative
work paths rather than site-specific absolute paths and must be kept with the
private run audit, not committed as project configuration.

The former empty-cache incident, its direct-JAR root cause and the corrected
runtime policy are recorded in the
[resume-cache diagnostic](resume-cache-diagnostic.md).

## Certified Python inheritance on Slurm

Site launchers must prepend the certified tool environment to `PATH` **before**
starting Nextflow. Nextflow processes then inherit that exact path. Checking
only that a `python3` executable exists is insufficient: the selected
interpreter must also provide the dependencies used by terminal manifest
generation, including `jsonschema`.

The production RNA-seq Slurm harness enforces this order:

```text
certified RNA/Python environment -> PATH -> Nextflow -> RUN_MANIFEST
```

Its compute-node preflight verifies that `python3` resolves to the certified
environment and executes `python3 -c "import jsonschema"` in the same inherited
environment before any scientific workflow is launched. A failed import or an
unexpected interpreter aborts the run before analysis. Site-specific absolute
paths remain private configuration and must not be committed to the repository.

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
  --chipseq_tracks_input_manifest tracks_input.json
nextflow run . -profile local --workflow chipseq --chipseq_run_mode report \
  --chipseq_report_input_manifest chipseq_report_input.json
```

`qc` performs metadata validation, raw FastQC and MultiQC. `alignment` adds
Bowtie2 indexing and per-record alignment. `post_alignment` adds selection,
duplicate, blacklist, integrity and final-QC providers. `peaks` adds validated
per-replicate MACS3 3.0.4 calling and requires explicit peak type and numerical
effective genome size. `full` is the native single-session coordinator and
requires an explicit Consensus strategy and a Differential Binding spec. The
current ChIP-seq workflow has no legacy coordinator or fallback.
`differential_binding` advances through Peak QC and Consensus into explicit
featureCounts/DESeq2 providers and requires a versioned DB specification.
`annotation` consumes an already produced Peak Calling or Consensus manifest
and never reruns upstream analysis.
`tracks` consumes an external final-BAM/reference inventory, creates individual
and optional non-control aggregate BigWigs, and never reruns upstream stages.
`report` consumes a versioned inventory of existing semantic manifests and
does not rerun upstream stages.

The existing configuration remains authoritative:

```text
pipelines/rnaseq/config/pipeline_config.sh
pipelines/chipseq/config/pipeline_config.sh
```

Integrative configuration is supplied through native manifests and the
versioned `integrative_*` policy parameters.

Override a config without changing workflow code:

```bash
nextflow run . --workflow rnaseq \
  --rnaseq_config /shared/project/config/pipeline_config.sh
```

## Profiles

- `local`: Nextflow local executor.
- `slurm`: one scheduler allocation per native scientific process; processes
  never submit child jobs.
- `docker`: uses the pinned images declared by each native QC, alignment,
  quantification, and import module.
- `singularity`: uses the same OCI images for native modules.
- `apptainer`: uses pinned OCI/blob images for native modules.
- `conda`: creates the declared native module environments.
- `test`: reduced local settings for stub tests.

## Dry-run modes

`-stub-run` compiles the complete graph and runs only module stub blocks. It is
the safe validation mode for this repository.

The retired legacy dry-run switch and Integrative shell-config parameter are no
longer part of the public interface. Use `-stub-run` for all active workflows.

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
Nextflow `-resume`: `qc`, `alignment`, `quantification`, `import`, `de`,
`report`, `report_reentry`, or `full`. The default is `full`.
`report_reentry` is a terminal-only exception to the cumulative stage model.
`--rnaseq_native_de false` is rejected
because the retired DEG wrapper is available only from `rnaseq-legacy-v1.0.0`.

```bash
nextflow run . --workflow rnaseq --rnaseq_run_mode de -resume
```

DESeq2 model fitting and each Wald contrast are separate cache boundaries.
Changing only a contrast does not refit the model.

## Native RNA-seq report

The candidate-gene Report API is opt-in in `full` and mandatory when the
terminal mode is `report`:

```bash
nextflow run . --workflow rnaseq --rnaseq_run_mode report \
  --rnaseq_de_spec /path/to/rnaseq_de_spec.json \
  --rnaseq_report_genes /path/to/genes.txt -resume
```

Set `--rnaseq_report_enabled true` to append it to a `full` run. The provider
consumes the Import abundance matrix/sample table and Differential Expression
aggregate/manifest directly. See [rnaseq_report_api.md](rnaseq_report_api.md).

To render a report after upstream scratch and cache cleanup, use the retained
API artifacts directly:

```bash
nextflow run . --workflow rnaseq --rnaseq_run_mode report_reentry \
  --rnaseq_report_import_manifest /path/to/import_manifest.json \
  --rnaseq_report_abundance /path/to/tpm_matrix.tsv \
  --rnaseq_report_samples /path/to/quant_samples.tsv \
  --rnaseq_report_annotation /path/to/annotation.gtf \
  --rnaseq_report_de_results /path/to/DEGs_all_results.tsv \
  --rnaseq_report_de_manifest /path/to/de_manifest.json \
  --rnaseq_report_genes /path/to/genes.txt \
  --outdir results
```

This route schedules only `RNASEQ_REPORT_CONTEXT` and
`RNASEQ_GENE_REPORT`. The context validates manifest types, declared checksums,
sample order, identifiers, and candidate syntax before rendering.
