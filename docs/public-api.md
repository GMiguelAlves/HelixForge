# HelixForge v1 public surface

This document identifies what users and external consumers may rely on in v1.
Anything not listed as public is an implementation detail.

## PUBLIC / STABLE

### Workflows

- `--workflow rnaseq`
- `--workflow chipseq`
- `--workflow integrative`
- `--workflow all`

### Primary invocation and configuration

- `nextflow run . --workflow <name> -profile <profile>`;
- `--outdir`;
- `--rnaseq_config` and `--chipseq_config`;
- `--rna_manifest` and `--chip_manifest` for independent Integrative runs;
- versioned RNA DE, ChIP differential-binding, annotation, track, report, and
  Integrative policy/specification inputs documented in the user guide.

The complete parameter inventory is machine-readable in
`nextflow_schema.json`. A parameter becomes stable only when documented as a
supported user input; container overrides, queue selectors, test controls, and
provider implementation switches are advanced configuration.

### Terminal contracts

- `rnaseq_run_manifest.json`;
- `chipseq_run_manifest.json`;
- `integrative_run_manifest.json`;
- JSON Schemas under `schemas/integration/`;
- Evidence Model 1.1 and schemas under `schemas/evidence/`;
- Harmonization/Molecular Integration, Interpretation, Functional,
  Visualization, and Report manifests documented in the scientific reference.

Published `$id` values and relative `$ref` relationships are contract
identifiers. Their current mixed GitHub/helixforge.dev namespaces are retained
for compatibility and must not be rewritten cosmetically.

### Primary output semantics

Stable meaning is attached to artifact types and terminal-manifest entries, not
to every intermediate directory. Primary reports, gene/peak results,
candidate ranking, references, provenance, and checksums retain their documented
scientific meaning.

## PUBLIC / EXPERIMENTAL

- STAR as an optional RNA Alignment provider; Salmon is the certified
  production quantification path;
- Apptainer/Singularity and Conda profiles until they are certified on a
  supported site;
- externally authored Integration API manifests. The schema is public, but
  format-specific external adapters are not yet supplied;
- standalone ChIP re-entry modes that consume annotation, track, or report
  inventories remain supported but may gain compatible validation.

Experimental interfaces may change before a later stable declaration. Changes
must still be documented and must not silently alter scientific models.

## INTERNAL

- all process and subworkflow names;
- `modules/local/`, `subworkflows/local/`, and Python package organization;
- work directories, task hashes, cache database, and `pipeline_info/` layout;
- module `.done`, log, and versions filenames;
- helper scripts not named in the user or developer guide;
- resource labels and scheduler implementation.

## HISTORICAL

Migration audits, legacy mappings, retirement documents, golden baselines, and
the tags `rnaseq-legacy-v1.0.0`, `chipseq-legacy-v1.0.0`, and
`integrative-legacy-v1.0.0` are preserved for audit and regression. They are
not executable fallbacks in current workflows.

See [Versioning and stability](versioning.md) for compatibility rules and
[Terminal manifests](terminal_manifests.md) for artifact semantics.
