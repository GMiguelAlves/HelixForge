# Integrative legacy retirement inventory

Stage 6 does not delete or tag the legacy implementation. It records the exact
boundary to remove in a later, isolated pull request after the native workflow
is accepted.

## Retire later

- `pipelines/integrative/legacy/`, including the shell coordinator and its
  numbered execution scripts;
- `subworkflows/local/integrative/integration.nf`, the former chain of
  `LEGACY_STEP` wrappers;
- Integrative-only legacy configuration parameters and documentation that
  point to `integrative_config` or old numbered result directories;
- legacy-only dry-run and wrapper tests after their golden scientific products
  have been archived.

`modules/local/legacy_step/` must be removed only if a repository-wide search
after that PR proves that no other supported path imports it. Frozen golden
tables used by native regression should remain under tests even after the
executable legacy tree is removed.

## Preserve

- terminal-manifest, Evidence, Harmonization, Molecular Integration,
  Interpretation, Functional, Visualization and Report contracts;
- the characterized legacy golden products and the script that compares them;
- documentation of scientific behavior, thresholds, deterministic ties and
  known non-critical visualization differences;
- a release tag pointing to the final merged commit that still contains the
  executable legacy coordinator.

The future tag should be created from the Stage 6 merge commit immediately
before the retirement PR is merged, for example
`integrative-legacy-v1.0.0`. It must not be created during Stage 6 because the
completed native replacement must be reviewed first.

## Retirement gate

Retirement requires green Stage 2–6 contract/regression suites, the complete
12-process reduced run, schema-valid terminal product, accepted documentation,
and correct `workflow all` bundle wiring. Reviewed biological benchmarks are a
post-retirement release activity and are not part of this gate.

