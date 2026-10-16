# Alignment API

Alignment API version: `1.1`

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
- `aligner`: provider name, currently `star` or `bowtie2`;
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

### Reusing a Bowtie2 index

ChIP-seq accepts a verified index independently of its original Nextflow workdir:

```bash
nextflow run . --workflow chipseq --chipseq_run_mode alignment \
  --chipseq_bowtie2_prebuilt_index /path/to/bowtie2_index \
  --chipseq_bowtie2_prebuilt_index_manifest /path/to/reference.manifest.json
```

Both options are required together. Keep the configured index-prefix basename
and build arguments identical to those in the supplied manifest. The generic
`REFERENCE_INDEX` envelope also accepts `prebuilt_index` and `prebuilt_manifest`
in its Bowtie2 `index_params` map; these become declared staged `path` inputs
to `BOWTIE2_INDEX_VALIDATE`, not untracked files used by a value-only task.

The enhanced `BOWTIE2_INDEX` publishes schema 1.2 manifests under
`pipeline_info/native_alignment/bowtie2_index/`. Preserve that manifest beside
the six published index shards. It records the FASTA SHA-256, optional genome
ID, basename, Bowtie2 version, tokenized build arguments and all six file hashes.
`bundle_sha256` is independent of the bundle directory name. The legacy `sha256`
field is retained on build manifests; use the portable bundle digest for reuse.

Reuse requires exact Bowtie2 build/runtime version equality, matching reference
identity and parameters, and exactly one complete six-shard `.bt2` or `.bt2l`
set. This conservative compatibility policy does not assert that other versions
are inherently incompatible. Missing, mixed, corrupt, old schema 1.1 or stub
bundles fail validation; they never trigger an automatic build. Historical
manifests lack the necessary provenance and must not be silently upgraded.

A valid supplied bundle schedules validation but no `BOWTIE2_INDEX` task, even
in a fresh execution without `-resume`. Validation may reread and hash the index;
that is not index reconstruction. The task-local alias does not modify or
republish the external index. Validation reports record source-manifest checksum,
compatibility policy, runtime version, requested resources and elapsed time.

Without these options, existing build/cache behavior remains. Existing files at
an output prefix alone are never treated as proof of compatibility. Updating
the new Python bundle helper participates in both tasks' cache keys.

Bowtie2 specifies six `.bt2` files, or `.bt2l` for a large index; see the
[official manual](https://bowtie-bio.sourceforge.net/bowtie2/manual.shtml#the-bowtie2-build-indexer).

The production RNA-seq Salmon path already has the analogous explicit
`salmon_prebuilt_index`/`salmon_prebuilt_index_manifest` branch; supplying a valid
bundle routes to `SALMON_INDEX_VALIDATE`, not `SALMON_INDEX`. See the
[Quantification API](quantification_api.md#reusing-a-prebuilt-salmon-index).

This feature does not reuse BAMs across independent run sets and does not alter
trimming, alignment arguments, peak calling, DB or downstream scientific policy.

Input envelope:

```nextflow
tuple val(meta), path(reads), path(reference), path(annotation),
      path(alignment_index), val(alignment_params)
```

Paired reads are represented as a two-element ordered list. Required `meta`
fields are `id`, `aligner`, `dataset`, `sample_id`, and `single_end`.

STAR owns `genomeDir`, reads, threads, output prefix/type, and `GeneCounts`.
`STAR_EXTRA_ARGS` cannot override those arguments. Multimapping, MAPQ and other
STAR defaults remain unchanged until a dataset-backed comparison justifies a
new policy. Downstream STAR import must explicitly choose unstranded, forward,
or reverse GeneCounts according to the library protocol.

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

Bowtie2 owns index prefix, reads, threads and SAM output. Its provider pipes the
unaltered alignments through samtools view and coordinate sort, then creates an
index and descriptive statistics. MAPQ/flag filtering, duplicate policy and
blacklist exclusion are deliberately outside the Alignment API.

## Provider selection

`meta.aligner` selects the implementation. Unsupported values fail before a
scientific command is launched. Version 1.0 implemented STAR; version 1.1 adds
Bowtie2 for ChIP-seq. Future HISAT2 and minimap2 providers must return the same
semantic channels.

Alignment is independent from transcript-abundance estimation. Salmon and
future abundance providers implement the separate
[Quantification API](quantification_api.md). `rnaseq_analysis_mode=both` fans
FASTQs into both APIs without introducing a STAR-to-Salmon dependency.
