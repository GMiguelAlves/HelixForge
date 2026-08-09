# Peak Calling API v1

Peak Calling API v1 separates experiment validation, caller execution and provider-neutral output normalization. Downstream stages consume semantic peak artifacts and manifests; they do not reconstruct MACS3 filenames.

## Request contract

Each request represents exactly one treatment replicate. Required semantic fields are:

- `peak_id`, `sample_id`, `record_id`, `experiment_id`, `target`;
- biological and technical replicate identifiers;
- treatment final BAM/BAI and optional control final BAM/BAI;
- explicit `control_id` resolved to at most one `control_record_id`;
- `genome_id`, reference checksum and numerical `effective_genome_size`;
- `caller`, pinned caller version and explicit `peak_type` (`narrow` or `broad`);
- input format (`BAM` or `BAMPE`), paired-end handling and duplicate policy;
- exactly one significance policy: q-value or p-value;
- validated additional arguments.

`peak_type=auto`, organism aliases for genome size, ambiguous controls, duplicated replicate identity and output collisions are invalid. Paired libraries require `BAMPE`; single-end libraries require `BAM`.

## Provider boundary

`PEAK_CALLING` dispatches a validated request to a provider. Provider v1 is `MACS3_CALLPEAK` with MACS3 3.0.4. A future provider must accept the common request and normalize its results through `PEAK_CALLING_AGGREGATE`; callers such as SEACR or Genrich therefore do not require workflow changes.

Managed arguments (`-t`, `-c`, `-f`, `-g`, `-n`, output directory, cutoff, broad mode, duplicate policy and signal generation) cannot be overridden through `additional_args`.

## Output contract

The result directory contains, when applicable:

- `peaks.narrowPeak` or `peaks.broadPeak`;
- `summits.bed` for callers/modes that define summits;
- treatment and control signal bedGraphs;
- unmodified provider outputs under `caller_outputs/`;
- `peak_metrics.json` and `peak_metrics.tsv`;
- `manifest.json` with experiment, replicate, control, provider and parameter identity.

The process channels additionally expose reports/logs, versions, execution metadata, provider manifest and status. Missing semantic roles are represented as `available: false`, not fabricated.

## Generic QC

Aggregation validates exact narrowPeak (10) or broadPeak (9) columns, non-negative half-open coordinates, `end > start`, contig names and numeric score/signal fields. It reports total peaks and width, score and signal distributions. FRiP is intentionally outside v1 until its read-counting denominator and overlap policy are formally specified.

## Cache semantics

Caller, peak type, cutoff, treatment BAM, control BAM, format, duplicate policy and additional arguments are task inputs under deep cache. A change invalidates only context/provider/aggregation tasks that depend on it. Unsupported caller changes fail during context validation rather than silently choosing a provider.
