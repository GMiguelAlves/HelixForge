# Frozen ChIP-seq benchmark protocol

## Purpose and ordering

The protocol answers four separate questions, in this immutable order:

1. Can narrow, summit-centred enrichment be recovered against known truth?
2. Can broad domains be recovered without reducing them to point peaks?
3. Does the narrow path recover expected CTCF biology in a public experiment?
4. Does the broad path recover expected H3K27me3 biology in a public experiment?

No result from a later arm may be used to tune an earlier design. The global
baseline is decided only after all four arms are classified independently as
`PASS`, `PASS_WITH_LIMITATIONS`, `FAIL` or `BLOCKED`.

## Synthetic reference

Both synthetic arms use a deterministic custom reference `synthetic_chip_v1`:

- three pseudochromosomes of 20 Mb each (60 Mb total);
- generator seed `20260900`, 42% target GC and deterministic 1 kb repeat blocks
  occupying 10% of the assembly;
- no annotation is used for peak accuracy; a minimal deterministic GTF is made
  only when an annotation smoke test is requested;
- truth and negative regions are restricted to non-N, uniquely mappable
  sequence and remain at least 2 kb from repeats and chromosome ends;
- explicit MACS3 effective genome size `54000000` (the 90% non-repeat eligible
  sequence); no blacklist is invented for this reference;
- FASTA, FAI, Bowtie2 index and generated truth checksums are recorded after
  generation and before simulation.

The simplified genome is a deliberate cost control and a documented source of
optimistic mapping. It is not presented as a human-genome substitute.

## Synthetic narrow design

`NARROW_SIMULATOR = ChIPs v2.4 (766c92c), direct narrow-region model`.

ChIPs was selected because it is a versionable C++ command-line simulator,
emits paired or single-end FASTQ, models shearing/pulldown/PCR/sequencing,
supports WCE/Input, accepts explicit region scores, exposes a seed and was
evaluated by its authors for TF and histone-mark data. ChIPulate models TF
binding energetics in more detail, but its published model does not generate
genome-wide background outside supplied bound regions in the same way. ART
alone is a sequencing simulator and does not model immunoprecipitation.

The frozen design is:

| Parameter | Value |
|---|---:|
| True peaks | 1,500 |
| Peak width | 400 bp |
| Minimum summit spacing | 5,000 bp |
| ChIP replicates | 2 biological simulation replicates |
| Matched Input | 1 WCE library |
| Read layout | paired-end |
| Read length | 75 bp per mate |
| Read pairs | 8,000,000 per library |
| Fragment distribution | Gamma(shape=15, scale=12), mean 180 bp |
| ChIPs copies | 1,000 |
| ChIP SPOT parameter | 0.25 |
| PCR rate | 0.85 |
| Seeds | 20260911, 20260912, Input 20260913 |

There are exactly 500 peaks in each predeclared signal class. With ChIPs
`--noscale`, their binding probabilities/scores are `0.90` (STRONG), `0.60`
(MEDIUM) and `0.30` (WEAK). Classes derive from the simulator input, never from
MACS3 output. Replicates share truth and parameters but use independent seeds;
this provides two stochastic biological-like realizations without pretending
that a simulator recreates actual donor variation.

A true peak is the exact half-open 400 bp input interval centred on its stored
summit. Required future truth artifacts are defined in
[`truth/README.md`](../truth/README.md). A negative panel contains 1,500
non-overlapping 400 bp intervals matched by chromosome, GC decile and
mappability, at least 2 kb from truth.

### Narrow matching

1. Remove calls outside eligible contigs; do not remove calls merely because
   they miss the truth set.
2. Build a bipartite graph between called and true peaks when intersection is
   at least 100 bp **and** covers at least 25% of the 400 bp true interval.
3. Obtain a deterministic maximum-cardinality matching; among equal solutions,
   maximize total intersection, then minimize total absolute summit distance,
   then sort by true `peak_id` and called coordinates.
4. One matched call is one TP and one recovered truth. Every unmatched call is
   an FP; every unmatched truth is an FN.
5. Additional calls overlapping an already matched truth are unmatched FPs and
   are also reported as narrow fragmentation. A call connected to several true
   peaks can match only one; the others remain available to other calls or FN.
6. Summit distance and width error are computed only for matched pairs. The
   matching itself does not require summit containment, avoiding circularly
   favourable localization estimates.

