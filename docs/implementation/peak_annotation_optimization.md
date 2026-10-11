# Peak annotation interval-index optimization

## Context

Peak Annotation API v1 uses the compatibility provider
`python_interval_v1`. The provider intentionally preserves the annotation
semantics of the legacy pipeline: feature classes are derived from GTF/GFF,
overlaps use zero-based half-open coordinates, feature priority is explicit,
and gene assignment remains deterministic.

The first native implementation stored features sorted by genomic coordinate,
but evaluated every feature on the chromosome for every peak. This was
scientifically correct and adequate for small fixtures. A real broad-peak run
exposed that its execution cost did not scale adequately.

This optimization changes only how overlap candidates are found. It does not
change the Peak Annotation API, scientific parameters, feature construction,
overlap predicate, category priority, gene selection, output schemas, or file
names.

## Previous lookup

For every peak and every feature category considered by the configured
priority, the provider evaluated the complete chromosome-specific feature
list:

```python
row.start < peak.end and row.end > peak.start
```

If `P` is the number of peaks and `F` the number of features on a chromosome,
the dominant lookup cost was approximately `O(P * F)` per feature category.
Broad-peak datasets amplify this cost because they can contain hundreds of
thousands of consensus intervals while the annotation contains many gene,
exon, intron, promoter, and downstream records.

## Current lookup

The provider now builds an immutable index for each feature category and
chromosome. Because feature rows are already sorted deterministically by
start, end, and gene identifier, the index records two arrays alongside those
rows:

- `starts[i]`: start coordinate of feature `i`;
- `prefix_max_end[i]`: greatest end coordinate among features `0..i`.

A query for the half-open peak interval `[peak_start, peak_end)` proceeds as
follows:

1. `bisect_left(starts, peak_end) - 1` locates the last feature that can start
   before the peak ends.
2. The search walks backwards while `prefix_max_end[i] > peak_start`.
3. Each remaining candidate is checked with the original overlap predicate:
   `feature_start < peak_end and feature_end > peak_start`.
4. Hits are reversed back into the original deterministic genomic order before
   feature priority and gene-assignment rules are applied.

The prefix maximum is important. Looking only at adjacent feature ends would
be incorrect for nested or long features; an earlier interval can overlap a
peak even when several later, shorter intervals do not.

Index construction is linear after the existing sort. A typical query avoids
examining most chromosome features and costs approximately `O(log F + C)`,
where `C` is the candidate region inspected. The worst case remains `O(F)` for
adversarial collections of highly nested or chromosome-spanning intervals.
This limitation is explicit and avoids overstating the data structure as a
fully balanced interval tree.

## Scientific equivalence

The optimization was accepted only after two equivalence checks:

- a unit regression compares indexed lookup with the frozen linear lookup over
  overlapping, nested, boundary-touching, absent-contig, and long-interval
  cases;
- a completed real DMSO annotation was repeated with the indexed provider. The
  SHA-256 values of both scientific semantic outputs,
  `annotated_peaks.tsv` and `peak_gene_associations.tsv`, were identical to the
  linear implementation.

Execution metadata and timing fields are expected to differ. They are not
scientific equivalence targets.

## Observed performance

The controlled Slurm validation produced the following evidence:

| Dataset | Linear provider | Indexed provider | Outcome |
|---|---:|---:|---|
| DMSO broad consensus, 171,471 intervals | 5,221 s | 210 s | about 24.9x faster; scientific output hashes identical |
| GSK343 broad consensus, 721,335 intervals | exceeded the 3 h 59 min task limit | completed in about 3 min 40 s | previous timeout removed |

The measurements are validation observations, not a general-purpose benchmark:
speedup depends on peak density, feature density, interval nesting, storage,
and compute-node characteristics.

## Why a project-local implementation remains

Tools such as BEDTools, ChIPseeker, HOMER, PyRanges, and Bioframe can perform
parts or richer variants of peak annotation. Replacing the compatibility
provider during validation would also change dependencies and could change
feature construction, overlap priority, ordering, multi-gene behavior, or
nearest-gene semantics.

The indexed implementation therefore remains the v1 compatibility provider.
The provider-neutral API allows alternative implementations to be added and
validated later without changing downstream workflows. A future provider
should be preferred over silently changing `python_interval_v1` whenever it
introduces different scientific semantics.

## Operational limits

- The index is held in memory for the duration of one annotation task.
- The provider is single-process Python; allocating additional CPUs does not
  currently parallelize overlap queries.
- Extremely nested annotations retain a linear worst case.
- Nearest-TSS and strand-aware overlap remain unsupported v1 scientific modes;
  the optimization does not approximate them.
- Any later replacement must repeat semantic-output regression, not merely
  compare task completion or row counts.

