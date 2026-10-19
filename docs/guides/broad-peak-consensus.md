# Broad peaks: support cores, candidate regions and gene associations

## Current interval semantics

The interval Consensus provider uses BEDTools `multiinter` and filters its
atomic, half-open segments by support. With `replicate_support` and
`min_replicates=2`, **every retained base must be covered by calls from at
least two evidence units**. The output is a support-core representation,
not a catalog of complete broad-domain boundaries.

For example, calls `[0,200)` and `[199,400)` yield the one-base core
`[199,200)`. This is an exact interval calculation, but it does not establish
one-base biological resolution or show that the remaining 399 bases are
false positives. Conversely, expanding the core to `[0,400)` does not make
every base reproducibly supported.

A large reduction in coverage can therefore reflect spatial disagreement
between the input calls as well as the chosen support rule. It is not, on
its own, a calibrated estimate of sensitivity or specificity. Merging
adjacent cores changes the counting unit but does not recover excluded bases.

## Distinct scientific questions

- **Support cores:** where do input peak calls coincide at base resolution?
- **Candidate regions:** what full enriched intervals are plausible, and how
  much of each interval has support across libraries?
- **Gene associations:** which genes overlap candidate or supported intervals
  under an explicit annotation policy?

These are separate evidence layers. A gene can have calls in several
libraries at different positions without satisfying the per-base rule. A
domain can contain both supported cores and singly supported tails. Neither
case should be silently reduced to an unqualified presence/absence label.

## Review before adopting a broad-domain policy

Keep the input calls, annotation, fragment model and filtering fixed while
comparing representations. Report at least:

- input-union coverage, retained coverage and fraction retained;
- atomic segment counts, merged component counts and width distributions;
- supported bases and support fraction inside each candidate region;
- gene associations under the same rule, with all-overlap associations
  distinguished from priority-based first-gene assignment;
- per-library enrichment against the corresponding Input and quantitative
  signal concordance when BAMs or suitable coverage tracks are available.

Interval-only diagnostics cannot certify biological domain boundaries or
decide whether a larger catalog has better sensitivity rather than more
false positives. Do not choose a representation to match a publication's
peak/gene count. Counts across assemblies or methods are not a ground truth.

## External method precedents

DiffBind documents a configurable minimum number of peaksets and merging
overlapping peaks into intervals. Its defaults are not interchangeable with
filtering every base of an atomic segmentation. Consult the
[DiffBind reference manual](https://bioconductor.org/packages/release/bioc/manuals/DiffBind/man/DiffBind.pdf),
especially `DBA.config$mergeOverlap` and `dba.peakset`.

ENCODE's histone pipeline uses pooled candidate peaks together with overlap
support from individual and pseudo-replicate sets. This illustrates an
alternative to treating shared atomic subintervals as complete domains; it
does not make ENCODE's thresholds universally appropriate for every target,
organism or experiment. See the
[histone pipeline standards](https://www.encodeproject.org/chip-seq/histone/).

## Implementation status

The [controlled representation review](../../validation/broad_consensus/README.md)
compares fixed alternatives and checks exact reconstruction of the native
baseline. It is a diagnostic, not a newly certified consensus provider.
The production provider and current defaults are unchanged. Any replacement
must declare its interval/support semantics, preserve source evidence,
report unsupported tails/merging behavior, receive tests and an explicit
scientific policy, and enter through a versioned release. Existing pinned
executions must not change silently.
