# Migrating to HelixForge v1

## What changed

The active tree no longer contains executable legacy coordinators or fallbacks.
Historical implementations remain available through immutable legacy tags.
HelixForge v1 uses native DSL2 processes and semantic terminal manifests.

## RNA-seq

- Provide local FASTQs, metadata and references; download is no longer a DAG
  stage.
- Salmon is the production quantifier. Select STAR only as an experimental
  provider.
- Select an explicit `rnaseq_import_policy`; do not rely on implicit tximport
  normalization.
- Supply a versioned DE design/contrast specification.
- Put batch in an estimable DESeq2 formula. Do not feed an automatically
  corrected matrix into inference.
- Downstream tools consume `rnaseq_run_manifest.json` and semantic artifact
  roles rather than legacy paths.

## ChIP-seq

- Express treatment/control and replicate identity explicitly in metadata.
- Select peak type, genome size, QC and consensus/IDR policy explicitly.
- `chipseq_run_mode=full` is entirely native.
- IDR is optional and limited to its declared two-replicate narrowPeak contract.
- Downstream tools consume `chipseq_run_manifest.json`.

## Integrative

- Supply compatible RNA and ChIP terminal manifests plus their sibling
  `integration_artifacts/` directories.
- Supply versioned harmonization, mark-role, interpretation, prioritization and
  functional-annotation policies.
- Do not point the workflow at arbitrary legacy result directories.

## Compatibility boundary

Public schema/model version `1.0` contracts are the v1 boundary. Internal work
paths, process names and cache keys are not API. Re-run reduced validation after
changing a provider, reference, policy or module script.

## Historical comparison

The legacy tags remain the reference for audit and semantic regression, but the
legacy layout is not a compatibility promise for new output trees. Follow the
retirement documents in `docs/` when a historical re-execution is necessary.
