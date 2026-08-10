# HelixForge

HelixForge (formerly OmicsFlow) is a compatibility-first Nextflow DSL2 implementation for the existing
RNA-seq, ChIP-seq, and IntegrateSeq pipelines. The scientific Bash, Python, and
R implementations are preserved under `pipelines/*/legacy` and remain directly
executable.

The RNA-seq QC layer is native: FastQC before trimming, Trim Galore, FastQC
after trimming, per-sample FASTQ merge, merged-read FastQC, and MultiQC are
separate DSL2 processes. Download and metadata preparation remain wrappers,
STAR alignment is native behind a generic Alignment API, and Salmon implements
an independent generic Quantification API. A native Import API converts Salmon
or STAR artifacts into provider-neutral matrices. A Differential Expression
API validates explicit designs and runs DESeq2 Wald models and contrasts
natively. Final reports remain compatibility wrappers; legacy batch correction
is reachable only through the legacy DE fallback. Existing filenames and result
directories are preserved.

The ChIP-seq native foundation validates flexible metadata, controls and
biological/technical replicate identity, reuses FastQC/MultiQC, and implements
Bowtie2 indexing/alignment behind the same generic Alignment API used by STAR.
Native modes include `qc`, `alignment`, `post_alignment`, `peaks`, `peak_qc`,
`consensus`, and `idr`. The BAM mode adds
explicit MAPQ/flag selection, duplicate policy, optional blacklist and final
BAM integrity/QC. Peak Calling API v1 validates explicit treatment/control
relationships and runs a pinned MACS3 provider independently for each replicate.
Peak QC API v1 then calculates explicitly defined per-replicate FRiP and generic
peak statistics and publishes a caller-neutral QC manifest.
Consensus API v1 safely joins those manifests by identity and implements
explicit `union`, `intersection`, and minimum-replicate-support strategies over
atomic intervals. The separate IDR mode validates and records an IDR request,
but deliberately produces no peak set until a pinned statistical runtime has
been scientifically validated.
Differential Binding API v1 adds the explicit `differential_binding` mode:
semantic Consensus peak sets become a comparison universe, featureCounts
produces an ID-mapped raw peak matrix, and DESeq2 fits one reusable model with
independently cached contrasts. A versioned specification is mandatory.

Native differential expression requires a versioned JSON specification with an
explicit design, contrasts, filter, and count-handling policy. Copy
`assets/rnaseq_de_spec.example.json` and adapt it to the study metadata.
Salmon users must declare `--rnaseq_library_protocol full_length` with
`scaledTPM`/`lengthScaledTPM`, or `three_prime` with
`--rnaseq_counts_from_abundance no`. Original full-length counts are rejected
by the current matrix-based provider until offset-aware tximport input exists.

## Workflows

- `rnaseq`
- `chipseq`
- `integrative`
- `all`

## Quick start

```bash
nextflow run . -profile local --workflow rnaseq \
  --rnaseq_config /path/to/rnaseq/pipeline_config.sh \
  --rnaseq_library_protocol full_length \
  --rnaseq_counts_from_abundance lengthScaledTPM \
  --rnaseq_de_spec /path/to/rnaseq_de_spec.json
```

Inspect the complete graph without running scientific tools:

```bash
nextflow run . -profile test -stub-run --workflow all
```

Ask the existing orchestrators to print their own dry-run commands:

```bash
nextflow run . -profile local --workflow chipseq --legacy_dry_run true \
  --chipseq_config pipelines/chipseq/legacy/config/example_pipeline_config.sh
```

Compile the native ChIP-seq foundation without scientific tools:

```bash
nextflow run . -profile test -stub-run --workflow chipseq \
  --chipseq_run_mode post_alignment
```

For a real run, use `--chipseq_run_mode qc`, `alignment`, `post_alignment`,
`peaks`, `peak_qc`, or `consensus` and provide the existing project config through `--chipseq_config`.
Native peaks require explicit `--chipseq_peak_type narrow|broad` and a numerical
`--chipseq_effective_genome_size`. `full` retains the complete legacy fallback;
`--chipseq_native_peak_calling false` selects only the legacy peak step.
`--chipseq_native_peak_qc false` stops `peak_qc` mode after native Peak Calling.
Native consensus additionally requires `--chipseq_consensus_method
union|intersection|replicate_support`; the latter also requires
`--chipseq_min_replicates`. `idr` is currently a validated, provenance-bearing
provider request only and is not a scientific IDR result.

Native differential binding additionally requires
`--chipseq_run_mode differential_binding`, an explicit consensus method, and
`--chipseq_db_spec /path/to/chipseq_db_spec.json`. Copy
`assets/chipseq_db_spec.example.json` as a starting point. Set
`--chipseq_native_differential_binding false` to retain the unchanged legacy
`differential` step.

The default configs remain the versioned `config/pipeline_config.sh` files in
each legacy pipeline. Create their existing untracked user configuration files
before a real run.

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
[docs/rnaseq-scientific-review.md](docs/rnaseq-scientific-review.md),
[docs/chipseq-legacy-analysis.md](docs/chipseq-legacy-analysis.md),
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
[docs/chipseq-differential-binding-review.md](docs/chipseq-differential-binding-review.md),
[docs/module_contracts.md](docs/module_contracts.md),
[docs/script-mapping.md](docs/script-mapping.md), and
[docs/limitations.md](docs/limitations.md).