AUPRC uses a fixed candidate universe: 1,500 one-kilobase windows centred on
true summits plus 1,500 matched negative windows. Each window receives the
maximum MACS3 signal score of an overlapping call, or zero. Genome-wide
unmatched calls still count in peak-level precision, so the restricted AUPRC
cannot conceal off-panel false positives.

### Narrow replicate result

Per-replicate accuracy, interval consensus and IDR are reported separately.
Ground-truth accuracy is evaluated for each replicate and for the final IDR
set. Replicate reproducibility is not ground truth.

IDR is official only for narrow:

- provider `idr=2.0.4.2`;
- exactly two premerged biological `narrowPeak` inputs;
- rank `signal_value`;
- threshold `0.05`;
- replicate mode `biological`, policy `require_premerged`;
- primary released peak set: IDR-filtered peaks; per-replicate accuracy remains
  mandatory evidence.

## Synthetic broad design

`BROAD_SIMULATOR = ChIPs v2.4 (766c92c) + frozen contiguous-domain generator`.

The ChIPs paper explicitly models histone modifications and accepts arbitrary
enriched intervals, WCE background, paired reads, fragment distributions and
seeds. It did not specifically validate H3K27me3 domain boundaries. Therefore,
the benchmark adds no unverified biological spreading model: a deterministic
generator declares continuous domains first, and ChIPs samples directly from
those intervals. This tests interval recovery under known coverage while the
absence of nucleation, chromatin accessibility and copy-number effects remains
a stated realism limitation. ChIPulate is not chosen because it targets
locus-specific TF occupancy; ART alone lacks ChIP enrichment.

The frozen design is:

| Parameter | Value |
|---|---:|
| True domains | 360 |
| Width × strength strata | 40 domains in each of 3 × 3 cells |
| Minimum inter-domain gap | 10,000 bp |
| ChIP replicates | 2 biological simulation replicates |
| Matched Input | 1 WCE library |
| Read layout / length | paired-end / 75 bp per mate |
| Read pairs | 12,000,000 per library |
| Fragment distribution | Gamma(shape=15, scale=12), mean 180 bp |
| ChIPs copies | 100 |
| ChIP SPOT parameter | 0.35 |
| PCR rate | 0.85 |
| Seeds | 20260921, 20260922, Input 20260923 |

Width classes are `SHORT_BROAD` 2,000–4,999 bp, `MEDIUM_BROAD` 5,000–19,999
bp and `LONG_BROAD` 20,000–80,000 bp. Widths are sampled deterministically and
recorded. Signal classes use ChIPs `--noscale` scores `0.80`, `0.50`, `0.25`.
A true domain is the exact declared half-open interval; no summit is defined.
The negative panel contains 360 eligible non-overlapping intervals matched to
the exact truth width distribution, chromosome and GC decile.

### Broad matching and topology

All coordinates are reduced to unions before base-level metrics. Let `T` be
the union of truth bases and `C` the union of called broadPeak bases.
Intersection is `|T ∩ C|`; union is `|T ∪ C|`. Base precision, recall and F1
use these lengths.

For topology, construct an overlap graph using every positive intersection.
An edge is *substantial* when it covers at least 10% of the truth domain and at
least 500 bp. A truth is recovered when the union of all overlapping calls
covers at least 50% of it. Per-domain IoU compares that truth interval with the
union of all substantially connected calls.

- **Fragmentation:** a truth domain has at least two substantial called
  neighbours. Fragmentation excess is `max(0, degree - 1)`; the fragmentation
  rate is the fraction of truth domains with degree ≥2.
- **Merging:** a called region has substantial edges to at least two truth
  domains. Merge excess is `max(0, degree - 1)`; the merging rate is the
  fraction of called regions with degree ≥2.
- Boundary error is reported for connected components containing exactly one
  truth and one call. Multi-node components are characterized as topology
  errors rather than assigned misleading single boundaries.

No summit metric or classical narrowPeak IDR gate is used. The primary broad
replicate result is `replicate_support` with `min_replicates=2`; union and
intersection may be descriptive sensitivity analyses only.

## Real narrow design

The selected dataset is ENCODE K562 CTCF `ENCSR000AKO` with raw FASTQs
`ENCFF000BWM` (biological replicate 1), `ENCFF000BWR` (replicate 2) and Input
`ENCFF000BWK` from control experiment `ENCSR000AKY`. All are single-end. The
two replicates use different read lengths (36 and 51 bp); this is frozen as a
dataset limitation, not normalized by trimming.

