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

## Retired V2 generator

Two pre-inference executions of the GC-decile-uniform plus balanced-swap V2
generator were performed in Slurm jobs `16267` and `16268`. They produced
byte-identical null-set SHA-256
`700d6d2fe9ab9e776f78f61b1b9049240fb61257d8aa5678528149dd01f2d925`.
Capacity, preservation, aggregate GC and absence of within-null duplicates all
passed, and RN3 was not calculated. Diversity failed identically:

```text
strata                              = 20,503
unique-occupancy gate failures      = 5
binomial reuse gate failures        = 1,942
balanced swaps per null, median     = 2,268
maximum observed reuse              = 22
```

Uniform selection inside broad GC deciles targets the pool's within-decile GC
mean. Enforcing a different observed aggregate mean requires preferential
selection; the swaps therefore cannot simultaneously preserve the registered
uniform marginals. V2 is invalid and retired. Its deterministic outputs remain
audit evidence and are not frozen for inference.

## Final V3 null-generator contract

The operational stratum changes methodologically from:

```text
chromosome x exact width x GC decile + aggregate balancing
```

to:

```text
chromosome x exact width x exact integer GC-base count
```

The GC decile remains a descriptive superclass only. Candidate pools are
produced by deterministic uniform rejection sampling of the frozen eligible
genome and partitioned by exact GC-base count. Within each exact stratum, every
null samples uniformly and without replacement. Nearest-GC ranking, GC
optimization and balanced swaps are forbidden. Exact per-region width and GC
count preservation makes aggregate GC exact by construction.

Before any V3 null is generated, a capacity-only preflight must report `M_g`,
`k_g`, and `M_g/k_g` for every exact stratum. `M_g` is counted exactly within
the deterministic operational candidate pool. The preflight reports the number
of strata, singleton strata, `M_g < k_g`, capacity quantiles, and observed peaks
across capacity bands. It cannot read ENCODE overlap, generate nulls or calculate
RN3. If any `M_g < k_g`, RN3 becomes
`NOT_EVALUABLE_UNDER_FROZEN_CONTROL_REQUIREMENTS`; no fourth ad hoc generator is
permitted.

The master seed remains `20261002`. Because the algorithm changed, it defines a
new deterministic sequence rather than claiming identity with either invalid
sequence.

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

If capacity passes, validation remains separated from inference:

1. generate 100 null sets and perform only preservation, capacity, diversity,
   reuse, duplicate, overlap, and exact-GC audits;
2. repeat the same implementation with the same seed and require byte-identical
   null-set SHA-256;
3. freeze the validated null sets and checksums;
4. calculate RN3 exactly once and accept PASS or FAIL without another
   p-value-motivated sampler change.

This is the final permitted null-generator methodological amendment for RN3.
After structural validation and physical freezing, RN3 is calculated once and
accepted regardless of outcome.

## Final V3 capacity result

The capacity-only preflight ran once as Slurm job `16269`, before any V3 null
generation or RN3 calculation. It produced the following registered outcome:

```ini
PREFLIGHT_STATUS = FAIL_NOT_EVALUABLE
NUMBER_OF_STRATA = 31426
STRATA_WITH_M_LT_K = 1511
OBSERVED_PEAKS_IN_INFEASIBLE_STRATA = 1546
CAPACITY_RATIO_MINIMUM = 0
CAPACITY_RATIO_P05 = 1
CAPACITY_RATIO_MEDIAN = 4
CAPACITY_RATIO_P95 = 9
NULL_SETS_GENERATED = false
RN3_CALCULATED = false
RN3 = NOT_EVALUABLE_UNDER_FROZEN_CONTROL_REQUIREMENTS
```

The frozen failure policy was therefore activated. No V3 null sets were
generated, the nominal V1 p-value remains invalid for inference, and no fourth
ad hoc null generator will be attempted. This is an explicit limitation of the
Real Narrow benchmark rather than a failure of HelixForge execution.

## Preserved decisions

The amendment does not change:

- FASTQs, reference, blacklist, Input, or scientific HelixForge outputs;
- the observed overlap statistic;
- the external ENCODE accession or contig-intersection policy;
- `n_null_sets = 100`;
- random seed `20261002`;
- exact per-region and therefore exact aggregate GC preservation;
- empirical-p calculation;
- RN3 threshold or interpretation category;
- any other frozen benchmark criterion.

If RN3 worsens or fails under the corrected null, that result is retained.

## Bias assessment

The amendment bias risk is `LOW_TO_MODERATE`: a nominal RN3 was observed under
V1, then invalidated by structural criteria independent of its value; V2 failed
before RN3; and V3 follows directly from that registered incompatibility. V3 is
fully specified and validated before inference, and its next RN3 must be
accepted whether PASS or FAIL. The invalid p-value remains visible rather than
being hidden. ENCODE remains an external plausibility reference, not biological
ground truth.
