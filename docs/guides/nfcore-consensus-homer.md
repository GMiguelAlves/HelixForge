# Regional consensus and HOMER annotation

HelixForge reuses the consensus implementation of **nf-core/chipseq 2.1.0**
and uses **HOMER 4.11** for annotation, adding orchestration, contracts and
evidence transport. This opt-in method is not numerical compatibility with
`python_interval_v1`. HelixForge is not an official or certified nf-core
pipeline. Existing modes and frozen benchmark classifications are unchanged.

## Available and retired methods

| Component | Current status |
|---|---|
| `nfcore_2_1` regional consensus + `homer_4_11` annotation | Available through explicit selection below |
| Atomic `union`, `intersection`, `replicate_support` consensus | Retained for compatibility; their existing geometry and support rules are unchanged |
| `python_interval_v1` annotation | Retained for compatibility and still the configured default annotation provider |
| IDR | Retained as a separate optional reproducibility analysis for supported narrow-peak inputs |
| Experimental `regional_catalog_v1` and `broad_heldout_v1` | Removed; their manifests are rejected rather than silently converted |

Retiring the two experimental providers did **not** remove the atomic consensus
or the compatibility annotator. Consensus selection remains explicit; adding
nf-core/HOMER did not switch existing executions automatically. To use the
regional policy, select both consensus and annotation providers as shown below.

## Explicit selection

Add these options to an otherwise configured ChIP-seq execution:

```bash
--chipseq_consensus_method nfcore_2_1 \
--chipseq_min_replicates 1 \
--chipseq_annotation_provider homer_4_11 \
--chipseq_annotation_mode homer_native
```

The existing `full` coordinator runs annotation, tracks and reporting; DB
remains optional through `--chipseq_db_enabled false`. These options do not
change alignment, duplicate handling, fragment-size policy or MACS3 thresholds.

For `nfcore_2_1`, an unset/null `chipseq_min_replicates` resolves to **1**:
retain every regional candidate and describe support rather than discard
single-library regions. Explicit higher thresholds remain available. This does
not change the default consensus provider or the legacy atomic strategies.

## Regional policy and evidence

The reference is pinned to commit `76e2382b6d443db4dc2396e6831d1243256d80b0`.
HF runs its BEDTools 2.30.0 sort/merge/column-collapse sequence and unchanged
`macs3_merged_expand.py`. Because the helper parses identity from peak names,
HF supplies reversible `HF_REPnnnn_peak_n` tokens. `source_peak_mapping.tsv`
retains original names and explicit library, record and source-peak IDs.

HF applies the policy within its existing dataset/experiment/condition/target/
reference/peak-type groups. It does not silently pool conditions or antibodies.
The reference nf-core workflow groups across conditions by antibody; direct
comparisons must use the **same selected input group**, not assume the entire
pipelines implement identical experimental designs.

BEDTools merges overlapping and bookended intervals with zero merge distance.
Connected chains can therefore form larger regions; no positive gap distance
is introduced. Library presence does not mean every base has replicate support.

| Product | Meaning |
|---|---|
| `unfiltered_peaks.bed`, `upstream.unfiltered.boolean.txt` | Catalog before support exclusion (`min_replicates=1`) |
| `consolidated_peaks.bed`, `upstream.boolean.txt` | Catalog retained by explicit support threshold |
| `excluded_regions.tsv` | Support exclusions, distinct from geometric reduction |
| `support_core.bed` | Supplementary HF atomic bases with at least `max(2, min_replicates)` libraries |

Stable HF IDs derive from the unfiltered catalog. Original upstream IDs remain
in native outputs. The core is **not an nf-core-certified output** and never
clips the annotation input or silently controls regional retention.

`support_by_library.tsv` includes every retained region × library pair, including
zeros: source identities, called-peak count, covered bases/fraction, region length
and core bases. Classification is `candidate` or `candidate_with_library_support`,
always with `occupancy_status=not_assessed`. No coverage or IP/Input ratio becomes
an occupancy significance test.

## Annotation and re-entry

HOMER receives the matching FASTA and GTF from the Reference Bundle:

```bash
annotatePeaks.pl peaks.bed genome.fa -gid -gtf annotation.gtf -cpu N
```

Use matching SM_V10/WBPS19 GTF `gene_id`/`transcript_id` attributes. HF never
substitutes a human/mouse genome or downloads an annotation database. Original
HOMER output remains available; custom GTFs may leave descriptive fields empty.
The normalized relationship is HOMER's nearest-promoter assignment, not the old
overlap-priority rule or proof of regulation. Native labels/distances and missing
values are preserved. Compatibility-specific parameter overrides are rejected.

Each regional gene association retains calling libraries, per-library coverage/
fraction, shared-core bases and candidate classification. Original evidence
artifacts are copied into a checksum-verified bundle. Aggregation preserves the
association fields, and report manifests retain the method/evidence semantics.

### TSV library provenance

`consolidated_peaks.tsv`, HOMER `annotated_peaks.tsv` and
`peak_gene_associations.tsv`, including the annotation aggregate, carry:

| Column | Meaning |
|---|---|
| `calling_libraries` | Comma-separated source `record_id` values, sorted by ID |
| `calling_samples` | Corresponding `sample_id` values in the same order; repeated sample IDs are preserved |
| `calling_library_count` | Number of distinct libraries with an original called peak in the region |
| `total_library_count` | All libraries in this condition/target group, including libraries with no calls |
| `library_support_category` | `single_library` (1), `multiple_libraries` (2 to N−1), or `all_libraries` (N) |

