# Versioning and stability

HelixForge uses [Semantic Versioning](https://semver.org/) for the public
software interface:

- **MAJOR**: an incompatible change to a stable workflow, required parameter,
  terminal manifest, schema, or documented output meaning;
- **MINOR**: a backward-compatible workflow feature, provider, optional field,
  or artifact type;
- **PATCH**: a backward-compatible correction that preserves public contracts.

Pre-release identifiers such as `1.0.0-rc.1` indicate a release candidate.
The canonical software version is `manifest.version` in `nextflow.config`.
Release metadata must be checked against it before tagging.

## Scientific model versions

Scientific contracts evolve independently from the software release:

| Contract/model | Current version |
|---|---:|
| Integration API | 1.0 |
| Evidence Model | 1.1 |
| Harmonization Model | 1.0 |
| Molecular Integration Model | 1.0 |
| Regulatory Interpretation Model | 1.0 |
| Candidate Score | 1.0 |
| Functional Analysis Model | 1.0 |

A HelixForge patch or minor release does not imply a Candidate Score change.
Any change to a scientific model requires its own version bump, regression
fixtures, schema/documentation review, and release-note entry.

## Stability promise for v1

Stable:

- public workflow names;
- required semantics of terminal run manifests;
- published schema identifiers and supported major versions;
- meaning of primary artifacts;
- Candidate Score v1 formula and deterministic tie-break rule.

May evolve compatibly:

- optional manifest fields and metadata;
- new artifact types, reports, figures, and provider implementations;
- additional validation with clearer errors, provided valid v1 inputs remain
  valid and retain their meaning.

Internal and not versioned as public API:

- Nextflow process/module names;
- work-directory structure and task hashes;
- Python package layout;
- intermediate `pipeline_info/` paths;
- implementation details not represented by a public manifest.

Deprecated public behavior must be documented for at least one compatible
release before removal, except when required to address security or data loss.
