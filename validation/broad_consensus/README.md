# Broad-peak representation review

This diagnostic compares interval representations on **the same called
peaks and frozen annotation**. It does not align reads, call new peaks,
change scientific parameters, run Differential Binding, or replace results.
Gene counts are measured outcomes, never optimization targets.

## Run

Use a Consensus API `replicate_evidence.tsv`, the exact annotation used by
Peak Annotation, its native annotation manifest, and its `annotated_peaks.tsv`:

```bash
python validation/broad_consensus/compare_representations.py \
    --evidence replicate_evidence.tsv \
    --annotation annotation.gtf \
    --annotation-manifest manifest.json \
    --native-annotations annotated_peaks.tsv \
    --output new_review_directory
```

Python's standard library is sufficient. The reference checksum must match
the annotation manifest. The program first reconstructs the native atomic
intervals **and every native category/gene assignment**; disagreement fails
the review. An existing destination is never overwritten.

## Fixed diagnostic comparisons

| Representation | What it tests | What it does not establish |
|---|---|---|
| `atomic_core` | Current >=2-unit per-base support rule | Complete domain boundaries |
| `merged_core` | Join adjacent cores without adding covered bases | Recovery of excluded regions |
| `overlap_supported_regions` | Preserve full connected peak envelopes that contain a >=2-unit core | Replicated support throughout those envelopes |
| `reciprocal_50_whole_peaks` | Whole peaks with pairwise >=50% overlap in both directions | A universally appropriate 50% threshold or the full ENCODE method |
| `full_union_no_replicate_filter` | All called bases; diagnostic upper bound | Reproducibility, specificity or biological truth |

Connected peak envelopes require positive overlap, not merely bookended
coordinates. They can contain long tails supported by only one library.
`region_support.tsv` reports these bases and the supported fraction rather
than assigning a misleading uniform support value to a whole region.

The 50% comparator is fixed and symmetric. It is not a threshold sweep, an
adopted default, or an implementation of pooled-peak ENCODE processing.
This review currently supports two-unit thresholds across two or more input
libraries; it does not generalize its pairwise comparator to arbitrary k-of-n.

## Annotation and interpretation

Each representation is annotated with the existing native provider, the
same feature priority and the same `gene_assignment=first` rule. A separate
all-gene overlap count uses gene bodies and the existing promoter/downstream
windows, ignoring the category priority; it must not be confused with the
native first-gene result. Annotation settings are not fitted to the outcome.

The gene-recurrence table counts a gene once per input library. Recurrence
at gene level does not mean that the same genomic interval is supported,
that biological independence is established, or that differential binding
has been demonstrated. Changes in interval geometry may also change the
priority-based gene assignment.

Outputs include interval BEDs, annotation tables, coverage/width summaries,
regional support, gene recurrence, input/code checksums and the exact
annotation parameters. No private execution path is recorded in the JSON.

The existing baseline is neither silently promoted to a full-domain catalog
nor replaced with the representation yielding the largest number of genes.
See the [representation guidance](../../docs/guides/broad-peak-consensus.md).
