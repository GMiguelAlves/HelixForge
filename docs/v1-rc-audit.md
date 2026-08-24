# v1 release-candidate consolidation audit

> **Historical record.** This audit documents preparation of the first release
> candidate. It is retained for traceability and is not user guidance.

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

## License audit

The maintainer selected Apache License 2.0 on 2026-08-24. The source audit
found no vendored third-party source tree, submodule, external binary asset, or
redistributed biological dataset. Synthetic fixtures are project-owned test
data. A root `LICENSE`, `NOTICE`, CFF license identifier, and explicit
third-party/container boundary are now present.

Scientific tools invoked by the workflows remain independently licensed.
Project-built containers are aggregate distributions and must preserve the
license metadata and notices shipped by their operating-system, Conda,
Bioconda, CRAN, and Bioconductor packages. Changing HelixForge from Apache-2.0
to MIT would not remove those upstream obligations.

The first clean-clone attempt exposed an undeclared development dependency: an
incomplete host `jsonschema` installation lacked `referencing`. The RC now pins
the test dependency in `requirements-dev.txt`. A second clone installed it in
an isolated `/tmp` target and passed the complete gate.

## Consolidation validation

- Environment: WSL2/Linux, Java 21.0.11, Nextflow 25.10.7, Docker available.
- Unit/contract/architectural suite: 139 tests, 139 passed; the original clean
  clone gate passed 138 tests and the licensing contract added one more;
  no skipped test in that dependency-complete environment.
- Documentation: 111 local links checked, none broken.
- Nextflow lint: 162 files, zero errors and zero warnings.
- Public stubs: RNA-seq 27, ChIP-seq 69, Integrative 12, and `all` 108
  processes; terminal manifests present for all.
- Reduced real Integrative: 12 processes; terminal manifest and final HTML
  report present.
- Clean clone contained no development cache, prior results or untracked file;
  final repository status remained clean.

The existing controlled Slurm validation remains the real reduced scientific
evidence for the native top-level RNA-seq and ChIP-seq paths. The RC clean-clone
pass revalidated their full composition and terminal contracts in stub mode; it
did not repeat the already certified OCI/Slurm scientific runs or claim a new
biological benchmark.

## Final classification

- `RC_BLOCKER`: none.
- `KNOWN_LIMITATION`: environment-specific Nextflow/LevelDB resume behavior;
  experimental STAR, Apptainer/Singularity, Conda and external manifests.
- `POST_RC`: reviewed biological benchmarks, Batch Effect Assessment, pathway
  enrichment, base-image/action SHA hardening and additional providers.

The audit found no remaining scientific, software-test, or repository-license
blocker in the executed release-candidate gate.
