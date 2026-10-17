# HelixForge v1.2.0

HelixForge `v1.2.0` is a backward-compatible minor release focused on reusable
ChIP-seq execution and clearer public documentation. Existing scientific
algorithms, statistical models, score definitions and frozen benchmark
classifications are unchanged. The certified runtime remains Nextflow 25.10.7
through the official launcher with Java 21.

## ChIP-seq features

- **Reusable Bowtie2 indexes:** supply an index and schema 1.2 provenance
  manifest to validate reference, build parameters, runtime version and all six
  shards without rebuilding. Invalid bundles fail before alignment.
- **Optional trimming:** shared single/paired-end Trim Galore modules accept
  explicit quality, minimum length and optional adapter settings. Read audits
  preserve sample/control identity; pre/post FastQC and MultiQC retain QC
  evidence. Raw reads remain the default.
- **Optional Differential Binding:** `full` can complete annotation, tracks,
  reporting and the terminal manifest without a DB specification or fabricated
  contrast. Explicit DB requests are validated before scientific producers.
- **Accepted-artifact continuation:** `post_consensus` consumes declared
  consensus/IDR, final BAMs, metadata and reference manifests without FASTQs or
  the original cache. `consensus`/`idr --chipseq_postprocess true` also completes
  postprocessing. Report-only mode remains isolated.

See [stage composition](../guides/chipseq-stage-composition.md),
[index reuse](../api/alignment_api.md#reusing-a-bowtie2-index) and
[trimming policy](../implementation/native-chipseq-trimming.md).

## Corrections and compatibility

- Import preserves valid explicit technical-library identities across runs and
  rejects incomplete or inconsistent metadata instead of inventing replication.
- Bowtie2 index publication and metadata serialization are corrected. Helper
  source is tracked in generated commands without an incidental checkout mount.
- The release pins the certified joint Bowtie2 2.5.4/SAMtools 1.20 OCI image
  containing `procps`; scientific tool versions and alignment options are
  unchanged by that runtime refresh.
- Existing DB-enabled configurations retain their path. Explicit
  `--chipseq_db_enabled false` disables DB even when a parameter file supplies
  a DB specification. Omission is recorded as `not_requested`, never success.
- Public schema identifiers and scientific model versions remain unchanged.
  Retain compatible index manifests and reference checksums when upgrading.

## Validation scope

Contract tests, stubs and reduced real-tool execution cover composition,
index reuse, optional trimming, accepted-artifact continuation and report-only
isolation. A consolidated trimmed, DB-enabled fixture completed all 132 tasks
inside a Slurm allocation using existing Conda toolchains. An identical resume
cached all 131 non-terminal tasks; only the manifest refreshed the generated
execution name. Controlled FASTQ, reference, contrast, QC-policy and task-script
changes passed their selective-invalidation checks.

Container certification is separate from that host-tool Slurm fixture. Neither
certifies automatic recreation of every Conda environment or complete
Apptainer execution. See [full-workflow validation](../validation/chipseq-full-native-validation.md),
[runtime inventory](../guides/runtime-inventory.md) and
[cache behavior](../guides/nextflow.md#cache-and-invalidation).

## Documentation and retained limitations

The user guides now describe current modes, correct operational output names,
runtime requirements and cache boundaries. Documentation checks validate links
inside runner workspaces and reject zero-link checks. Detailed historical release notes
remain available from the documentation index; the README links only the two
latest releases.

The v1 RNA-seq, ChIP-seq and Integrative baselines remain
`PASS_WITH_LIMITATIONS`. STAR remains experimental; biological single-end
validation remains study-specific. The RN3, broad-domain, real-replicate and
Integrative IB4/IB5 qualifications are not removed by this functional release.
Batch Effect Assessment and RNA pathway enrichment remain roadmap items.
