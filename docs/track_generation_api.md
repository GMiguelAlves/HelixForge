# Track Generation API v1

Track Generation API v1 converts manifest-identified `FINAL_BAM` artifacts into
genome-browser tracks. It consumes already processed BAMs and never repeats
alignment, MAPQ selection, duplicate policy, blacklist exclusion, peak calling,
or another upstream analysis.

## Input inventory

The dedicated workflow receives one versioned `track_generation_input`
inventory. It contains one reference envelope and one or more records. Every
record carries:

- `record_id`, `sample_id`, dataset, condition, target, control role, and
  biological/technical replicate identity;
- a final BAM, matching BAI, and `type=bam_final` manifest;
- explicit genome/build inherited from the reference envelope.

The reference envelope contains FASTA, a reference manifest, `genome_id`, and
build. Paths are launch-time locations; scientific association is established
only after manifest IDs and checksums are validated. File order, glob order,
basenames, and first/second channel position are forbidden identity sources.

When aggregate tracks are enabled, v1 groups non-control records by the
explicit tuple `(dataset, condition, target, genome_id, build)`. Individual
tracks are generated for every record, including controls. Aggregate tracks do
not subtract, divide by, or otherwise compare a treatment with its control.

## Scientific parameters

| Field | v1 values | Legacy-compatible default |
|---|---|---|
| `provider` | `deeptools_bamcoverage_v1` | same |
| `track_format` | `bigwig` | `bigwig` |
| `bin_size` | integer > 0 | `10` |
| `normalization` | `CPM`, `RPGC` | `CPM` |
| `effective_genome_size` | null or integer > 0 | null; required for RPGC |
| `scale_factor` | `1.0` | `1.0` |
| `extend_reads` | `false` | `false` |
| `fragment_mode` | `reads` | `reads` |
| `strand` | `unstranded` | `unstranded` |
| `additional_filters` | `none` | `none` |
| `aggregate_tracks` | boolean | `true` |
| `aggregate_scope` | `condition_target` | `condition_target` |

Unsupported parameters fail. They are never ignored. `RPGC` requires an
explicit effective genome size; the provider does not guess it. V1 intentionally
does not expose the broader bamCoverage option catalog.

## Scientific meaning

The primary track is read-based, unstranded binned coverage from a semantically
final BAM. Paired-end data are not explicitly extended or converted to a new
fragment representation. Mapped/unmapped, secondary/supplementary, duplicate,
MAPQ, and blacklist behavior is exactly the upstream final-BAM policy recorded
in its manifest. The provider adds no hidden read filters.

For an aggregate request, `samtools merge` combines only explicitly listed,
compatible final BAMs. It does not deduplicate or filter them again. The merged
BAM and BAI are provider auxiliary artifacts, not a new `FINAL_BAM` API result.

## Process boundaries

`TRACK_CONTEXT` validates inventory-derived metadata, stable IDs, BAM/BAI and
final-BAM manifests, reference manifest/build, declared checksums, BAM/reference
contigs, format, parameters, group membership, and output-ID collisions.

`TRACK_PROVIDER` dispatches provider-neutral requests. The first implementation
is `deeptools_bamcoverage_v1`, using pinned deepTools `bamCoverage` and samtools.
It emits:

- primary BigWig;
- optional merged BAM/BAI for explicit aggregate groups;
- command/log and provider metrics;
- versions, execution metadata, provenance, partial manifest, and status.

`TRACK_STATISTICS` derives track size, contigs, covered bases, finite-value
depth summary, bins, source read counts, scale, and parameters from the BigWig
and documented provider metrics. Unavailable values remain null.

`TRACK_AGGREGATE` joins provider/statistics manifests by track ID and emits a
provider-neutral inventory of tracks, metadata, statistics, versions,
provenance, manifest, and status. It preserves all source record/sample IDs,
condition, replicate identity, BAM checksums, reference, and build.

## Cache and workflow semantics

Every boundary uses deep cache. BAM, BAI, final-BAM manifest, reference,
reference manifest, metadata identity, provider/version, normalization, bin
size, scaling, unit, and all parameters participate in the key. Track changes
cannot invalidate upstream tasks because `--chipseq_run_mode tracks` consumes
only external native manifests.

The dedicated `tracks` mode always invokes this API. Native `full` supplies the
final-BAM and Reference Bundle channels directly to the same Track API.

The API has deterministic contract and reduced runtime validation. Reviewed
biological equivalence of generated BigWigs remains part of the broader
benchmarking scope.
