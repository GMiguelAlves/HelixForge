# ChIP-seq legacy differential-binding review

This review documents the current implementation without changing it or
declaring it scientifically equivalent to the native API. Files audited:

- `scripts/110-consensus-peaks/consensus_peaks.sh`;
- `scripts/120-differential-binding/differential_binding.sh`;
- `scripts/r/differential_binding.R`;
- `scripts/validate_metadata.py`, `scripts/lib/common.sh` and
  `chipseq_pipeline.sh`;
- differential settings in `config/pipeline_config.sh` and
  `config/user_settings_template.sh`;
- `envs/chipseq.yml` and the downstream report reader.

All paths above are under `pipelines/chipseq/legacy/`.

## Execution and dependencies

The shell wrapper activates the shared `chipseq` environment and invokes the R
script after the legacy consensus job. The environment is not fully pinned and
contains R >=4.2, BEDTools, Subread, DESeq2, ggplot2 and pheatmap. In the actual
path, consensus/counting uses shell, AWK, sort and `bedtools multicov`; the
statistical script uses base R and optionally DESeq2. Subread/featureCounts is
installed but is not used for differential binding.

The legacy orchestrator submits differential binding after consensus. Its
scheduler behavior remains outside the native design and is not copied.

## Peak-set selection and counting

Consensus creates two families of interval sets:

1. `condition__mark.consensus.bed`, unioning peaks for all IP samples in that
   condition and target;
2. `mark__all.consensus.bed`, unioning the target across all conditions.

Peak files are discovered with `find ... | head -n 1`, so caller/type identity
is implicit. Only chromosome, start and end are retained, and any overlap is
merged. No minimum replicate support or reciprocal-overlap rule is used.

`metadata_ip_samples` returns all non-control sample IDs in metadata row order.
Their filtered BAM paths are passed, in that order, to `bedtools multicov` for
every consensus BED. The output has no header: the first three columns are BED
coordinates and remaining columns are inferred later to have the same order as
all IP rows. Counts are not restricted to the mark/target of a peak set during
count construction. No manifest, checksum or explicit BAM-to-column map is
stored with the matrix.

The default statistical scope is `mark_all`, so condition-specific peak sets
are skipped. Count files are found by directory glob and parsed from filenames.

## Metadata and statistical unit

The legacy validator requires unique `sample_id` values and columns including
condition, mark/factor, replicate, batch and control status. It checks replicate
counts by `(condition, mark_or_factor)`, but `REQUIRE_DIFF_REPLICATES=false` by
default makes low replication a warning at pipeline validation time.

Inside R, the effective statistical columns are sample IDs from non-control
metadata rows. Technical and biological replicate meanings are not separated;
the `replicate` column is not used by the model. After positional assignment of
matrix columns, samples are filtered to the peak set's mark and conditions with
at least `MIN_REPLICATES_DIFF` rows (default 2). Thus an independently aligned
technical record could be counted as an independent replicate if represented as
a unique sample row.

The `batch`, treatment and control relationship fields are not used by the
statistical model.

## Design, contrasts, normalization and filtering

The only model is DESeq2 Wald with `design = ~ condition`. Counts are rounded
before `DESeqDataSetFromMatrix`; no explicit fractional-count policy is exposed.
DESeq2 estimates size factors and dispersions internally. No matrix
pre-normalization or batch correction is performed.

`DIFF_CONTRASTS` accepts comma-separated `numerator:denominator` pairs. If it is
empty, all unordered pairs are inferred from the order in which condition
levels appear. Invalid pairs are silently removed. Contrast direction is the
first level versus the second. There is no versioned contrast specification,
unique contrast-ID validation or rank-deficiency preflight.

There is no explicit low-count, minimum-sample, condition-support, width or
blacklist filter in the R model. The only effective filters select a target,
conditions with enough metadata rows and valid contrasts. Peak totals before
and after filters are not recorded as a filter audit trail.

## Statistical fallback

When DESeq2 is unavailable, the script calculates the difference between group
means of `log2(count + 1)` and emits `NA` p-values and adjusted p-values. When
DESeq2 throws an error, the peak set is reported as failed/no-results. The
exploratory fallback can therefore look like a differential result even though
it is not an inferential test. The native API must fail instead of producing
this fallback.

## Outputs

Per eligible peak set, the script can write:

- `<peak_set>.differential.tsv[.gz]`;
- PCA and heatmap PDFs or a QC-skipped text file;
- per-contrast MA and volcano PDFs.

It also writes `differential_binding_run_summary.tsv[.gz]` and
`differential_binding_results.tsv[.gz]`, plus a skip marker when appropriate.
DESeq2 tables contain peak ID, base mean, log2 fold change, p-value, adjusted
p-value, contrast, method, peak set, target and count filename. They omit
`lfcSE`, Wald statistic and explicit genomic columns from the combined semantic
contract. No model object, normalized matrix, session information, versions,
execution metadata, checksums or manifest is emitted.

## Implicit behavior and compatibility risks

- BAM/count columns depend on metadata order rather than stable IDs.
- Count matrices include all IP BAMs before target filtering.
- Peak caller/type is selected by filesystem discovery.
- Biological and technical replicates are not explicitly distinguished.
- Pairwise contrasts may be invented from observed condition order.
- Counts are rounded without a declared policy.
- DESeq2 availability changes the meaning of the result.
- Batch is collected but ignored.
- `mark__all` is a filename convention rather than a semantic manifest.
- Multiple count files are discovered and processed by glob.
- Peak coordinates become a colon-concatenated row name.

## Native compatibility boundary

The legacy filenames remain available through fallback, but the native API will
not preserve unsafe positional joins, implicit contrasts, automatic rounding or
the exploratory fallback. It will use semantic Consensus manifests, explicit
BAM/sample mappings, an explicit counting provider, explicit filtering/design/
contrasts, DESeq2-internal normalization and separate model/contrast cache
boundaries. These are intentional scientific-contract changes and require later
biological validation before equivalence claims are possible.
