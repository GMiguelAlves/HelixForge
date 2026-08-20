# Integration API v1

Contract identifier: `helixforge.integration_api`  
Contract version: `1.0`

The Integration API is the semantic boundary between completed assay workflows
and the future Molecular Evidence Integration Engine. A terminal manifest says
what a scientific product means, which reference and experimental context it
belongs to, and how it was produced. It is not an inventory of a result
directory.

## Boundary

```text
native RNA-seq DAG ──> rnaseq_run_manifest.json ─┐
                                                ├─> Evidence Providers
native ChIP-seq DAG ─> chipseq_run_manifest.json ┘
```

The manifests are assembled only from channels, metadata and artifacts already
known to the active DAG. The assembler never searches `results/`, interprets a
glob, or extracts a contrast, mark or sample from a filename.

## Common models

### Run manifest

The run envelope records the workflow, stable run identity, HelixForge and
Nextflow versions, Git commit, profile and whether the producer is HelixForge
or an external implementation. `created_at` is optional/volatile and is ignored
by equivalence tests.

### Reference

`reference_id` is the integration identity. `organism`, `genome_id` and the
assembly are recorded independently from display names and physical files.
Each available FASTA, annotation, transcriptome, blacklist or chromosome-size
resource has a typed location and optional SHA-256. Existing Reference Bundle
manifests are projected into this model; no reference file is modified.

RNA and ChIP manifests are compatible only when `reference_id`, `genome_id`,
assembly (when both declare it) and organism agree. Missing identity is an
error, not a request to infer it from a basename.

### Artifact

Every entry uses the common object in
`schemas/integration/definitions/artifact.schema.json`. The controlled v1
taxonomy is deliberately small: expression/count matrices, differential
expression, BAMs, peaks, Peak QC, consensus/IDR, differential binding,
peak-gene annotation, signal tracks and terminal reports.

An artifact separates:

```text
location                 semantic type                scientific context
path/URI/base semantics  assay/entity/reference      sample/contrast/mark
```

`source.type` is `helixforge` or `external`, so external RNA or ChIP providers
can create the same contract. `provenance` names the producing workflow/process
and source manifests/artifacts without copying the full Nextflow trace.

### Contrast

RNA and ChIP share `contrast_id`, `factor`, `numerator`, `denominator`, label,
formula and covariates. A complex design may retain its formula and metadata,
but v1 never fabricates numerator/denominator values. Contrast IDs are stable
semantic identifiers and cannot be recovered from filenames.

## Path rules

Locations have one explicit kind:

- `manifest_relative`: resolved from the terminal manifest directory;
- `producer_relative`: resolved from the named upstream producer manifest;
- `absolute`: an explicitly non-portable local/NFS path;
- `uri`: a URI managed outside the local filesystem.

Consumers must not silently reinterpret one kind as another. A deployment may
relocate producer-relative artifacts by supplying the corresponding upstream
manifest location. The filesystem validator accepts an explicit base-path map;
schema and semantic validation do not require local files to exist.

## Validation layers

`bin/validate_integration_manifest.py` exposes three independent checks:

1. `schema`: JSON Schema Draft 2020-12 structure;
2. `semantic`: unique IDs, valid references and contrasts, assay/type rules,
   required ChIP marks and control relationships;
3. `filesystem`: resolves local paths and verifies existence/checksums.

Compatibility validation compares two already-valid run manifests and reports
reference, genome/assembly and organism incompatibilities. It does not perform
scientific integration.

## Version policy

Breaking field or semantic changes increment the major Integration API version.
Optional additive fields increment the minor version. Patch releases may only
clarify validation or documentation without changing accepted meaning. A
consumer must reject an unsupported major version.

Examples are in `assets/examples/rnaseq_run_manifest.example.json` and
`assets/examples/chipseq_run_manifest.example.json`; both are exercised by the
contract tests.

## Evidence-provider and integration boundary

The terminal manifest describes products of an assay run. Standardized RNA and
ChIP Evidence Providers consume that contract plus explicitly staged artifacts,
as specified by the [Evidence Model v1](evidence_model.md). The next native
boundary performs explicit ID/context/contrast/mark harmonization and creates a
Master Molecular Evidence Table. See
[Cross-Assay Harmonization and Molecular Integration v1](cross_assay_integration.md).
Regulatory classes, candidate scores and functional analysis remain later-stage
consumers.
