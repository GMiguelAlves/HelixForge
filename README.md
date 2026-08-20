# HelixForge

Start with the [HelixForge Wiki](https://github.com/GMiguelAlves/HelixForge/wiki) for a Portuguese, navigable
overview of the current architecture, workflows, execution, and development.
Planned scientific APIs are tracked in the [roadmap](docs/roadmap.md).

HelixForge is a Nextflow DSL2 implementation for RNA-seq, ChIP-seq, and
IntegrateSeq analyses. RNA-seq is fully native; its retired implementation is
archived in the immutable `rnaseq-legacy-v1.0.0` tag. ChIP-seq and IntegrateSeq
retain compatibility boundaries while their remaining providers are migrated.

The RNA-seq input boundary and QC layer are native: validated local FASTQs and
metadata feed a checksummed Reference Bundle, FastQC, Trim Galore, per-sample
FASTQ merge, and MultiQC as separate DSL2 processes. Data acquisition is no
longer part of the scientific workflow. STAR alignment is native behind a
generic Alignment API, and Salmon implements
the production RNA-seq Quantification API. Salmon is the default path; STAR is
an optional, experimental provider that must be selected explicitly. A native
Import API converts Salmon or STAR artifacts into provider-neutral matrices. A Differential Expression
API validates explicit designs and runs DESeq2 Wald models and contrasts
natively. The RNA-seq Report API now validates explicit Import/DE manifests and
generates the established candidate-gene tables, figures and HTML through a
native provider. No top-level RNA-seq path applies matrix batch correction
before inference; DESeq2 represents an estimable batch effect in the explicit
design, such as `~ batch + condition`. The preserved batch utilities are manual
exploratory tools only. Existing scientific filenames and the report `results/`
hierarchy are preserved. The native gene-report image is pinned by certified
OCI digest and its real reduced R execution is enforced by CI.
The complete production path was also revalidated on Slurm with the synthetic
release fixture; see the [RNA-seq final validation](docs/rnaseq-final-validation.md).
The removal boundary and historical regression procedure are recorded in the
[RNA-seq legacy retirement note](docs/rnaseq-legacy-retirement.md).

The ChIP-seq native foundation validates flexible metadata, controls and
biological/technical replicate identity, reuses FastQC/MultiQC, and implements
Bowtie2 indexing/alignment behind the same generic Alignment API used by STAR.
Native modes include `qc`, `alignment`, `post_alignment`, `peaks`, `peak_qc`,
`consensus`, `idr`, `differential_binding`, `annotation`, `tracks`, and
`report`. The BAM mode adds
explicit MAPQ/flag selection, duplicate policy, optional blacklist and final
BAM integrity/QC. Peak Calling API v1 validates explicit treatment/control
relationships and runs a pinned MACS3 provider independently for each replicate.
Peak QC API v1 then calculates explicitly defined per-replicate FRiP and generic
peak statistics and publishes a caller-neutral QC manifest.
Consensus API v1 safely joins those manifests by identity and implements
explicit `union`, `intersection`, and minimum-replicate-support strategies over
atomic intervals. IDR is an optional statistical provider for exactly two
premerged biological `narrowPeak` replicates. It runs IDR 2.0.4.2 with an
explicit threshold/rank metric and fixed random seed, then publishes the same
provider-neutral peak roles consumed by Differential Binding, Annotation and
Report.
Differential Binding API v1 adds the explicit `differential_binding` mode:
semantic Consensus peak sets become a comparison universe, featureCounts
produces an ID-mapped raw peak matrix, and DESeq2 fits one reusable model with
independently cached contrasts. A versioned specification is mandatory.
Peak Annotation API v1 consumes an existing Peak Calling or Consensus manifest
without rerunning upstream stages, validates the reference/GTF/build contract,
and emits provider-neutral annotated peaks, associations, statistics, and
provenance.
Track Generation API v1 independently consumes an existing final-BAM inventory
and reference manifest. It creates explicitly parameterized individual and
non-control aggregate BigWigs through a reusable provider, statistics, and
aggregation graph without rerunning upstream stages.
Report/Integration API v1 closes the native ChIP-seq functional DAG. It joins
existing semantic manifests, preserves optional and `not_implemented` states,
and emits self-contained HTML, structured JSON, final manifest, versions,
execution metadata, and provenance without rerunning upstream stages.
The optional IDR full path was validated end-to-end on Slurm with the reduced
synthetic fixture: 105 processes completed, both condition-level IDR groups
produced non-empty results, and the final report passed all top-level checks.

Native differential expression requires a versioned JSON specification with an
explicit design, contrasts, filter, and count-handling policy. Copy
`assets/rnaseq_de_spec.example.json` and adapt it to the study metadata.
Salmon users must declare `--rnaseq_library_protocol full_length` with
`--rnaseq_counts_from_abundance lengthScaledTPM`, or `three_prime` with
`--rnaseq_counts_from_abundance no`. See the versioned
[RNA-seq Import policy](docs/rnaseq_import_policy.md).

HelixForge currently pins **Nextflow 25.10.7** as the runtime certified for
complete scientific execution. The exact pin holds the runtime stable while a
task-cache persistence failure observed on the institutional Slurm environment
is investigated. Top-level `-resume` and selective invalidation are not yet
certified.

## Workflows

- `rnaseq`
- `chipseq`
- `integrative`
- `all`

## Quick start

```bash
nextflow run . -profile local --workflow rnaseq \
  --rnaseq_config /path/to/rnaseq/pipeline_config.sh \
  --rnaseq_import_policy production_v1 \
  --rnaseq_library_protocol full_length \
  --rnaseq_counts_from_abundance lengthScaledTPM \
  --rnaseq_de_spec /path/to/rnaseq_de_spec.json \
  --rnaseq_report_enabled true \
  --rnaseq_report_genes /path/to/genes.txt
```

Use `--rnaseq_trim_quality` or `--rnaseq_trim_length` only when intentionally
overriding the corresponding shell-configuration QC setting. Their defaults remain the
values sourced from `config/pipeline_config.sh`.

FASTQs and references must already exist at the locations declared by the
samplesheet/configuration. HelixForge validates and tracks them but does not
download data during a scientific run.

This command follows the official path `QC -> Salmon -> Import/tximport ->
DESeq2`. Use `--rnaseq_analysis_mode config`, `alignment`, or `both` only when
explicitly testing the optional STAR provider.

Inspect the complete graph without running scientific tools:

```bash
nextflow run . -profile test -stub-run --workflow all
```

Compile the native ChIP-seq foundation without scientific tools:

```bash
nextflow run . -profile test -stub-run --workflow chipseq \
  --chipseq_run_mode post_alignment
```

For a real run, use `--chipseq_run_mode qc`, `alignment`, `post_alignment`,
`peaks`, `peak_qc`, `consensus`, `differential_binding`, `annotation`, `tracks`,
`report`, or `full` and provide the required config or external manifest.
Native peaks require explicit `--chipseq_peak_type narrow|broad` and a numerical
`--chipseq_effective_genome_size`. `full` is the native, single-session
coordinator from QC through the final report; it also requires an explicit
consensus method and `--chipseq_db_spec`. ChIP-seq has no legacy coordinator or
fallback in the current source tree.
Native consensus additionally requires `--chipseq_consensus_method
union|intersection|replicate_support|idr`; replicate support also requires
`--chipseq_min_replicates`. IDR additionally requires exactly two premerged
biological narrowPeak inputs and an explicit `--chipseq_idr_rank_metric
signal_value|p_value|q_value`. Select it in `full` with
`--chipseq_consensus_method idr`, or use the dedicated `idr` mode.

Native differential binding additionally requires
`--chipseq_run_mode differential_binding`, an explicit consensus method, and
`--chipseq_db_spec /path/to/chipseq_db_spec.json`. Copy
`assets/chipseq_db_spec.example.json` as a starting point.

Native peak annotation uses `--chipseq_run_mode annotation` with explicit
`--chipseq_annotation_peaks`, `--chipseq_annotation_peak_manifest`,
`--chipseq_annotation_reference`, `--chipseq_annotation_reference_manifest`,
and `--chipseq_annotation_gtf`.

Native tracks use `--chipseq_run_mode tracks` and
`--chipseq_tracks_input_manifest /path/to/tracks_input.json`. Copy
`assets/chipseq_tracks_input.example.json` as a starting point.

Native report generation uses `--chipseq_run_mode report` and
`--chipseq_report_input_manifest /path/to/chipseq_report_input.json`. Copy
`assets/chipseq_report_input.example.json` as a starting point.

The current ChIP-seq configuration is
`pipelines/chipseq/config/pipeline_config.sh`. The final executable legacy
snapshot is preserved by the annotated tag `chipseq-legacy-v1.0.0`.

See [docs/nextflow.md](docs/nextflow.md),
[docs/native-trim-galore.md](docs/native-trim-galore.md),
[docs/native-rnaseq-qc.md](docs/native-rnaseq-qc.md),
[docs/native-rnaseq-alignment.md](docs/native-rnaseq-alignment.md),
[docs/alignment_api.md](docs/alignment_api.md),
[docs/native-rnaseq-quantification.md](docs/native-rnaseq-quantification.md),
[docs/quantification_api.md](docs/quantification_api.md),
[docs/import_api.md](docs/import_api.md),
[docs/native-rnaseq-import.md](docs/native-rnaseq-import.md),
[docs/differential_expression_api.md](docs/differential_expression_api.md),
[docs/native-rnaseq-de.md](docs/native-rnaseq-de.md),
[docs/rnaseq_report_api.md](docs/rnaseq_report_api.md),
[docs/native-rnaseq-report.md](docs/native-rnaseq-report.md),
[docs/rnaseq-scientific-review.md](docs/rnaseq-scientific-review.md),
[docs/chipseq-legacy-analysis.md](docs/chipseq-legacy-analysis.md),
[docs/chipseq-legacy-retirement.md](docs/chipseq-legacy-retirement.md),
[docs/chipseq-architecture.md](docs/chipseq-architecture.md),
[docs/chipseq-scientific-review.md](docs/chipseq-scientific-review.md),
[docs/chipseq-api.md](docs/chipseq-api.md),
[docs/native-chipseq-bam-processing.md](docs/native-chipseq-bam-processing.md),
[docs/peak_calling_api.md](docs/peak_calling_api.md),
[docs/native-chipseq-peak-calling.md](docs/native-chipseq-peak-calling.md),
[docs/peak_qc_api.md](docs/peak_qc_api.md),
[docs/native-chipseq-peak-qc.md](docs/native-chipseq-peak-qc.md),
[docs/consensus_idr_api.md](docs/consensus_idr_api.md),
[docs/native-chipseq-consensus-idr.md](docs/native-chipseq-consensus-idr.md),
[docs/differential_binding_api.md](docs/differential_binding_api.md),
[docs/native-chipseq-differential-binding.md](docs/native-chipseq-differential-binding.md),
[docs/peak_annotation_api.md](docs/peak_annotation_api.md),
[docs/native-chipseq-peak-annotation.md](docs/native-chipseq-peak-annotation.md),
[docs/track_generation_api.md](docs/track_generation_api.md),
[docs/native-chipseq-tracks.md](docs/native-chipseq-tracks.md),
[docs/chipseq_report_api.md](docs/chipseq_report_api.md),
[docs/native-chipseq-report.md](docs/native-chipseq-report.md),
[docs/chipseq-differential-binding-review.md](docs/chipseq-differential-binding-review.md),
[docs/module_contracts.md](docs/module_contracts.md),
[docs/script-mapping.md](docs/script-mapping.md),
[docs/architecture-consolidation-audit.md](docs/architecture-consolidation-audit.md),
[docs/final-validation-plan.md](docs/final-validation-plan.md),
[docs/final-validation-report.md](docs/final-validation-report.md),
[docs/scientific-deviation-log.md](docs/scientific-deviation-log.md), and
[docs/limitations.md](docs/limitations.md).
