# ChIP-seq APIs

ChIP-seq API version: `0.1`

These contracts define semantic roles independently from organism, aligner,
peak caller and legacy directory names. Version 0.1 implements metadata, raw QC
and Bowtie2 alignment. Later APIs are defined now to prevent monolithic BAM and
peak processes, but are not yet native providers.

## Common experiment metadata

Each sequencing record carries a `meta` map. Required fields are:

- `id`: unique, filesystem-safe execution record identifier;
- `sample_id`: biological library identifier;
- `dataset`, `condition`, `layout`, `single_end`;
- `biological_replicate`, with `technical_replicate` kept separately;
- `is_control`, `control_id` for IP records, `genome_id`.

Optional fields include `run_accession`, `lane`, `batch`, `assay`, `antibody`,
`target`, `organism`, `treatment` and `peak_type`. `mark_or_factor` is accepted
as a legacy alias for `target`; `replicate` is accepted as a legacy alias for
`biological_replicate`. Normalized metadata retain both source and semantic
values. Multiple rows may share a sample only when they have distinct run/lane
identity and compatible biological attributes.

Controls are referenced by `sample_id`, must exist and must be marked as a
control. IP/control pairs must share dataset and genome build. The metadata
validator does not infer controls by file name or row order.

## Reference API

Input roles:

```text
meta(reference_id, genome_id, organism, index_provider)
FASTA
optional GTF/GFF
optional blacklist BED
index parameters
```

Output roles are reference checksums, chromosome metadata, provider index,
versions, execution metadata and a partial manifest. Chromosome names, contig
counts and genome builds are never hard-coded. Bowtie2 indexing consumes only
FASTA; annotation and blacklist remain independently tracked inputs for stages
that require them.

## QC API

Raw QC receives `tuple(meta, FASTQ)` and uses the existing generic `FASTQC`
module once per FASTQ. Generic `MULTIQC` consumes a collected set of compatible
reports. Trimming is an explicit optional transformation, not an implicit QC
requirement. The first native ChIP-seq foundation performs raw QC only; fastp
and a controlled ChIP-seq trimming policy remain future work.

## Alignment API

The existing generic Alignment API is extended with provider `bowtie2`.

```nextflow
tuple val(meta), path(reads), path(reference), path(annotation),
      path(alignment_index), val(alignment_params)
```

Bowtie2 emits a coordinate-sorted BAM and BAI, exact command/logs, flagstat,
idxstats, samtools stats, MAPQ distribution, versions, execution metadata,
manifest and status. It supports single- and paired-end reads. Alignment does
not apply MAPQ, duplicate, blacklist, mitochondrial or fragment filters.

## BAM processing APIs (contract only)

Post-alignment stages will be independent cache boundaries:

1. `BAM_SELECT`: explicit MAPQ and SAM-flag policy;
2. `BAM_DUPLICATES`: `keep`, `mark`, or `remove`, with tool and metrics;
3. `BAM_BLACKLIST`: optional interval exclusion against a tracked BED;
4. `BAM_INDEX_QC`: index, quickcheck, flagstat, idxstats and stats;
5. optional future contig/fragment filters, only after a scientific decision.

Each consumes and emits `tuple(meta, BAM, BAI)` plus reports, versions,
execution metadata, manifest and status. Policies must be explicit inputs; a
module may not silently adopt the legacy defaults.

## Peak Calling API (contract only)

```text
Inputs:  IP meta + treatment BAM/BAI + optional matched control BAM/BAI
         explicit genome/effective size + explicit peak type + parameters
Outputs: semantic peaks + caller-native artifacts + statistics + logs
         versions + execution metadata + manifest + status
```

`PEAK_CALLER` will dispatch providers such as MACS3 without exposing
caller-specific filenames downstream. `peak_type` must be `narrow` or `broad`;
the native API will not infer it from an antibody/target string. Missing
controls and effective genome-size policy must be explicit, versioned choices.

## Replicate and consensus API (contract only)

Technical records and biological replicates remain distinct. Peak calling is
defined per biological replicate. A future consensus provider must declare its
support rule, minimum biological replicates, overlap semantics and sample order
in a manifest. The legacy union is available only through fallback. IDR is a
possible future provider, not an implicit requirement.

## Modes and implementation state

| Mode | Native state in 0.1 |
|---|---|
| `qc` | metadata validation + raw FastQC + MultiQC |
| `alignment` | native QC + Bowtie2 index/alignment |
| `peaks` | legacy fallback |
| `full` | legacy fallback |

The fallback remains the complete legacy graph. Native and legacy outputs must
not be mixed within one analysis without an explicit manifest boundary.

