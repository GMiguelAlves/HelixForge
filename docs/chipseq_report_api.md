# ChIP-seq Report/Integration API v1

Report API v1 assembles existing ChIP-seq results into a scientific project
summary. It is a terminal consumer: it cannot schedule or infer an upstream
analysis and receives only versioned manifests plus explicitly declared result
artifacts.

## Input contract

The workflow receives one `chipseq_report_input` JSON document. Its immutable
project envelope contains `project_id`, `dataset`, `genome_id`, and `build`.
`required_components` declares which components must exist. `components`
contains explicit entries with:

- semantic `component` role;
- manifest path;
- zero or more result artifact paths declared by that manifest.

Supported roles are `metadata`, `reference`, `alignment`, `bam`, `peak`,
`peak_qc`, `consensus_idr`, `differential_binding`, `annotation`, `tracks`, and
`provenance`. Multiple manifests may implement a sample-level role. Entries
are associated through manifest type and stable IDs, never file order, glob,
basename convention, or internal module directory.

Artifacts are optional because many compact manifests already contain their
metrics. When an artifact is supplied, its semantic association must be
declared by a manifest; checksums are validated whenever the manifest provides
one. Missing optional metrics remain `null`.

## Component status

Every supported role has exactly one of these report states:

- `available`: complete usable results exist;
- `not_requested`: no result was supplied and the role was not required;
- `not_implemented`: the provider explicitly reports that state;
- `failed`: an upstream result explicitly failed;
- `incomplete`: supplied results are partial, stubbed, or internally mixed.

An absent required component is an error. `not_implemented`, `failed`, and
`incomplete` are never converted to zero. In particular, current IDR requests
are represented as `not_implemented` and do not contribute a region count.

## Identity and compatibility

`REPORT_CONTEXT` validates manifest JSON, supported types and schema versions,
unique `(type,id)` identity, project/dataset, genome/build, record/sample
identity, and incompatible status/version declarations. Missing fields in an
optional historical manifest are recorded as unavailable; conflicting
non-empty values fail.

Sample-level associations use `record_id` and `sample_id`. Group-level results
use dataset, condition, target, genome/build, and declared biological and
technical replicate identities. Controls are represented explicitly. The API
does not infer a treatment/control relationship from names.

## Semantic aggregate

`REPORT_AGGREGATE` produces a provider-neutral object with these ordered
sections:

1. project and metadata;
2. reference;
3. sequencing/QC;
4. alignment;
5. BAM processing;
6. peak calling;
7. Peak QC/FRiP;
8. consensus/IDR;
9. differential binding;
10. annotation;
11. tracks;
12. provenance.

The aggregate retains source manifest IDs, SHA-256 values, statuses, versions,
parameters, commands, execution records, and declared artifact references.
Scientific counts are reported only when present in the manifests or supplied
semantic result files.

## Presentation provider

`REPORT_GENERATOR` is a separate cache boundary. Provider `html_v1` consumes
the semantic aggregate and a presentation specification and emits a
self-contained HTML report with embedded CSS, structured JSON, final manifest,
provenance, versions, and execution metadata. A missing section is rendered as
`Not executed`, while other non-available states retain their exact label.

No PDF or external web asset is part of v1. Adding another renderer must not
change `REPORT_CONTEXT` or `REPORT_AGGREGATE`.

## Cache semantics

Context and aggregate cache keys include the inventory, all supplied manifests,
all supplied semantic artifacts, and their identities. Presentation options
enter only the generator task. Consequently, a layout change invalidates only
`REPORT_GENERATOR`; a changed downstream manifest invalidates the report graph
without scheduling scientific producers.

`--chipseq_run_mode report --chipseq_native_report true` requires
`--chipseq_report_input_manifest`. Setting `--chipseq_native_report false`
invokes the unchanged legacy report step. `full` remains unchanged.

This contract defines architecture and executable validation only. It does not
claim scientific equivalence to the legacy report.