HelixForge runs through `chipseq_run_mode=idr`. Per-replicate narrowPeak,
FRiP, peak overlap/rank concordance, IDR and the IDR-filtered set are primary.
ENCODE optimal IDR peaks `ENCFF519CXF` and signal `ENCFF433VSV` are external
plausibility references, not ground truth and not inputs to HelixForge.

## Real broad design

The selected dataset is ENCODE K562 H3K27me3 `ENCSR000AKQ`, using raw FASTQs
`ENCFF000BXP` (biological replicate 1), `ENCFF000BXN` (replicate 2) and the
same Input `ENCFF000BWK`. They are single-end and have 51/36 bp read lengths.

HelixForge runs through `chipseq_run_mode=consensus` with
`replicate_support`, `min_replicates=2`. Per-replicate broadPeak, FRiP,
coverage correlation, base/domain overlap and consensus domains are primary.
Classical IDR is excluded. ENCODE replicated peaks `ENCFF049HUP` and signal
`ENCFF366NNJ` are descriptive external references only.

## Frozen processing policy

Both HelixForge and the independent implementation use raw FASTQ without
trimming, Bowtie2 2.5.4 `--very-sensitive`, samtools 1.20, MAPQ 30, exclusion
flags 2308, duplicate mode `none`, and the same reference/blacklist policy.
Keeping duplicates reflects current HelixForge defaults; duplicate fraction is
reported and the limitation is interpreted, not silently changed.

Synthetic data use no blacklist. Real data use ENCODE GRCh38 exclusion list
`ENCFF356LFX` with fragment-level removal. Every IP has explicit Input; IgG and
no-control behavior are out of scope. Input and IgG are never treated as
semantically interchangeable.

## Independent implementation

The independent harness is a separately launched, versioned Bash/Python path:

```text
raw FASTQ
→ independent FastQC inventory (descriptive)
→ bowtie2-build / bowtie2
→ samtools sort/index/view with frozen filters
→ independent blacklist filter
→ MACS3 callpeak with the frozen argument set
→ independent interval/IDR evaluation
```

It may use the same scientific tools and versions but cannot import HelixForge
modules, manifests, work directories or scientific outputs. `END_TO_END`
starts from separate raw FASTQ links/copies. `METHOD_CONTROLLED` independently
runs MACS3 on a checksum-verified copy of a common frozen BAM only when needed
to localize a disagreement; it is diagnostic and cannot replace end-to-end
evidence.

## Real reference bundle

- assembly: GRCh38 primary assembly (GRCh38.p14 context);
- FASTA: GENCODE release 50 `GRCh38.primary_assembly.genome.fa.gz`, MD5
  `da1a11258be075cfa7af718162c894e7`;
- annotation: `gencode.v50.primary_assembly.annotation.gtf.gz`, MD5
  `289b91e5e95e8b0450d223246f10a12e`;
- contig naming: GENCODE chromosome/scaffold names, unchanged;
- effective genome size: `2913022398`, the explicit MACS3/deepTools GRCh38
  value;
- blacklist: ENCODE `ENCSR636HFF` / `ENCFF356LFX`, MD5
  `393688b4f06c9ce26165d47433dd8c37`.

Compressed-source MD5 and post-decompression SHA-256 must both be captured by
the future reference manifest. Reference preparation fails on contig mismatch;
it never renames chromosomes automatically.

## Execution sequence

After maintainer approval, execute exactly:

```text
Synthetic narrow
→ Synthetic broad
→ Real narrow
→ Real broad
→ administrative ChIP-seq baseline freeze
```

For each arm: validate metadata → prepare/download asynchronously → validate
checksums → run HelixForge on Slurm → run independent path on Slurm → evaluate
frozen metrics → classify → archive compact evidence → clean eligible scratch
artifacts. A failure is investigated and reported before the next arm; no
parameter is tuned against observed results.

## Sources

- [ChIPs paper](https://doi.org/10.1186/s12859-021-04097-5) and
  [v2.4 source](https://github.com/gymreklab/chips/tree/v2.4)
- [MACS3 3.0.4 callpeak reference](https://macs3-project.github.io/MACS/docs/callpeak.html)
- [GENCODE human release 50](https://www.gencodegenes.org/human/)
- [ENCODE CTCF experiment](https://www.encodeproject.org/experiments/ENCSR000AKO/)
- [ENCODE H3K27me3 experiment](https://www.encodeproject.org/experiments/ENCSR000AKQ/)
- [ENCODE Input experiment](https://www.encodeproject.org/experiments/ENCSR000AKY/)
- [ENCODE blacklist annotation](https://www.encodeproject.org/annotations/ENCSR636HFF/)
