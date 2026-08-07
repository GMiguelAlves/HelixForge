# Alignment API

Alignment API version: `1.0`

This contract separates workflow semantics from the selected aligner. RNA-seq
and future ChIP-seq workflows call `REFERENCE_INDEX` and `ALIGNMENT`; they do
not invoke STAR, Bowtie2, HISAT2, or minimap2 processes directly.

## Reference index provider

Input envelope:

```nextflow
tuple val(meta), path(reference), path(annotation), val(index_params)
```

`annotation` is a staged path when the provider uses annotations and an empty
list for providers that do not. A provider must reject a missing annotation
when it is scientifically required.

Required `meta` fields:

- `id`: stable reference identifier;
- `aligner`: provider name, initially `star`;
- `target_dir`: optional legacy-compatible index directory.

Outputs:

```nextflow
artifacts          // tuple(meta, index_directory)
reports            // tuple(meta, checksum_and_build_reports)
versions           // tuple(meta, versions.yml)
execution_metadata // tuple(meta, execution.json)
manifest           // tuple(meta, manifest.json)
status             // tuple(meta, status.json)
```

The reference and annotation are content-tracked inputs. Index parameters are
part of the process script and cache key. A reference or parameter change
therefore invalidates the index and only the alignments consuming it.

## Alignment provider

Input envelope:

```nextflow
tuple val(meta), path(reads), path(reference), path(annotation),
      path(alignment_index), val(alignment_params)
```

Paired reads are represented as a two-element ordered list. Required `meta`
fields are `id`, `aligner`, `dataset`, `sample_id`, and `single_end`.

Every provider exposes these semantic outputs:

```nextflow
aligned_bam        // tuple(meta, coordinate-sorted BAM)
bam_index          // tuple(meta, BAI or CSI)
logs               // tuple(meta, aligner logs and executed command)
statistics         // tuple(meta, mapping and BAM statistics)
versions           // tuple(meta, versions.yml)
execution_metadata // tuple(meta, execution.json)
manifest           // tuple(meta, partial manifest.json)
status             // tuple(meta, status.json)
```

Provider modules retain the common module emissions as `artifacts` (BAM and
index) and `reports` (logs and statistics). The generic `ALIGNMENT` dispatcher
projects these into the semantic channels above.

## Provenance requirements

The execution metadata and partial manifest collectively contain:

- the exact command and configured extra arguments;
- tool versions;
- requested CPUs, memory, and time;
- index path and deterministic index checksum;
- reference path and SHA-256;
- input read SHA-256 values;
- output checksums and elapsed time.

Absolute compatibility paths may differ from staged Nextflow paths in logs.
Regression tests normalize only paths, timestamps, host information, and speed;
mapping counts, percentages, MAPQ, flags, assignments, and BAM records must
remain equivalent.

## Provider selection

`meta.aligner` selects the implementation. Unsupported values fail before a
scientific command is launched. Version 1.0 implements `star`; future Bowtie2,
HISAT2, and minimap2 providers must return the same semantic channels.
