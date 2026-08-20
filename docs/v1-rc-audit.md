# v1 release-candidate consolidation audit

Audit date: 2026-08-20. Branch: `contrib/v1-rc-consolidation`.

## Classification

### REMOVE

- Dead post-retirement `legacy_orchestrator` configuration and comments.
- Personal institutional paths in active Slurm validation harnesses.

### UPDATE

- User-first README, installation, Quick Start, workflows and outputs.
- Runtime/profile statements and Slurm concurrency.
- Version identity, contribution/release metadata and CI gate.
- Nextflow lint warnings and previously unused Apptainer parameters.

### KEEP -- required

- All 76 native module directories: consumer audit found no orphan module.
- Public schemas, policies, fixtures, contract tests and regression goldens.
- Native RNA-seq, ChIP-seq, Integrative and `all` entry points.

### KEEP -- historical

- Legacy analysis/retirement records, validation reports, baseline manifests
  and regression evidence. These are audit material, not active runtime code.

### DEFER

- Public/reviewed biological benchmarks (explicitly outside this stage).
- Batch Effect Assessment API and pathway enrichment.
- Additional assay/quantification providers.
- Full external-manifest interoperability and alternative cache backends.
- Full-SHA pinning of third-party GitHub Actions; current version tags remain a
  supply-chain hardening item.

## Security and portability

- No credentials or tokens were found in tracked application/configuration
  files during the consolidation search.
- Personal Slurm paths were replaced with generic guarded paths.
- Generated caches, IDE files, Python/R state and common biological binaries
  are excluded or treated as binary by repository hygiene rules.
- Heavy/private scientific datasets are not part of the repository.

## Release blockers

1. **License:** no root `LICENSE` exists. A maintainer must choose the license;
   it cannot be inferred safely from code or repository history.
2. **Final gate:** clean-clone and smoke/CI evidence must be completed after all
   RC consolidation commits are present.

The final decision must be reported as `RC_READY` only when this list is empty;
otherwise it is `RC_BLOCKED` with the unresolved items named explicitly.
