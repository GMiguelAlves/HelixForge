# Real Narrow protocol amendment: GC-matched null relocation

Date: 2026-08-30  
Benchmark: K562 CTCF Real Narrow  
Status: null-generator correction accepted before valid RN3 inference

## Classification

```ini
PROTOCOL_IMPLEMENTATION_CONFLICT = RESOLVED_BEFORE_VALID_RN3_INFERENCE
SCIENTIFIC_RATIONALE = STRONG
PREVIOUS_RN3 = INVALID_FOR_INFERENCE
```

## Problem

The originally frozen ENCODE-overlap null used one rigid circular offset per
chromosome and required the aggregate GC fraction of each null set to differ
from the observed HelixForge IDR peaks by no more than `0.005`.

The first evaluator attempt stopped before publishing any evaluation result
because an ENCODE narrowPeak record legitimately used `-1` for an unavailable
summit. After that schema-only correction, Slurm job `16256` tested 2,000 rigid
rotations and accepted none. The observed CTCF peak GC fraction was `0.505083`;
the closest rigid rotation remained approximately `0.083` away. No RN3 value,
null-overlap table, metrics bundle, figure, or benchmark classification was
produced or inspected.

This is a structural incompatibility between rigid rotation and GC matching.
Rigid rotation preserves relative peak geometry, but moves the GC-enriched CTCF
peak set toward chromosome-background sequence. Increasing the number of
rotations or relaxing the frozen tolerance would not correct the null model.

## Original rule

```text
100 chromosome-preserving rigid circular rotations
aggregate absolute GC-fraction difference <= 0.005
seed 20261002
empirical p = (1 + null values >= observed) / 101
```

## Accepted correction

Each observed peak is independently relocated. Every candidate preserves:

- chromosome;
- exact peak width;
- GC decile;
- the shared observed/null contig universe;
- the eligible genome mask.

GC classes are frozen as `[0.0,0.1)`, `[0.1,0.2)`, ..., `[0.9,1.0]`. The class
is `min(9, floor(10 * (G+C)/(A+C+G+T)))`. Candidate intervals containing any
non-`ACGT` base or intersecting the frozen ENCODE blacklist `ENCFF356LFX` are
ineligible.

Candidates are grouped by chromosome, exact width, and GC class. Before the
scientific null statistic is calculated, every group must expose a deterministic
candidate pool of at least:

```text
max(200, 20 * observed peaks in the group)
```

This verifies at least twenty eligible candidates per required placement in a
single null set. Sampling is without replacement inside each group and null
set. Reuse across the 100 independently sampled null sets is permitted and is
reported through the number of unique relocated intervals and maximum exact
interval reuse. Candidate-pool size, capacity ratio, and random-probe count are
written to `null_relocation_capacity.tsv`.

The first capacity-only pass in Slurm job `16259` stopped at a rare
`chr10`/259 bp/GC-decile-8 group after finding 189 of the required 200 unique
candidates in 400,000 uniform probes. This demonstrated ample capacity for the
single required placement but exposed an overly short search budget. The pool
requirement was not relaxed: the deterministic probe budget was increased from
2,000 to 10,000 probes per required pool entry before retrying. No null overlap,
RN3 value, or evaluation bundle was produced by that pass.

Slurm job `16260` subsequently passed the capacity checks for every group, but
uniform sampling inside the intentionally broad GC deciles produced zero of
2,000 sets within the separately frozen aggregate tolerance. This was a sampler
implementation conflict, not a lack of eligible regions. The decile boundaries,
pool sizes, aggregate tolerance, and scientific criteria were retained. No
overlap statistic, RN3 value, or evaluation bundle was produced by job `16260`.

A nearest-GC implementation was then evaluated. Slurm job `16266` completed and
produced a provisional empirical p of `0.009900990099009901`, but its diversity
audit showed that this sampler did not implement the intended randomization:

```text
eligible candidate-pool positions = 4,100,600
total relocations                 = 3,183,800
unique relocated intervals       = 141,317 (4.44%)
mean reuse                        = 22.5
maximum reuse                     = 100/100
minimum pool capacity             = 22.22 times demand
```

The provisional value is preserved in the audit trail but is classified as:

```ini
RN3 = INVALID_FOR_INFERENCE
status = NOT_ACCEPTED
reason = NULL_GENERATOR_DIVERSITY_FAILURE
```

No scientific classification may use that p-value.

## Final null-generator contract

Candidate pools continue to be produced by deterministic uniform rejection
sampling of the frozen eligible genome. Within each frozen
chromosome/exact-width/GC-decile stratum, each null set samples uniformly and
without replacement. Reuse is allowed only between independently generated
null sets. Nearest-GC ranking or preferential sampling is forbidden.

If a uniformly drawn set misses the separately frozen aggregate GC tolerance,
randomly ordered within-stratum swaps may replace selected candidates only in
the direction that reduces the aggregate GC difference. The swaps cannot cross
strata, change pool membership, use a coordinate twice within a stratum/null,
or inspect ENCODE overlap. The master seed remains `20261002`; because the
algorithm changed, it defines a new deterministic sequence rather than claiming
identity with the invalid sequence.

For stratum `g`, with candidate-pool size `M_g`, demand per null `k_g`, and
`B=100`, expected occupancy is frozen as:

```text
E[unique_g] = M_g * [1 - (1 - k_g/M_g)^100]
```

Every stratum with expected occupancy of at least 50 must satisfy
`observed_unique_g >= 0.80 * E[unique_g]`. Maximum candidate reuse is bounded
by the stratum-specific quantile of `Binomial(100, k_g/M_g)`, using global
family-wise alpha `0.01` across all candidate-pool positions. Exact duplicates
inside one stratum/null are forbidden. Within-null interval overlap is reported
descriptively.

Validation is separated from inference:

1. generate 100 null sets and perform only preservation, capacity, diversity,
   reuse, duplicate, overlap, and aggregate-GC audits;
2. repeat the same implementation with the same seed and require byte-identical
   null-set SHA-256;
3. freeze the validated null sets and checksums;
4. calculate RN3 exactly once and accept PASS or FAIL without another
   p-value-motivated sampler change.

The aggregate absolute GC-fraction tolerance remains `0.005`. Up to the frozen
2,000 candidate sets may be examined to obtain the 100 accepted null sets.

## Preserved decisions

The amendment does not change:

- FASTQs, reference, blacklist, Input, or scientific HelixForge outputs;
- the observed overlap statistic;
- the external ENCODE accession or contig-intersection policy;
- `n_null_sets = 100`;
- random seed `20261002`;
- aggregate GC tolerance `0.005`;
- empirical-p calculation;
- RN3 threshold or interpretation category;
- any other frozen benchmark criterion.

If RN3 worsens or fails under the corrected null, that result is retained.

## Bias assessment

The original correction was triggered by feasibility. The later nearest-GC
diversity defect was detected by its predeclared audit and invalidated despite a
nominally passing RN3. The p-value is retained rather than hidden, while the
final generator is validated without calculating RN3. This separation prevents
the next inferential result from influencing sampler development. ENCODE remains
an external plausibility reference, not biological ground truth.
