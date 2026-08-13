# HelixForge scientific roadmap

This roadmap records planned scientific APIs without making them part of the
current production contract. A planned item becomes supported only after its
contract, provider runtime, reduced tests, real-data validation, provenance,
and documentation are complete.

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

Status: **planned, post-legacy-retirement release**.

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

1. Retire automatic batch correction from every top-level inferential path.
2. Complete the native RNA-seq release and validate it with reviewed biological
   datasets.
3. Implement Batch Effect Assessment as an optional exploratory subworkflow.
4. Implement Pathway Enrichment providers behind the common downstream API.
