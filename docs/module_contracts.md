# Module contracts

This document defines the interface required for every new native Nextflow DSL2
module in OmicsFlow. The contract standardizes orchestration and provenance; it
does not force unrelated scientific tools to produce the same file types.

Contract version: `1.7`

This contract applies to Trim Galore, FastQC, FASTQ merge, MultiQC, and every
later native module.

## Module layout

Each module must live under `modules/local/<tool>/` and contain:

```text
modules/local/<tool>/
├── main.nf
├── environment.yml
├── meta.yml
├── README.md
└── tests/
```

The process name must be uppercase and unambiguous. Scientific logic must remain
in the tool command; the process may only stage inputs, prepare command-line
arguments, validate expected outputs, and materialize compatibility paths.

## Common channel envelope

Every data item must carry a `meta` map as the first tuple element:

```nextflow
tuple val(meta), path(input_artifacts)
```

Required `meta` field:

- `id`: stable, filesystem-safe identifier for the task.

Optional identity fields should be retained when available:

- `dataset`
- `sample_id`
- `run_accession`
- `single_end`

Tool-specific values may be added to `meta`, but a module must not silently
remove or rename fields received from its caller.

## Inputs

The first input must use the common envelope:

```nextflow
input:
tuple val(meta), path(input_artifacts)
```

Paired or heterogeneous inputs may use multiple `path` elements while keeping
`meta` first:

```nextflow
tuple val(meta), path(read_r1), path(read_r2)
```

Additional parameters must be explicit `val` or `path` inputs. Scientific
parameters must come from the authoritative pipeline configuration or the
calling workflow; modules must not introduce hidden scientific defaults.

Biological identifiers and categorical metadata values must be preserved.
Normalization of versions, prefixes, case, punctuation, or missing values is a
scientific input parameter, never an implicit convenience. A requested
normalization must detect collisions and record the policy in execution
metadata. Invalid numeric values must fail; they must not be replaced with zero.

## Outputs

Modules must expose the following named emissions when applicable:

```nextflow
output:
tuple val(meta), path(primary_artifacts), emit: artifacts
tuple val(meta), path(report_artifacts),  emit: reports, optional: true
tuple val(meta), path(version_file),      emit: versions
tuple val(meta), path(status_file),       emit: status
```

- `artifacts`: primary outputs consumed by downstream processes.
- `reports`: human- or machine-readable reports; optional only when the tool
  genuinely produces no report.
- `versions`: one YAML file describing every scientific executable used.
- `status`: one small JSON completion record for orchestration and provenance.

The `meta` map must be emitted unchanged with every tuple output. Modules that
transform reads still use `artifacts`; the caller assigns the biological role
through `meta` rather than relying on tool-specific channel names.

### Versions format

```yaml
"PROCESS_NAME":
  tool_name: "1.2.3"
```

### Status format

```json
{
  "id": "sample_or_run_id",
  "process": "PROCESS_NAME",
  "status": "complete"
}
```

Primary scientific outputs must retain the names, formats, compression, and
directory contract of the pipeline being migrated. Temporary files must be
written first and atomically renamed when materializing compatibility outputs.

## Process directives

Every module must declare:

```nextflow
tag "${meta.id}"
label 'native_module'
cpus <default>
memory <default>
time <default>
cache 'deep'
maxRetries 2
```

It must also define an `errorStrategy`. Retries should be limited to transient
termination or infrastructure failures; deterministic scientific failures must
terminate immediately. Resource defaults must match the existing pipeline until
a controlled benchmark justifies a change.

Each module must use `publishDir` for lightweight reports, versions, and status
records. Large primary artifacts should remain tracked Nextflow outputs and be
materialized separately only when legacy compatibility requires an exact
external path.

## Software support

Every module must define both:

```nextflow
container params.<tool>_container
conda "${moduleDir}/environment.yml"
```

Requirements:

- Conda package versions must be pinned.
- Docker must use a versioned OCI image, preferably with a recorded digest.
- The same OCI image must work through Singularity or Apptainer.
- Local or Slurm execution without environment management may use the tool on
  `PATH`, but its version must still be recorded.
- Container and Conda versions must represent the same scientific tool release.

Cluster partition, account, and QoS remain profile or site configuration, never
scientific module logic.

## Stub contract

Every module must implement a `stub:` block that:

