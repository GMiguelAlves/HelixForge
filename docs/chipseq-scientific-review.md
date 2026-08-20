# ChIP-seq scientific review

This document records the decisions made during the native migration. Its
foundation-era validation notes are historical; current retirement evidence is
in `docs/chipseq-legacy-retirement.md`.

## Decisions retained for the first native foundation

- Bowtie2 is the first alignment provider and starts with the configured legacy
  `--very-sensitive` arguments.
- Single- and paired-end records are supported.
- FASTQ identity, reference FASTA, genome build and control relationships are
  explicit tracked inputs.
- Alignment outputs are coordinate-sorted and indexed and include samtools
  statistics. No downstream filtering is hidden inside alignment.

These choices preserve the observable alignment contract without declaring the
legacy downstream policy scientifically optimal.

## Decisions made explicit or deferred

| Topic | Legacy behaviour | Native decision |
|---|---|---|
| Trimming | always scheduled; raw fallback | optional, deferred; raw input is explicit in foundation 0.1 |
| MAPQ | 30 | explicit `BAM_SELECT` input; config-compatible default, overrideable |
| Secondary/supplementary | removed | explicit exclude mask 2308; never hidden in aligner |
| Duplicates | removed by default | native default `none`; explicit `mark/remove`, always measure before removal |
| Blacklist | optional alignment-level exclusion | optional tracked BED; fragment default preserves paired templates, alignment mode is compatibility policy |
| Mitochondrial/alternative contigs | not filtered | unsupported until an organism-independent policy exists |
| Peak type | inferred by target regex | must be explicit narrow/broad |
| Genome size | sum of contig lengths | require an explicit declared policy/value |
| Missing controls | normally rejected | retain early validation; future exceptions must be explicit |
| Consensus | union of any overlapping peak | explicit union, intersection, replicate-support or IDR strategy |
| IDR | absent | optional native IDR 2.0.4.2 provider |
| Differential binding | DESeq2 `~ condition`, silent fallback | explicit featureCounts/DESeq2 provider and versioned design/contrasts |
| Annotation | first overlap/custom precedence | explicit provider, priority and coordinate policies |

## Metadata interpretation

Biological replicate describes independently prepared biological material.
Technical replicate describes repeated sequencing or handling of the same
library. `run_accession` and `lane` identify records; they do not create new
biological replicates. Native validation rejects ambiguous duplicate rows and
incompatible fields across records assigned to the same sample.

Controls may represent input DNA or another explicitly labelled control. The
current validator checks identity and reference compatibility; it does not
claim antibody/control-type suitability, which depends on assay design and must
be reviewed by the study owner.

## Validation targets for later stages

A reduced alignment comparison should evaluate total reads, overall alignment,
uniquely/multiply aligned records where available, MAPQ distribution, flags and
BAM records after normalizing order where necessary. Post-alignment validation
will add duplication metrics and fragment distributions. Peak validation will
compare count, width and score distributions, FRiP when implemented, replicate
concordance and basic biological plausibility.

Differences must be classified as technical (format/order), expected (declared
policy), methodological (changed scientific decision) or defect. No stage is
scientifically validated merely because its stub succeeds.

## Known limitations retained after retirement

- Native ChIP-seq trimming remains unimplemented. BAM processing and
  downstream analysis consume the declared FASTQs directly.
- Technical replicate merging is not implemented; records align independently.
- The supported alignment provider is Bowtie2; BWA is not exposed as a fallback.
- FRiP and IDR are implemented. Cross-correlation, library-complexity estimates
  and motif analysis are not currently claimed.
- Reviewed biological regression remains a post-release milestone.

## Development validation

- At the time of this historical review, `nextflow lint .` passed 72 files and
  reported one warning in `LEGACY_STEP`. That module was later removed during
  Integrative retirement.
- Native alignment stub: passed with one input control and two IP biological
  replicates (six FastQC tasks, MultiQC, one Bowtie2 index and three aligns).
- Resume probe: every native foundation task was reported as cached.
- The historical full fallback stub passed during migration; the coordinator
  was subsequently removed and preserved in `chipseq-legacy-v1.0.0`.
- Metadata unit tests: six passed, covering multiple samples, controls,
  biological/technical replicates and representative invalid inputs.
- Real SAMtools BAM processing: passed with paired MAPQ/flag selection,
  duplicate detection/removal, fragment blacklist, disabled blacklist, final
  indexes, two records and full cache reuse.
- Expected failures: reference-length and blacklist-contig incompatibilities
  were both rejected before final BAM publication.

A real Bowtie2 alignment and scientific legacy comparison were not executed:
the pinned combined Bowtie2 runtime is not installed on this development host.
The BAM layer was executed with host SAMtools 1.20, but this does not establish
alignment equivalence or biological peak performance.
