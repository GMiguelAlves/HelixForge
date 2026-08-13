# Differential Binding API v1

Differential Binding API v1 converts semantic ChIP-seq peak sets and final BAM
artifacts into an explicit count model and independently cached contrasts. It
does not claim biological validation or equivalence with the legacy workflow.

## Statistical unit

One model column represents one premerged biological replicate/sample. A
technical sequencing record is not an independent observation. V1 accepts only
`replicate_mode=biological` with `replicate_policy=require_premerged` from the
Consensus API and rejects repeated biological-replicate identities within a
condition. The stable column identity is `record_id`/`sample_id` from validated
metadata and matching final-BAM manifests, never path order.

Controls used during peak calling are not model columns unless explicitly
represented as treatment samples in a future design. Each model requires at
least two represented condition levels and the configured minimum number of
biological replicates in every contrast level.

## Input boundary

The logical request contains:

```text
meta
Consensus or IDR provider artifacts and manifests
FINAL_BAM/BAI artifacts and manifests
validated ChIP-seq metadata plan
versioned differential-binding specification
```

Inputs must describe compatible dataset/experiment, target, genome, peak type
and caller-neutral semantic coordinates. V1 accepts completed native
`consensus` or `idr` manifests. An unavailable IDR artifact is a fatal input
error; `complete_empty` remains an explicit empty statistical result.

The specification defines:

- peak-universe method (`union` in v1);
- counting provider and read/fragment policies;
- explicit formula (`~ condition` or `~ batch + condition` in v1);
- design variable and supported categorical covariates;
- one or more named numerator/denominator contrasts;
- peak filter and every threshold;
- normalization and statistical provider parameters.

Interactions, arbitrary R formulas, inferred contrasts, unlisted covariates and
pre-model batch correction are rejected.

## Peak universe

Comparison conditions require the same row universe. `DB_PREFLIGHT` groups
compatible Consensus manifests across conditions and constructs a recorded
comparison union from their semantic consolidated intervals. Overlapping or
book-ended intervals are merged after deterministic genomic sorting and receive
stable peak IDs. Input manifest IDs and checksums remain in the request.

This is an explicit peak-selection policy, not IDR or replicate evidence. No
caller score, summit, p-value or q-value is synthesized. Future providers may
accept an externally curated or IDR-derived universe behind the same contract.

## Counting provider

`PEAK_COUNTING_PROVIDER` dispatches one implementation in v1:

```text
FEATURECOUNTS_PEAK
```

It consumes the comparison BED, explicit BAM/sample map and counting
specification and emits an integer peak-by-sample matrix. It uses Subread
featureCounts with SAF coordinates. Provider parameters include:

- `unit`: reads for single-end or fragments for paired-end;
- `strandedness`: 0, 1 or 2;
- `min_mapq`;
- `overlap_policy`: `any` in v1;
- `allow_multi_overlap`: false in v1;
- `allow_multimapping`: false in v1;
- final-BAM duplicate and blacklist policies, recorded from manifests.

Mixed single/paired layouts in one model, silent duplicate re-filtering,
fractional counts and ambiguous multiple assignment are rejected in v1. Raw
counts and featureCounts summary remain available. Counting performs no
normalization or statistical filtering.

## Preflight

`DB_PREFLIGHT` fails before counting/model jobs when it finds:

- absent or duplicate sample/record IDs;
- missing condition or biological-replicate identity;
- unpremerged or duplicated technical evidence;
- fewer than the requested biological replicates in a contrast level;
- missing or inconsistent BAM, BAI, BAM manifest, peak artifact or manifest;
- incompatible genome, target, peak type or analysis grouping;
- invalid/duplicate contrast IDs or absent numerator/denominator levels;
- unsupported formula, interaction or covariate;
- missing batch values, one-level batch, or obvious rank deficiency;
- unsupported counting, filtering, normalization or provider policy.

Joins use manifest identity and checksums. Filenames, glob order and channel
arrival order are not biological associations.

## Filtering and normalization

Filtering is a model input and occurs before fitting, with an audit trail of
initial and retained peaks. V1 supports:

- `none`;
- `minimum_count`: retain peaks with `count >= min_count` in at least
  `min_samples` samples.

No peak is silently removed. Blacklist handling is inherited and recorded from
the final-BAM and Consensus contracts; it is not applied again implicitly.

Raw counts remain immutable. With provider `deseq2`, normalization must be
`deseq2_median_of_ratios`; DESeq2 estimates size factors from raw integer counts.
Normalized counts are an output for inspection, not input to the Wald test.
ComBat or another count transformation is not run before the model. Batch is a
categorical covariate in `~ batch + condition` when requested.

## Statistical providers and cache boundaries

```text
DB_PREFLIGHT
    -> FEATURECOUNTS_PEAK
    -> DB_MODEL_PROVIDER / DESEQ2_DB_MODEL
    -> DESEQ2_DB_CONTRAST x N
    -> DB_AGGREGATE
```

V1 implements DESeq2 Wald only. The model and contrasts are separate tasks.
Changing a contrast invalidates that contrast and aggregation, not peak
counting or model fitting. Changing BAMs or peak universe invalidates counting
and all downstream tasks. Changing filtering/design/model parameters invalidates
the model and contrasts. Every process uses deep cache with tracked files and
explicit specifications.

## Output contract

The API emits:

| Role | Contract |
|---|---|
| raw counts | peak ID and one explicitly mapped integer column per sample |
| normalized counts | DESeq2 size-factor-normalized matrix |
| model | serialized DESeq2 object, design metadata, dispersions and coefficients |
| contrast results | peak genomic coordinates, baseMean, log2FoldChange, lfcSE, statistic, pvalue and padj |
| MA data | machine-readable baseMean/log2FoldChange/significance table |
| statistics | input/retained peaks, samples, levels and significance counts |
| provenance | peak/BAM/sample IDs, biological replicates, conditions, batch, policies, checksums and commands |
| versions | featureCounts/Subread, R, Bioconductor, DESeq2 and runtime versions |
| execution metadata | Nextflow version, resources, profile, Git commit and elapsed time |
| manifest/status | semantic artifacts with availability and completion state |

The aggregate manifest links experiment, conditions, replicates, peak universe,
count matrix, model and every contrast. Downstream annotation, motif, enrichment,
tracks, reports and Integration APIs must consume this manifest instead of
reconstructing paths.

## Legacy fallback

`chipseq_native_differential_binding=false` routes the dedicated mode to the
unchanged `differential` legacy step. Native results deliberately do not reproduce
positional BAM columns, inferred pairwise contrasts, automatic rounding or the
non-inferential log2-mean fallback described in the legacy review.