- creates every required output;
- preserves expected filenames and tuple shape;
- creates syntactically valid small files where practical;
- never invokes scientific software;
- writes `versions` with `stub` values and status `stub`.

## Required tests

Every new module must provide:

1. `stub`: graph compilation and output-contract validation.
2. `integration`: execution on a reduced deterministic dataset.
3. `regression`: comparison with the unchanged legacy implementation.

Regression tests must compare the representation appropriate to each artifact:

- byte checksum for deterministic files;
- decompressed checksum for gzip files with variable headers;
- extracted tables and statistics for ZIP, HTML, or timestamped reports;
- numeric tolerances only when the scientific format requires them.

Test fixtures must be small, versioned, and independent of production data.

## Review checklist

Before a module is accepted, confirm:

- [ ] `meta.id` is present and propagated unchanged.
- [ ] Named emissions follow `artifacts`, `reports`, `versions`, and `status`.
- [ ] Scientific parameters and resources match the legacy implementation.
- [ ] Output names, formats, compression, and compatibility paths are preserved.
- [ ] Conda and OCI versions are pinned and consistent.
- [ ] No `sbatch` or nested scheduler call exists.
- [ ] Stub, integration, and regression tests pass.
- [ ] `nextflow lint` reports no new warnings.
- [ ] Module reuse does not depend on RNA-seq-specific paths or assumptions.

Changes to this contract require a documented contract-version increment and a
migration note for existing native modules.

## Domain contracts

Modules may participate in a stricter domain API in addition to this common
envelope. Domain APIs must define stable semantic roles independently from a
specific tool. The Alignment API is defined in `docs/alignment_api.md`; the
Quantification API is defined in `docs/quantification_api.md`; the Import API
is defined in `docs/import_api.md`; the Differential Expression API is defined
in `docs/differential_expression_api.md`.

The ChIP-seq domain contracts are defined in `docs/chipseq-api.md`. They add
explicit control relationships, biological/technical replicate identity and
separate post-alignment policies for selection, duplicates and blacklist
exclusion.

Contract 1.1 adds `meta.yml`, module-local documentation, tests, and formal
domain contracts. Existing QC modules remain valid under 1.0 and can adopt the
additional layout incrementally; all modules created after 1.1 must use it.

Contract 1.2 adds the independent transcriptome-index and abundance-estimation
roles of the Quantification API. Quantification providers must preserve their
complete native output directory while also projecting stable semantic
channels for downstream workflows.

Contract 1.3 adds aggregation modules. An aggregation item carries a global
`meta` map followed by content-tracked manifests, provider artifacts, sample
metadata, and explicit parameters. Aggregators must expose matrices through
semantic emissions (`counts`, `abundance`, and `lengths`) and must not discover
provider files by reconstructing pipeline-specific directory names. A semantic
role unavailable from a provider is represented in its manifest as
`available: false`; modules must not fabricate scientific values to satisfy an
interface.

Contract 1.4 adds statistical-provider modules. A statistical model and its
contrasts must be separate cache boundaries. Designs and contrasts are explicit
versioned values, while counts, metadata, and their Import manifest are tracked
files. Providers emit common statistical field names without removing
provider-native compatibility files. Unsupported statistical tests must fail
explicitly and must never be approximated silently.

Contract 1.5 adds scientific input integrity. Metadata keys must be non-empty
and unique at their declared granularity. Design, contrasts, expression filter,
fractional-count handling, gene/transcript ID normalization, and stranded count
selection are explicit versioned values. Modules fail on collisions, unmapped
required identifiers, negative counts, and missing design values.
Library protocol and transcript-length correction strategy are also explicit
when transcript abundance estimates feed gene-level inference.

Contract 1.6 adds multi-assay alignment providers and ChIP-seq experiment
identity. Generic Alignment API providers may omit annotation and gene counts
when those roles do not apply, but they must still emit sorted BAM, index,
logs, statistics, versions, execution metadata, manifest and status. ChIP-seq
modules must not hide MAPQ, duplicate, blacklist or peak-type policy inside an
aligner process.

Contract 1.7 adds BAM transformation providers. Selection, duplicate policy,
blacklist exclusion and final index/QC are separate deep-cache boundaries.
Every policy is an explicit value or tracked file; disabled optional stages
still emit a manifest describing the no-op. BAM/reference and blacklist/BAM
contig mismatches fail without automatic renaming. Final BAM providers must
emit integrity evidence, compact read metrics, checksums and a matching index.
