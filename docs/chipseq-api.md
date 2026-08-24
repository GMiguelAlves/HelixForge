# ChIP-seq APIs

ChIP-seq API suite version: `0.9`

These contracts define semantic roles independently from organism, aligner,
peak caller and historical directory names. The suite covers metadata, QC,
Bowtie2 alignment, BAM processing, MACS3 peak calling, FRiP/Peak QC, Consensus
or optional IDR, Differential Binding, Peak Annotation, Track Generation and
terminal Report/Integration APIs.

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

The normalized record shape is published as
`schemas/chipseq-metadata-v0.1.schema.json`; a tabular example is available at
`assets/chipseq_metadata.example.tsv`.

Controls may be referenced by an exact `record_id` or by a unique `sample_id`,
must exist and must be marked as a control. IP/control pairs must share dataset,
genome build, organism and layout. The validator does not infer controls by
file name or row order and rejects ambiguous sample-level associations.

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

## BAM processing APIs

Post-alignment stages are independent cache boundaries:

1. `BAM_SELECT`: explicit MAPQ and SAM-flag policy;
2. `BAM_DUPLICATES`: `none`, `mark`, or `remove`, with tool and metrics;
3. `BAM_BLACKLIST`: optional interval exclusion against a tracked BED;
4. `BAM_INDEX_QC`: index, quickcheck, flagstat, idxstats and stats;
5. optional future contig/fragment filters, only after a scientific decision.

The implemented graph is selection → duplicate policy → optional blacklist →
final index/QC. Each emits reports, versions, execution metadata, manifest and
status. Policies are explicit cache inputs; a module may not silently adopt the
legacy defaults. Full details are in `docs/native-chipseq-bam-processing.md`.

## Peak Calling API v1

```text
Inputs:  IP meta + treatment BAM/BAI + optional matched control BAM/BAI
         explicit genome/effective size + explicit peak type + parameters
Outputs: semantic peaks + caller-native artifacts + statistics + logs
         versions + execution metadata + manifest + status
```

`PEAK_CALLING_CONTEXT` validates and gates the graph, `PEAK_CALLING` dispatches
providers, MACS3 3.0.4 is the first implementation, and
`PEAK_CALLING_AGGREGATE` validates/normalizes semantic artifacts. `peak_type`
must be `narrow` or `broad`; no antibody/target inference is permitted. See
`docs/peak_calling_api.md` for the complete contract.

## Peak QC API v1

`PEAK_QC_CONTEXT` safely associates one final treatment BAM with its semantic
peak set and explicit scientific specification. `FRIP` counts eligible reads or
fragments overlapping the temporary peak union; `PEAK_STATISTICS` reports
caller-neutral distributions; `PEAK_QC_AGGREGATE` emits one row per replicate.

The denominator, MAPQ/SAM flags, duplicate handling, overlap semantics and
blacklist policy are explicit and recorded. The API does not calculate a pooled
FRiP, consensus, IDR, replicate rank, or differential binding. See
`docs/peak_qc_api.md` for the formal definition.

## Consensus / IDR API v1

Technical records and biological replicates remain distinct. The native API
groups only records with matching dataset, experiment, condition, target,
genome, peak type and compatible caller. It never associates artifacts by file
order or glob. Biological mode requires technical records to have been merged
upstream; technical mode explicitly preserves them.

`union`, `intersection`, and `replicate_support` use BEDTools `multiinter`
atomic segments and retain the supporting replicate IDs. Scores, summits and
significance values are preserved as evidence rather than fabricated for the
consolidated intervals. IDR is a separate statistical provider: it validates
exactly two premerged biological narrowPeak replicates, an explicit threshold
and rank metric, and emits filtered peaks plus local/global IDR evidence.
See `docs/consensus_idr_api.md`.

## Modes and current behavior

| Mode | Behavior in 0.9 |
|---|---|
| `qc` | metadata validation + raw FastQC + MultiQC |
| `alignment` | native QC + Bowtie2 index/alignment |
| `post_alignment` | native QC + alignment + final BAM processing |
| `peaks` | native QC + alignment + BAM processing + per-replicate MACS3 |
| `peak_qc` | native peaks + per-replicate FRiP/peak statistics + QC aggregation |
| `consensus` | native Peak QC + explicit union/intersection/replicate-support provider |
| `idr` | native IDR 2.0.4.2 provider with normalized peaks, evidence, plot and provenance |
| `differential_binding` | native Consensus + featureCounts provider + explicit DESeq2 model/contrasts |
| `annotation` | external Peak/Consensus manifest + native annotation provider/statistics/aggregate; no upstream rerun |
| `tracks` | external FINAL_BAM inventory + native deepTools provider/statistics/aggregate; no upstream rerun |
| `report` | external semantic manifest inventory + native context/aggregate/HTML+JSON provider; no upstream rerun |
| `full` | native single-session QC → Bowtie2 → BAM → MACS3 → Peak QC → Consensus → Differential Binding → Annotation/Tracks → Report |

`full` and every dedicated stage mode now resolve exclusively to native
providers. The retired implementation is available only from the immutable
`chipseq-legacy-v1.0.0` tag.

## Differential Binding API v1

`DB_PREFLIGHT` groups compatible semantic Consensus or IDR sets across conditions,
validates one premerged biological sample per model column, builds the explicit
comparison universe and emits separate count/model/contrast specs.
`PEAK_COUNTING_PROVIDER` dispatches featureCounts, `DESEQ2_DB_MODEL` fits one
raw-count Wald model, `DESEQ2_DB_CONTRAST` fans out named directions and
`DB_AGGREGATE` produces the downstream manifest. See
`docs/differential_binding_api.md`. No biological validation is claimed.

## Peak Annotation API v1

An explicit Peak Calling or Consensus manifest is joined with a reference
manifest, FASTA, and GTF/GFF. Mode, overlap, promoter windows, feature priority,
gene assignment, strand handling, intergenic policy, genome/build, and provider
are versioned values. The initial `python_interval_v1` provider emits annotated
peaks and peak-to-gene associations; metrics and aggregation are separate cache
boundaries. See `docs/peak_annotation_api.md`.

## Track Generation API v1

An explicit inventory joins `FINAL_BAM`/BAI manifests with reference identity
and a small, versioned coverage specification. `TRACK_CONTEXT` rejects hidden
or unsupported behavior, `TRACK_PROVIDER` dispatches deepTools bamCoverage,
`TRACK_STATISTICS` derives generic metrics, and `TRACK_AGGREGATE` publishes a
provider-neutral inventory. All records receive individual tracks; aggregates
contain explicitly grouped non-controls and perform no treatment/control
subtraction. See `docs/track_generation_api.md`.

## Report/Integration API v1

`REPORT_CONTEXT` validates an explicit project inventory and upstream semantic
manifests, including optional and non-available component states.
`REPORT_AGGREGATE` builds ordered provider-neutral scientific sections, while
`REPORT_GENERATOR` renders self-contained HTML and structured JSON as a
renderer-only cache boundary. No module scans producer directories or invokes
an upstream stage. See `docs/chipseq_report_api.md`.
