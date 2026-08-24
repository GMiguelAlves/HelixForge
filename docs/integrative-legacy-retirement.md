# Integrative legacy retirement

> **Historical retirement record.** The current Integrative workflow is
> documented in [Integrative workflow](integrative-native-workflow.md).

Status: **retired from the current source tree**.

## Immutable boundary

The final commit containing both the accepted Integrative workflow and the
executable Integrative legacy path was protected before deletion:

- annotated tag: `integrative-legacy-v1.0.0`;
- target commit: `62d71a7025801e01f98af869e4d632922412fd99`;
- retirement date: 2026-08-20.

The tag is the authoritative source for historical execution and audit. It is
not a supported provider in current runs.

## Removed interfaces

- `pipelines/integrative/legacy/` and its shell/Python/R coordinator;
- the former `subworkflows/local/integrative/integration.nf` wrapper chain;
- the repository-wide `LEGACY_STEP` module and helper scripts, after confirming
  that RNA-seq and ChIP-seq had no remaining imports;
- `legacy_dry_run` and `integrative_config` from configuration and schema;
- legacy characterization executors that depended on removed source.

The current `workflows/integrative.nf`, Integration APIs, schemas, modules and
`workflow all` terminal-bundle wiring were not changed.

## Preserved scientific evidence

`tests/integrative_legacy_characterization/` retains the reduced inputs,
expected behavior, baseline manifest, 38 normalized golden artifacts and their
checksums. Native Evidence, Harmonization, Molecular Integration,
Interpretation, Functional Analysis and top-level workflow tests consume these
oracles directly. A repository architecture test rejects restored legacy paths,
imports or public parameters.

## Validation gate

Retirement required green Integration contract suites, Integrative
stub and reduced real run, schema-valid terminal manifest, and `workflow all`
stub composition. Scientific outputs are compared with the archived golden
tables; paths, timestamps and serialization metadata are not treated as
scientific values. Reviewed biological benchmarks remain a post-retirement
release activity.

## Historical recovery

Use an isolated worktree so tagged outputs cannot be mixed with current native
products:

```bash
git worktree add ../helixforge-integrative-legacy integrative-legacy-v1.0.0
```

The current Integrative workflow accepts only RNA-seq and ChIP-seq terminal
bundles plus explicit native policies. No fallback to the tagged source exists.
