# HelixForge scientific roadmap

This roadmap records planned scientific APIs without making them part of the
current production contract. A planned item becomes supported only after its
contract, provider runtime, reduced tests, real-data validation, provenance,
and documentation are complete.

## Container runtime validation milestone

Status: **completed with an external operational limitation**.

RNA-seq and ChIP-seq OCI providers have reduced functional Docker coverage,
and reduced complete paths have passed inside Slurm allocations with controlled
toolchains. Apptainer end-to-end certification remains pending and requires a
supported runtime, GHCR/Quay access and consistent input/work/output mounts on
both management and execution nodes. Container certification and host-tool
execution are distinct evidence; neither implies the other.

## ChIP-seq composition and read processing

Status: **implemented in v1.2.0; reduced functional validation passed**.

- Explicit prebuilt Bowtie2 indexes are validated without reconstruction.
- Trimming is optional and reuses shared single/paired-end Trim Galore modules
  with an explicit ChIP policy; raw reads remain the default.
- Differential Binding is optional in `full`; consensus/IDR can continue into
  annotation, tracks and reporting without invented contrasts.
- `post_consensus` supports accepted-artifact continuation without FASTQs or
  the original work directory; report-only mode remains isolated.
- Identical resume and selective FASTQ/reference/contrast/QC/script changes
  have reduced functional coverage, separate from the frozen benchmarks.

See [stage composition](guides/chipseq-stage-composition.md) and the
[v1.2.0 release notes](releases/release-notes-v1.2.0.md).

## RNA-seq inference policy already adopted

- Differential Expression consumes the uncorrected count artifact from the
  Import API.
- A valid batch variable is represented in the DESeq2 design, for example
  `~ batch + condition`; it is not removed from the matrix before inference.
- The specification remains explicit because batch may be absent, have one
  level, or be confounded with condition. Rank-deficient designs fail during
  preflight.
- ComBat, limma `removeBatchEffect`, or similar corrected matrices are
  exploratory artifacts and must never be selected automatically as DESeq2
  input.

## Batch Effect Assessment API

Status: **planned for a future release**.

The optional `BATCH_EFFECT_ASSESSMENT` subworkflow will consume the Import API
manifest, uncorrected matrix, sample metadata, and the Differential Expression
design. It will diagnose batch without changing the inferential input.

Planned analyses include:

- PCA before and after an explicitly selected exploratory correction;
- variance associated with batch and biological condition;
- correlation between principal components and batch;
- sample distances and clustering before and after correction;
- preservation of biological signal and batch/condition confounding;
- comparison of `~ condition` and `~ batch + condition` models;
- rank-deficiency and complete-confounding alerts.

Planned outputs include `batch_effect_metrics.tsv`,
`variance_explained.tsv`, PCA and clustering figures, an exploratory corrected
matrix, HTML report, manifest, parameters, versions, and provenance. The
corrected matrix will have an exploratory semantic role that the Differential
Expression API rejects as an inferential input.

## Pathway Enrichment API

Status: **planned for a subsequent RNA-seq release**.

Pathway enrichment will be a provider-neutral API downstream of Differential
Expression, not hidden inside the candidate-gene report. It will consume a DE
manifest, explicit contrast result, tested-gene universe, annotation/ID mapping,
organism, database release, and multiple-testing policy.

Initial provider candidates are GO, KEGG, and Reactome. Each provider must
record database version, gene identifier namespace, mapping losses, background
universe, enrichment method, thresholds, command, container, and checksums.
Common outputs will include enrichment tables, plots, mapping diagnostics,
manifest, versions, execution metadata, and provenance.

## RNA-seq single-end extension

Status: **implemented; reduced synthetic Slurm validation passed**.

The paired-end Salmon path remains the established biological production route. The
single-end extension now covers samplesheet validation, QC, trimming, technical
run merging, Salmon `-r`, Import, DESeq2, reports, terminal manifests and CI
stub regression. Fragment-length mean and standard deviation are explicit,
validated and retained in provenance; layouts cannot be mixed within one
dataset. Two reduced real-tool Slurm cases, including technical-run merge,
and identical cached `-resume` passed. Biological single-end validation with
a reviewed study and its justified fragment prior remains a separate gate.

## Release order

RNA-seq, ChIP-seq and Integrative legacy retirement is complete. Their final
sources are preserved by `rnaseq-legacy-v1.0.0`, `chipseq-legacy-v1.0.0`, and
`integrative-legacy-v1.0.0`.

The Integrative benchmark has been completed and frozen as
`PASS_WITH_LIMITATIONS`; every core release gate passed. The remaining planned
scientific work is:

1. Implement Batch Effect Assessment as an optional exploratory subworkflow.
2. Implement Pathway Enrichment providers behind the common downstream API.
3. Validate the single-end path with a reviewed biological study and its
   fragment-length prior while preserving the paired-end baseline.

RNA-seq and ChIP-seq reviewed biological benchmarks are complete. Their frozen
administrative entry points are
[`benchmark/rnaseq/`](../benchmark/rnaseq/README.md) and
[`benchmark/chipseq/`](../benchmark/chipseq/README.md).
