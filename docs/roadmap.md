# HelixForge scientific roadmap

This roadmap records planned scientific APIs without making them part of the
current production contract. A planned item becomes supported only after its
contract, provider runtime, reduced tests, real-data validation, provenance,
and documentation are complete.

## Container runtime validation milestone

Status: **completed with an external operational limitation**.

The RNA-seq and ChIP-seq OCI runtimes were certified with reduced functional
Docker tests, and both complete synthetic scientific paths were validated on
Slurm with controlled runtimes. The institutional cluster did not provide an
administrator-supported Apptainer runtime on either the head node or compute
nodes. Consequently, an end-to-end Apptainer run with registry pulls from GHCR
and Quay and the required `/home` and `/scratch` mounts could not be performed.

This infrastructure absence is documented and is not a scientific failure or
a release gate for HelixForge. If the cluster later provides that complete
runtime configuration, the versioned probe and full synthetic workflow should
be repeated as an operational certification without reopening the pipeline
architecture.

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

Status: **planned, post-retirement release**.

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

## Release order

RNA-seq, ChIP-seq and Integrative legacy retirement is complete. Their final
sources are preserved by `rnaseq-legacy-v1.0.0`, `chipseq-legacy-v1.0.0`, and
`integrative-legacy-v1.0.0`.

1. Validate RNA-seq and ChIP-seq with reviewed biological
   datasets.
2. Implement Batch Effect Assessment as an optional exploratory subworkflow.
3. Implement Pathway Enrichment providers behind the common downstream API.
