# Quantification API

Quantification API version: `1.0`

This contract separates transcript-abundance estimation from a specific tool.
RNA-seq and future workflows call `TRANSCRIPTOME_INDEX` and `QUANTIFICATION`;
they do not invoke Salmon, Kallisto, RSEM, featureCounts, or later providers
directly.

## Transcriptome index provider

Input envelope:

```nextflow
tuple val(meta), path(transcriptome), val(index_params)
```

Required `meta` fields:

- `id`: stable reference identifier;
- `quantifier`: provider name, initially `salmon`;
- `target_dir`: optional legacy-compatible index directory.

`index_params` contains only provider parameters that affect index content.
For Salmon 1.10.3 this is `kmer_size`, sourced from `SALMON_KMER_SIZE`.

Outputs:

```nextflow
artifacts          // tuple(meta, transcriptome_index_directory)
reports            // tuple(meta, checksum_and_build_reports)
versions           // tuple(meta, versions.yml)
execution_metadata // tuple(meta, execution.json)
manifest           // tuple(meta, partial manifest.json)
status             // tuple(meta, status.json)
```

The transcriptome and index parameters are content-tracked inputs. Providers
must use deep cache and must not skip index construction merely because an
unverified directory exists at `target_dir`. A successful cached task may
republish its verified index at that compatibility path.

## Quantification provider

Input envelope:

```nextflow
tuple val(meta), path(reads), path(transcriptome),
      path(transcriptome_index), val(quantification_params)
```

Paired reads are an ordered two-element list. Required `meta` fields are `id`,
`quantifier`, `dataset`, `sample_id`, `single_end`, and `target_dir`.

Required parameters are explicit. Salmon 1.10.3 receives `lib_type` and
`validate_mappings`; no scientific default may be introduced inside the
provider.

Every provider exposes these semantic outputs:

```nextflow
quantification     // tuple(meta, primary abundance table)
command_info       // tuple(meta, provider command metadata)
library_format     // tuple(meta, inferred/observed library-format metadata)
auxiliary          // tuple(meta, provider auxiliary directory)
logs               // tuple(meta, command and provider logs)
statistics         // tuple(meta, normalized quantification statistics)
versions           // tuple(meta, versions.yml)
execution_metadata // tuple(meta, execution.json)
manifest           // tuple(meta, partial manifest.json)
status             // tuple(meta, status.json)
```

Provider modules also retain the common `artifacts` and `reports` emissions.
An implementation that cannot produce one of the semantic roles must emit a
documented empty artifact with a stable format; callers must never branch on a
tool-specific filename.

For Salmon the primary table is `quant.sf`, command metadata is
`cmd_info.json`, library-format metadata is `lib_format_counts.json`, and the
auxiliary directory is `aux_info/`. The complete native output directory is
published unchanged at `QUANT_DIR/<dataset>/<sample_id>` so the existing
tximport wrapper continues to resolve `quant.sf` without modification.

## Provenance requirements

The execution metadata and partial manifest collectively record:

- the exact executed command and scientific parameters;
- requested CPUs, memory, and time;
- tool version and pinned OCI image;
- transcriptome SHA-256;
- deterministic index checksum;
- input-read SHA-256 values;
- primary-output checksums;
- start, end, and elapsed time.

Provider-native files are never edited to normalize paths or timestamps.
Regression tests may normalize absolute paths, timestamps, host information,
and speed. Transcript identifiers, `Length`, `EffectiveLength`, `TPM`,
`NumReads`, fragment counts, mapping rates, inferred library type, and other
scientific statistics must remain equivalent.

## Provider selection

`meta.quantifier` selects the implementation. Unsupported values fail before a
scientific command is launched. Version 1.0 implements `salmon`; Kallisto,
RSEM, featureCounts, and future providers must return the same semantic roles.

Alignment and quantification are independent APIs. A workflow may fan the same
FASTQs into both APIs, and a quantifier must not require an Alignment API output
unless that provider explicitly implements alignment-based quantification.
