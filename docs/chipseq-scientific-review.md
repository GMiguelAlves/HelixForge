# ChIP-seq scientific review

This review classifies decisions before they become native defaults.

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
| MAPQ | 30 | future `BAM_SELECT` input |
| Secondary/supplementary | removed | future explicit SAM-flag policy |
| Duplicates | removed by default | future `keep/mark/remove` policy; collect metrics first |
| Blacklist | optional | future independent tracked transformation |
| Mitochondrial/alternative contigs | not filtered | unsupported until an organism-independent policy exists |
| Peak type | inferred by target regex | must be explicit narrow/broad |
| Genome size | sum of contig lengths | require an explicit declared policy/value |
| Missing controls | normally rejected | retain early validation; future exceptions must be explicit |
| Consensus | union of any overlapping peak | legacy fallback only; define reproducibility/support rule first |
| IDR | absent | future optional provider, not added in this stage |
| Differential binding | DESeq2 `~ condition`, silent fallback | not migrated; future separate API must fail if its method is unavailable |
| Annotation | first overlap/custom precedence | not migrated; document semantics before selecting a provider |

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

## Known limitations of foundation 0.1

- Native ChIP-seq trimming, BAM filtering, duplicate handling and peak calling
  are not implemented.
- Technical replicate merging is not implemented; records align independently.
- The first provider is Bowtie2 only. The legacy BWA option remains fallback.
- Container parity and a real reduced Bowtie2 regression depend on availability
  of the pinned execution environment.
- No FRiP, cross-correlation, library-complexity estimate, IDR or motif analysis
  is claimed.

