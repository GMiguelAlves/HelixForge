# Synthetic ChIP-seq truth contract

Truth is generated before reads and is immutable within a benchmark run. Every
file is tab-delimited, coordinate-sorted, uses zero-based half-open BED
coordinates and carries a SHA-256 entry in the run manifest.

## Narrow truth

Required files:

- `narrow_true_peaks.bed`: `chrom`, `start`, `end`, `peak_id`, `signal_score`,
  `strand`;
- `narrow_true_summits.bed`: one-base summit intervals keyed by `peak_id`;
- `narrow_peak_strength.tsv`: signal class, numeric strength, GC decile,
  mappability and seed;
- `narrow_negative_regions.bed`: 1,500 matched negative intervals;
- `narrow_simulation_manifest.json`: generator version, parameters and
  checksums.

There must be exactly 1,500 400 bp truth intervals and 500 members of each
signal class. Truth intervals and negatives may not overlap one another,
repeat blocks, ambiguous sequence or chromosome-end exclusion zones.

## Broad truth

Required files:

- `broad_true_domains.bed`: `chrom`, `start`, `end`, `domain_id`,
  `signal_score`,
  `strand`;
- `broad_domain_strength.tsv`: width class, signal class, exact width, GC
  decile, mappability and seed;
- `broad_negative_regions.bed`: 360 width-, chromosome- and GC-matched
  intervals;
- `broad_simulation_manifest.json`: generator version, parameters and
  checksums.

There must be exactly 360 domains, with 40 in every width-by-strength cell and
at least 10 kb between domains. Broad truth has no summit.

## Validation invariants

The future generator must fail before simulation when counts, bounds, spacing,
class balance, coordinate order, overlap constraints or reference identity do
not match the frozen JSON configuration. Evaluators must consume truth from an
independent read-only path and never infer it from generated FASTQs, alignments
or MACS3 output.
