# Peak QC API v1

Peak QC API v1 consumes one final treatment BAM/BAI, its BAM manifest, one
semantic Peak Calling result, a reference, optional blacklist provenance, and
an explicit QC specification. Requests are joined by stable record and peak
identifiers; channel order is never used as biological identity.

## FRiP definition

For a validated peak union `P` and the set of eligible alignment units `E`:

```text
FRiP = |{ e in E : e overlaps P by at least one reference base }| / |E|
```

The unit is `reads` for single-end libraries and `fragments` for paired-end
libraries under the default `layout` policy. Paired fragments are properly
paired primary templates and are counted once. An explicit `reads` override is
supported for paired data and is recorded in provenance; fragments are invalid
for single-end data.

Eligible alignments exclude unmapped, secondary, supplementary, and QC-failed
records by default. The default Peak QC MAPQ threshold is zero because the final
BAM has already passed the explicit BAM Processing threshold. Duplicate-marked
records remain included by default: the upstream BAM duplicate policy is
authoritative, and Peak QC never silently removes duplicates. Users may choose
`exclude_flagged` explicitly.

Peaks that overlap one another are merged only in a temporary interval set used
for overlap counting, so one read/fragment contributes at most once. Original
peak files remain unchanged. `any_base` is the only v1 overlap strategy.

The default blacklist policy is `bam_preprocessed`: Peak QC records the tracked
blacklist and relies on BAM Processing, which already applied its explicit
blacklist policy. No organism, chromosome set, or genome size is hardcoded.

## Request contract

Each request records:

- sample, experiment, target, control, biological replicate, and technical replicate;
- final BAM, BAI, peak file, manifests, reference, optional blacklist, and checksums;
- narrow/broad peak type, caller, and caller version;
- resolved read/fragment unit, overlap strategy, filter flags, MAPQ, duplicate policy, and blacklist policy.

Context validation rejects identity mismatches, invalid narrowPeak/broadPeak
columns, negative or reversed coordinates, unknown contigs, and coordinates
beyond reference sequence bounds before overlap jobs start.

An existing empty peak file is a valid complete-empty result: peak count and
numerator are zero and FRiP is zero when the eligible-unit denominator is
positive. A missing file or a zero denominator remains an explicit error.

## Output contract

Per replicate, the API emits FRiP, numerator, denominator, peak statistics,
filter and overlap statistics, logs, versions, execution metadata, provenance,
manifest, and status. A caller-neutral aggregate table combines replicas but
does not pool BAMs, call consensus peaks, perform IDR, rank samples, or remove
outliers.

Consensus/IDR and differential binding remain separate future APIs consuming
peaks, replicate identity, and these QC manifests.
