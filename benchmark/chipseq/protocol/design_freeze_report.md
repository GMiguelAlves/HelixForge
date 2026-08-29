# ChIP-seq benchmark design freeze report

## Scientific target

| Field | Frozen value |
|---|---|
| HelixForge version | `1.0.0-rc.1` |
| Target commit | `0829c7c154dc634ffd4e13672b95ad4fbdc5957f` |
| Last ChIP-seq feature commit | `a7b939fadc22f17db0c0517759a3985a9f2c25cf` |
| Nextflow | `25.10.7` |
| Java | `21` |

The target is newer than the original RC tag because the ChIP-seq native path
received reviewed feature, maintenance and immutable-runtime changes after the
tag. No new tag is created by this design freeze.

## Current ChIP-seq implementation

| Capability | Current state |
|---|---|
| Official path | raw FASTQ → FastQC/MultiQC → Bowtie2 → BAM processing → MACS3 → FRiP → consensus/IDR → optional downstream APIs |
| Narrow support | MACS3 narrowPeak and two-replicate IDR |
| Broad support | MACS3 broadPeak and replicate-support interval consensus |
| Control | Input supported and selected; IgG semantics not separately validated |
| Replicates | biological replicate metadata; no technical-replicate merge |
| IDR | official for exactly two premerged narrow biological replicates |
| Differential binding | implemented, but outside this single-condition benchmark |
| Report / terminal manifest | complete in `full`; mode-specific benchmark evidence requires an external top-level benchmark manifest |

No ChIP-seq trimming, BWA provider, cross-correlation QC or NRF/PBC module is
present. The benchmark does not pretend otherwise.

## Synthetic narrow

| Field | Frozen value |
|---|---|
| Simulator | ChIPs v2.4, commit `766c92cbb50783a537c897431b77e6bff8dba506` |
| Reference | `synthetic_chip_v1`, 60 Mb total, 54 Mb effective |
| Libraries | 2 paired-end IP replicates + 1 WCE Input |
| Truth | 1,500 peaks of 400 bp with known summits |
| Depth | 8 million 75 bp read pairs per library |
| Signal | 500 each at scores 0.90, 0.60 and 0.30 |
| MACS3 | 3.0.4, `BAMPE`, narrow, q=0.01 |
| Primary metrics | precision, recall, F1, observed FDP, summit error and strength-stratified recall |
| Primary released set | IDR-filtered peaks, while per-replicate truth accuracy remains mandatory |

## Synthetic broad

| Field | Frozen value |
|---|---|
| Simulator | frozen contiguous-domain generator + ChIPs v2.4 |
| Reference | same deterministic 60 Mb synthetic reference |
| Libraries | 2 paired-end IP replicates + 1 WCE Input |
| Truth | 360 domains balanced across 3 width × 3 signal classes |
| Depth | 12 million 75 bp read pairs per library |
| Widths | 2–4,999 bp; 5–19,999 bp; 20–80 kb |
| MACS3 | 3.0.4, `BAMPE`, broad, q=0.01, implicit broad cutoff 0.1 |
| Primary metrics | base precision/recall/F1, IoU, coverage recall, boundaries, fragmentation and merging |
| Primary released set | replicate-support consensus with support ≥2; no classical IDR gate |

## Real narrow

| Field | Frozen value |
|---|---|
| Dataset | ENCODE `ENCSR000AKO`, K562 CTCF |
| IP files | `ENCFF000BWM`, `ENCFF000BWR` |
| Control | Input `ENCSR000AKY` / `ENCFF000BWK` |
| Layout | single-end, 36/51 bp IP reads |
| Approximate compressed download | 2.22 GiB |
| Biological expectations | canonical CTCF motif centrality, replicate reproducibility, reference-peak plausibility and beta-globin locus signal |

## Real broad

| Field | Frozen value |
|---|---|
| Dataset | ENCODE `ENCSR000AKQ`, K562 H3K27me3 |
| IP files | `ENCFF000BXP`, `ENCFF000BXN` |
| Control | Input `ENCSR000AKY` / `ENCFF000BWK` |
| Layout | single-end, 51/36 bp IP reads |
| Approximate compressed download | 2.46 GiB |
| Biological expectations | extended-domain shape, positive replicate coverage concordance, reference-domain plausibility and Polycomb-associated annotation context |

The two arms use GENCODE release 50 GRCh38 primary assembly and ENCODE
blacklist `ENCFF356LFX`. ENCODE processed peaks are references, never ground
truth.

## Independent reference

The external implementation starts from separate raw FASTQs and independently
runs Bowtie2 2.5.4, samtools 1.20 selection, compatible blacklist filtering,
MACS3 3.0.4 and the frozen evaluator. It may share the scientific method but
cannot consume HelixForge work directories, BAMs, peaks, modules or manifests.

## Risks and gaps

- **POTENTIAL_BUG:** none identified as a blocker before execution.
- **IMPLEMENTATION_GAP:** `full` requires differential binding, so
  single-condition arms use `idr` or `consensus`.
- **IMPLEMENTATION_GAP:** those mode-specific paths lack the same terminal
  manifest emitted by `full`; the benchmark manifest supplies top-level audit
  binding without changing the workflow.
- **DOCUMENTATION_GAP:** migration-era ChIP-seq pages retain some obsolete
  status statements, deferred to later editorial cleanup.
- **BENCHMARK_BLOCKER:** none.

Scientific limitations include simplified synthetic mappability, incomplete
broad-domain biological realism, legacy unequal-length ENCODE reads, duplicate
retention and dataset-dependent plausibility references. Full details are in
[`risks_and_limitations.md`](risks_and_limitations.md).

## Next execution

```text
Synthetic narrow
↓
Synthetic broad
↓
Real narrow
↓
Real broad
↓
ChIP-seq administrative baseline freeze
```

No execution starts from this branch. The maintainer must review and approve
the frozen protocol first.

**Final status: `CHIPSEQ_BENCHMARK_DESIGN_FROZEN`.**
