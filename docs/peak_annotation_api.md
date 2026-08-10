# Peak Annotation API v1

Peak Annotation API v1 associates an explicitly identified peak set with a
user-supplied genomic annotation. It is provider-neutral: downstream consumers
read semantic artifacts and manifests, never provider-specific filenames.

## Input contract

One request represents one peak set and contains:

- a Peak Calling (`type=peak_calling`) or Consensus (`type=consensus`) manifest;
- the semantic BED, narrowPeak, or broadPeak artifact referenced by that manifest;
- a reference manifest or equivalent reference envelope;
- a tracked GTF or GFF annotation;
- metadata containing `record_id` (replicate peaks) or the preserved source
  record IDs (consensus peaks), sample IDs, dataset/experiment, target,
  organism, and explicit genome/build;
- an annotation mode and all scientific parameters.

Association is exclusively by manifest identity. Channel order, globs, file
basenames, and inferred filename tokens are forbidden identity sources. The
context must reject missing/duplicate IDs, incompatible peak and manifest
types, output-ID collisions, malformed coordinates, missing contigs, and
genome/build or seqname mismatches. It must not rename contigs, lift
coordinates, strip ID versions, or repair annotations silently.

## Scientific parameters

The versioned parameter object contains:

| Field | v1 values | Compatibility default |
|---|---|---|
| `mode` | `overlap_priority` | `overlap_priority` |
| `overlap_mode` | `any` | `any` |
| `promoter_upstream` | integer >= 0 | `2000` |
| `promoter_downstream` | integer >= 0 | `500` |
| `max_tss_distance` | null or integer >= 0 | null |
| `feature_priority` | ordered unique list | promoter, exon, intron, downstream, gene |
| `gene_assignment` | `first` or `all` | `first` |
| `strand_aware` | boolean | `false` |
| `intergenic_policy` | `retain` or `drop` | `retain` |

The provider implemented in v1 supports `overlap_priority`, `any`, and
`strand_aware=false`. `max_tss_distance` is recorded but must be null because
the legacy method does not perform nearest-TSS assignment. Unsupported values
fail explicitly.

The defaults reproduce the relevant legacy definition: GTF/GFF features are
converted from one-based closed coordinates to zero-based half-open intervals;
promoter and downstream windows are strand-specific; any overlap assigns a
category; later categories in the legacy loop overwrite earlier ones. The
equivalent explicit priority is therefore promoter > exon > intron >
downstream > gene > intergenic. `gene_assignment=first` selects the first
feature after deterministic genomic sorting. These are compatibility defaults,
not a universal biological definition.

## Provider contract

`PEAK_ANNOTATOR` consumes only a validated request, staged peaks, and staged
annotation. A provider emits:

- `annotated_peaks.tsv` with peak identity, original coordinates, category,
  associated gene IDs, and distance-to-TSS when defined;
- `peak_gene_associations.tsv`, one row per reported peak/gene association;
- provider auxiliary files and command/report metadata;
- `versions.yml`, execution metadata, provenance, manifest, and status.

The initial provider is `python_interval_v1`. It implements the explicit legacy
overlap model with Python standard-library interval indexing. It does not
invoke the legacy R wrapper and does not submit scheduler jobs.

## Statistics contract

`PEAK_ANNOTATION_STATISTICS` derives metrics exclusively from the provider
semantic tables. It reports total/annotated/unassociated peaks, category
distribution, unique genes, mean genes per peak, distance-to-TSS distribution
when populated, peaks by chromosome, and by `record_id` when available.
Unavailable scientific values are represented as null or an empty
distribution, never fabricated.

## Aggregate and output contract

`PEAK_ANNOTATION_AGGREGATE` normalizes one or more provider manifests into:

- annotated peaks and peak-to-gene association tables;
- statistics JSON/TSV;
- preserved metadata, `record_id`, sample IDs, and peak-set origin;
- versions, execution metadata, provenance, a partial aggregate manifest, and
  explicit `complete`, `complete_empty`, or `stub` status.

The per-set manifest has `schema_version=1.0`,
`type=peak_annotation`, stable `id`, `source_type`, `source_id`, genome/build,
provider/version, parameters, input checksums, semantic artifact roles, and
status. The aggregate has `type=peak_annotation_aggregate` and references every
per-set manifest by ID and checksum.

## Workflow and cache semantics

`--chipseq_run_mode annotation --chipseq_native_peak_annotation true` consumes
external, tracked manifests and their referenced artifacts. It never invokes
peak calling or Differential Binding. The legacy annotation step remains the
fallback when the flag is false. `full` retains its current behavior.

Peak/reference manifests, peaks, GTF/GFF, metadata identity, genome/build,
provider version, and all annotation parameters are deep-cache inputs. A
change invalidates only context, annotation, statistics, and aggregation for
the affected peak set.

Peak Annotation API v1 does not claim scientific equivalence. Biological
regression against the legacy implementation is deferred to the consolidated
production-readiness validation.