For two-library groups, support in both is `all_libraries`, not the middle
category. “All” refers only to the declared group, never all studies or marks.
Consensus still requires at least two declared evidence units, even with
minimum support 1. Biological/technical replicate policies remain explicit.
`support` and `support_replicates` remain available for compatibility; the latter
contains replicate keys, not the source library identifiers.

`support_by_library.tsv` retains the complete region × library matrix with
`record_id`, `sample_id`, source peak ID, coverage and zero-support rows.
The annotation TSVs preserve this detail in `library_support_json`, together
with `support_core_bp`, `evidence_classification` and `occupancy_status`.
Support categories describe called-library membership, not significance,
basewise reproducibility, or confirmed occupancy. A regional chain can have
multiple calling libraries and little or no shared core.

### Ambiguous gene associations

Library support and gene-assignment ambiguity are independent evidence axes.
A region called in every library can still have an ambiguous nearest-gene
assignment. Conversely, a single-library candidate can have a well-defined
nearest annotated promoter without proving regulation.

The HOMER adapter preserves the single `Nearest PromoterID` returned by HOMER,
its native annotation and TSS distance. It additionally checks distance ties
against a preserved `parseGTF.pl annotation.gtf tss -gid` snapshot produced by
the same HOMER 4.11 package. TSVs, including annotation aggregates, expose:

| Column | Meaning |
|---|---|
| `gene_assignment_ambiguous` | `true`, `false`, or `not_assessed` within the stated scope |
| `gene_assignment_ambiguity_reason` | Tie detected, no tie detected, or why assessment was unavailable |
| `gene_assignment_ambiguity_scope` | `homer_nearest_tss_distance_ties_v1` |
| `alternative_gene_ids` | Sorted JSON array of distinct tied gene IDs, excluding the provider-selected gene |

`true` means distinct genes have equally nearest TSS positions on the peak's
chromosome, consistent with HOMER's reported distance and native peak midpoint.
This covers shared TSS coordinates and equidistant TSS on opposite sides of the
midpoint. Transcript duplicates from the same gene do not create gene-level
ambiguity. `false` means no tie was detected **by this distance-based check**,
not proof of a uniquely regulated gene. Broader regulatory ambiguity is outside
this scope. `not_assessed` is used for no assigned gene, missing evidence in
older results, or a provider position/distance that cannot be reconciled with
the snapshot. Missing columns in compatibility/older results also mean not
assessed; they must never be treated as `false`.

The flag does not reassign the selected gene, alter `gene_count`, create extra
association rows, or change HOMER parameters. `gene_count=1` remains one reported
assignment. TSS snapshots and metadata are checksummed against the supplied GTF;
the manifest records scope, checksums and assessment counts. A checksum mismatch
fails rather than silently declaring a relationship unambiguous.

Distinct annotated genes may share a TSS. A disagreement between otherwise
identical direct and orchestrated HOMER runs can expose that ambiguity; it
does not create it. The same reference-level ambiguity can be relevant in an
ordinary annotation run even when no comparison is performed. Row-order-only
differences are ignored by the reduced comparator, but a changed gene identity
still fails exact record equivalence. A deterministic selected ID would not,
by itself, establish a uniquely correct biological target.

Downstream atlas consumers should display flagged assignments as **ambiguous**,
retain the provider-selected gene separately from `alternative_gene_ids`, and
link evidence to the region, reference, provider and assessment scope. Additional
reviewed alternatives should be distinguished from these automatically detected
distance ties. Alternatives must not be inferred from library support. This flag
is computed during normal annotation, not only during method comparison.

`excluded_regions.tsv` uses the same library columns when a higher threshold
is selected. Its `calling_libraries` field now contains identifiers rather than
the earlier numeric count; consumers needing the count must use
`calling_library_count`. Original upstream boolean tables remain unchanged.

Standalone annotation requires the existing peak/reference/annotation parameters
plus `--chipseq_annotation_evidence_bundle /path/to/consensus_result` for regional
inputs. `post_consensus` inventories can declare `evidence_bundle` alongside each
`peaks` and `manifest` location. Missing or incompatible evidence fails instead
of being discovered by scanning a published results tree.

## Reuse, runtimes and validation

The original MIT license, unchanged imported files and SHA-256 pins are in
`vendor/nfcore_chipseq/2.1.0/`. HF adapters are separate. HOMER is an external
program: the repository does not redistribute its source/binary. Its exact
Conda package/image is pinned. Before publishing a derived HOMER image, review
the package's GPL terms and corresponding-source obligations.

Adapters/helpers are tracked task inputs. Native output, commands, resources,
package metadata, checksums and versions are retained. Reduced tests compare HF
with direct tool execution on identical inputs/parameters. This validates
integration, not biological truth; biological acceptance is a separate review.

References: [consensus module](https://github.com/nf-core/chipseq/blob/2.1.0/modules/local/macs3_consensus.nf),
[helper](https://github.com/nf-core/chipseq/blob/2.1.0/bin/macs3_merged_expand.py),
[HOMER module](https://github.com/nf-core/chipseq/blob/2.1.0/modules/nf-core/homer/annotatepeaks/main.nf),
[nf-core outputs](https://nf-co.re/chipseq/2.1.0/docs/output/),
[HOMER package/license](https://bioconda.github.io/recipes/homer/README.html).
