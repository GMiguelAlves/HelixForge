# Real Narrow protocol amendment: GC-matched null relocation

Date: 2026-08-30  
Benchmark: K562 CTCF Real Narrow  
Status: accepted before production of the ENCODE null result

## Classification

```ini
PROTOCOL_IMPLEMENTATION_CONFLICT = RESOLVED_PRE_EXECUTION
SCIENTIFIC_RATIONALE = STRONG
POST_HOC_TUNING_RISK = LOW
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

The correction was triggered by a feasibility failure, not by an inspected RN3
result. It makes the null more conservative with respect to a relevant genomic
covariate and was fixed before any alternative-null execution. The residual
bias risk is therefore low. ENCODE remains an external plausibility reference,
not biological ground truth.
