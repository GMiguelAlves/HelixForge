# Integrative legacy scientific audit

Status: characterization baseline for Integration migration stage 1  
Legacy source: `pipelines/integrative/legacy` at commit
`d24f14588252c1184d78b865965d9f95e7754d01`

This document describes observed code behavior. It is not a proposal for the
future Integration API and it does not treat historical documentation as an
authority when it differs from the executable implementation.

## Scope and execution boundary

The top-level `ALL` workflow starts RNA-seq and ChIP-seq independently and
collects only their completion values. `INTEGRATIVE` receives that collection
as a synchronization seed, but no RNA or ChIP artifact crosses the channel.
The Integrative configuration independently discovers all scientific inputs.

`INTEGRATION` invokes eleven aliases of the generic `LEGACY_STEP`. Each task
calls `bin/run_legacy_step.sh`, which calls `integrative_pipeline.sh` with one
step and `--mode local`. Nextflow therefore controls allocation, but the
scientific files remain external side effects under `INTEGRATION_OUTPUT_DIR`.

The legacy coordinator can also submit its own `sbatch --dependency=afterok`
chain when invoked outside Nextflow. Its order is:

```text
validate -> prepare -> harmonize -> map-peaks
                         |             |
                         +-> summarize-rna
                                       +-> summarize-chip
summarize-rna + summarize-chip -> integrate -> score
                                                |-> visualize
                                                +-> functional
visualize + functional -> report
```

The Nextflow subworkflow expresses the same dependencies, except that every
step receives status files rather than the scientific artifacts it consumes.

## Central responsibility inventory

| Legacy responsibility | Function(s) | Type | Real inputs | Principal outputs | Scientific rules | Hidden assumptions | Future component | Equivalence |
|---|---|---|---|---|---|---|---|---|
| Validate | `command_validate`, `read_matrix_gene_ids`, `normalize_deg_rows` | MIXED | configured paths/globs | validation TSV/Markdown | checks matrix and DEG gene overlap | only three RNA files are fatal; ChIP, annotation and metadata may be absent | Integration preflight | SEMANTIC_EQUIVALENCE |
| Prepare | `command_prepare`, `normalize_deg_rows` | IO/ADAPTER | environment paths, RNA DEG and metadata | path manifest, normalized DEG, combined metadata | classifies DEG using configured padj/LFC thresholds | globs and guessed columns define identity | RNA/ChIP evidence adapters | TABLE_EXACT after path normalization |
| Harmonize | `command_harmonize`, `parse_annotation_genes`, `load_epigenetic_catalog` | MIXED | GTF/GFF, both RNA matrices, DEG, gene lists/catalogs, functional annotation | gene master, unmapped genes, machinery catalog | union of every observed exact gene ID | no namespace/version conversion; missing coordinates do not fail | ID Harmonization provider | TABLE_EXACT |
| Map peaks | `annotated_peak_rows`, `bed_peak_rows_from_master`, `command_map_peaks` | SCIENTIFIC + COMPATIBILITY | annotated peak glob, otherwise BED glob; gene master; ChIP metadata | peak-gene links, promoter/distal partitions, gene summary | annotated tables win globally; BED rescue assigns one nearest gene within 5 kb | file/column/name inference; configured promoter windows are unused | consume Peak Annotation API; optional explicit mapper | TABLE_EXACT / SET_EQUALITY |
| Summarize RNA | `metadata_groups`, `resolve_sample_group`, `command_summarize_rna` | SCIENTIFIC + IO/ADAPTER | normalized matrix, metadata, normalized DEG | gene summary, expression by context, sample mapping, DEG long table | arithmetic expression summaries and per-gene contrast counts | sample aliases/substrings and names can determine stage | RNA Evidence provider | TABLE_NUMERIC_TOLERANCE |
| Summarize ChIP | `load_diff_binding`, `command_summarize_chip`, `chip_metadata_mark_stage_rows` | SCIENTIFIC + IO/ADAPTER | mapped peaks, differential-binding table, ChIP metadata | gene summary, DB long table, mark-stage metadata | counts location categories; gained/lost uses padj/LFC thresholds | mark and gene columns are guessed; peak intensity/count glob is unused | ChIP Evidence provider | TABLE_EXACT / numeric tolerance |
| Integrate | `integration_class`, `command_integrate`, `write_gene_mark_stage_tables` | SCIENTIFIC | gene master, RNA/ChIP summaries, DEG, peak links, optional RNA evidence | integrated gene/contrast tables and gene-mark-stage catalogs | deterministic class priority; joins by exact gene ID | representative DEG is `up` if any contrast is up | Evidence Integration provider | TABLE_EXACT |
| Score | `command_score`, `write_mark_enrichment_tests`, `write_gene_mark_stage_correlations` | SCIENTIFIC | integrated tables, mark-stage links, expression contexts | ranked candidates, enrichment tests, signal matrix, correlations | fixed additive heuristic; one-sided Fisher; global BH; Pearson/Spearman | missing values become zero/default; stable ties inherit gene order | Candidate Prioritization provider | ORDERED_RANKING plus numeric tolerance |
| Visualize | `command_visualize`, `visualize_integrative.R` | REPORTING + MIXED | numbered output directories | PNG/PDF/SVG figures, panel index and figure manifest | visual recanonicalization and display-only evidence sums | discovers files by fixed directory names | Visualization provider | VISUAL_NOT_REGRESSION_CRITICAL |
| Functional | `command_functional` | SCIENTIFIC (descriptive) | top candidates and functional annotation | functional enrichment TSV | counts selected/background genes by split terms | despite its name, performs no enrichment hypothesis test | Functional Evidence provider or later Pathway API | TABLE_EXACT |
| Report | `command_report` | REPORTING | fixed prior output paths | Markdown and HTML | presents existing results; no model fitting | timestamps and absolute paths are embedded | Integration Report provider | SEMANTIC_EQUIVALENCE |

## Function-level map

The following tables cover every helper that can change scientific values or
associations. Simple text/file writers are listed separately as infrastructure.

### Generic data and statistics

| Function | Called by | Inputs and defaults | Behavior and output | Assumptions / preservation decision |
|---|---|---|---|---|
| `first_col` | most readers | header plus ordered candidate list | case-insensitive first matching column | COMPATIBILITY: replace with schemas; characterize guessed-column priority |
| `as_float` | all numeric logic | missing/NA/non-finite -> supplied default, normally 0 | finite float | LEGACY_BEHAVIOR: malformed scientific values silently become defaults |
| `as_int` | counts and flags | conversion through float; invalid -> default 0 | integer truncation | LEGACY_BEHAVIOR: preserve only for baseline |
| `fmt_float` | statistics | eight significant digits by default | empty for invalid/non-finite | preserve serialization semantics where relevant |
| `fisher_right_tail` | mark enrichment | overlap, target size, marked size, universe | one-sided hypergeometric right-tail using log combinations | preserve mathematical behavior and test numerically |
| `bh_adjust` | mark enrichment | all emitted p-values in one list | BH step-up monotonic adjustment | preserve; correction universe is global across all targets/scopes/marks/stages |
| `rank_values` | Spearman | numeric list | average ranks for exact ties | preserve |
| `pearson_corr` | correlations | paired lists, at least two points | product-moment correlation; `None` for constant input | preserve |
| `spearman_corr` | correlations | paired lists | Pearson over average ranks | preserve |
| `safe_id` | labels/aliases | arbitrary string | non `[A-Za-z0-9_.-]` -> `_`; empty -> `unknown` | reporting/compatibility only |

### IDs, annotations, samples, stages and marks

| Function | Responsibility | Inputs / expected columns | Rules and side effects | Decision |
|---|---|---|---|---|
| `parse_gtf_attributes` | parse GTF/GFF attributes | semicolon list, `key=value` or `key value` | strips surrounding quotes | preserve parser behavior for baseline; future Reference API should own it |
| `parse_annotation_genes` | construct genomic gene records | 9-column GTF/GFF; features gene/mRNA/transcript | gene ID priority `gene_id`, `ID`, `Name`; strips literal `gene:`; merges coordinate extent by exact ID | SCIENTIFIC; no transcript-to-gene mapping is performed |
| `read_matrix_gene_ids` | collect gene universe | guessed gene column, otherwise first column | exact non-empty strings | future contract must require the gene column |
| `read_set_file` | gene-of-interest set | first TSV/CSV token per line | lines whose first value starts with `gene` are skipped | POTENTIAL_BUG: valid IDs beginning with `gene` are discarded |
| `load_epigenetic_catalog` | machinery evidence | gene priority `matched_gene_id/gene_id/query/id`; group/name aliases | deduplicates `(gene, group)`, not gene; labels primary/supplemental source | preserve evidence; replace path discovery |
| `canonical_stage` | stage normalization | free text | token aliases: adult(s), egg(s), cercaria(e), miracidium/miracidia, schistosomulum/a, sporocyst(s), all/pooled | preserve as versioned vocabulary |
| `stage_label` | unknown/custom stage | stage text | canonical alias, otherwise sanitized lowercase; NA-like -> `unknown` | note that arbitrary values survive here but not in all callers |
| `row_stage` | metadata stage | configured stage/group columns, then columns containing stage/condition/etc. | first canonical stage found; otherwise `unknown` | COMPATIBILITY heuristic |
| `metadata_sample_keys` | sample identity candidates | many named columns plus any column containing sample/run/accession/etc. | produces ordered unique keys | COMPATIBILITY heuristic; project/study columns excluded |
| `sample_aliases` | sample matching | sample/path text | strips replicate and quant suffixes; adds basename and accession-like variants | COMPATIBILITY heuristic |
| `resolve_sample_group` | associate matrix column with stage | sample name and metadata alias map | exact alias, substring (length >=5), stage inferred from sample name, otherwise unknown | POTENTIAL_BUG risk of accidental substring association |
| `canonical_mark` | mark normalization | free text | HP1/SmHP1/Smp_179650/CBX -> SmHP1; known histone marks/ATAC; regex fallback; unknown ChIP | preserve vocabulary, replace filename inference |
| `infer_mark_stage` | infer peak identity | row values, source filename, ChIP metadata | explicit row -> metadata substring -> filename; missing mark -> `unknown_ChIP`; stage -> `unknown` | COMPATIBILITY; forbidden in future semantic joins |
| `chip_sample_metadata_lookup` | filename inference map | guessed sample/mark/condition columns | exact key dictionary; later duplicate keys overwrite earlier rows | compatibility only |
| `chip_metadata_mark_stage_rows` | ChIP assay inventory | mark, condition, sample, replicate, batch aliases | counts rows and joins sets with semicolons | migrate to explicit metadata contract |
| `load_mark_config` | mark biology annotations | fixed `${PROJECT_DIR}/config/chip_marks_config.tsv` | dictionary keyed by mark | preserve content as a versioned catalog, not a hidden project path |

### RNA evidence

| Function | Inputs | Scientific transformation | Defaults / hidden behavior |
|---|---|---|---|
| `normalize_deg_rows` | DEG table; gene/name/contrast/LFC/padj/pvalue aliases | `up` when `padj <= 0.05` and LFC `>= 1`; `down` when `<= -1`; otherwise not significant | missing LFC -> 0, missing padj -> 1, missing contrast -> `default`; exact gene IDs |
| `metadata_groups` | RNA metadata | maps all sample aliases to canonical stage | later aliases overwrite earlier ones |
| `command_summarize_rna` | normalized abundance matrix, metadata, DEG | per gene mean/median/min/max; stage means; fraction `value > 0`; specificity `max/sum`; significant contrast counts; dynamism `log2(max+1)*max(abs LFC)` | every non-gene matrix column is assumed to be a sample; negative abundance is not rejected |
| `expression_context_lookup` | optional external table, otherwise generated summary | dictionary by exact `(gene, lower-case stage string)` | does not canonicalize the external stage key |
| `stage_expression_table` | generated summary, otherwise external table | canonicalizes stage, weighted mean by `n_samples`, excludes unknown/all stages | if only log2TPM is present, reverses with `2^x-1` |
| `supplemental_rna_evidence` | WGCNA/Mfuzz/DTU/splicing files | presence of any row sets hit=true; configured fields concatenated as text | no significance threshold is applied to these optional files |

### ChIP evidence and peak mapping

| Function | Inputs | Scientific transformation | Defaults / hidden behavior |
|---|---|---|---|
| `annotated_peak_rows` | every annotated table matched by glob | selects one associated gene column and normalizes mark/stage | no splitting of multi-gene fields; peak ID synthesized from filename and row number |
| `bed_peak_rows_from_master` | BED globs and gene master | assigns midpoint to one nearest gene boundary when distance <= `PEAK_GENE_WINDOW_BP` (5000) | not nearest TSS; tie keeps first gene encountered (gene-master gene-ID order) |
| `command_map_peaks` | annotated rows or BED fallback | annotated source is used if any row exists; promoter iff annotation text contains `promoter`; body iff exact class gene/exon/intron/gene_body | `PROMOTER_UPSTREAM_BP=2000` and `PROMOTER_DOWNSTREAM_BP=500` are configured but never used |
| `load_diff_binding` | DB table with aliased gene/peak/mark/LFC/padj columns | gained/lost at padj <=0.05 and LFC >=1 or <=-1 | missing values become 0/1; condition is not carried into normalized records unless present incidentally |
| `command_summarize_chip` | peak links and DB rows | per-gene peak/location counts, mark/stage sets, differential count, maximum absolute DB LFC and minimum padj | differential rows join by gene only, not peak ID |

`CHIP_PEAK_COUNT_GLOB` is validated and written into the path manifest but is
never read by scientific code. `GENOME_FASTA` is configured but unused.

### Integration classes

`integration_class(deg_status, chip_summary)` applies this exact priority:

1. DEG (`up` or `down`) and at least one differential peak ->
   `DEG_with_differential_peak`;
2. DEG and promoter peak -> `DEG_with_promoter_peak`;
3. DEG and gene-body peak -> `DEG_with_gene_body_peak`;
4. DEG and distal peak -> `DEG_with_distal_peak`;
5. DEG without peak -> `DEG_only`;
6. non-DEG with any associated peak -> `ChIP_only`;
7. otherwise -> `unchanged`.

There is no activation/repression concordance in the class. Direction of the
DEG and biological meaning of a mark do not change the class.

For the gene-level table, `representative_deg_status` is `up` if any contrast
is up, otherwise `down` if any contrast is down. Thus an up/down-conflicting
gene is represented as up. The contrast table recalculates the class using the
individual contrast status.

`write_gene_mark_stage_tables` adds mark `regulatory_class` and
`expected_effect` as annotations only. They do not affect integration or
ranking. It also writes a field named `max_abs_log2FC`, but the implementation
uses `max(log2FoldChange)` without `abs`. Negative-only genes therefore receive
a negative value in this relation table. This is frozen as `POTENTIAL_BUG`.

## Exact candidate-score specification

The candidate score is a **heuristic of prioritization**, not a statistical
test, probability, confidence score or model coefficient.

For each integrated gene:

```text
score = min(10, -log10(max(rna_min_padj, 1e-300))) if padj < 1 else 0
      + min(5, rna_max_abs_log2FC)
      + 2.0 if chip_promoter_peaks > 0
      + 2.0 if chip_n_differential_peaks > 0
      + 1.0 if is_gene_of_interest
      + 2.0 if is_epigenetic_machinery
      + min(3, 0.5 * rna_n_significant_contrasts)
      + min(2, 0.5 * number_of_semicolon_delimited_chip_marks)
      + 2.0 if wgcna_hit
      + 1.5 if mfuzz_hit
      + 1.0 if dtu_hit
      + 1.0 if splicing_hit
```

Important observed behavior:

- there are no penalties;
- missing/malformed numeric values become zero, except padj becomes one;
- significance and LFC contributions are awarded independently of DEG class;
- every machinery-catalog gene is also inserted into the gene-of-interest set,
  so it normally receives both the `+1` and `+2` bonuses;
- the `score_components` string lists all possible components even when they
  contributed zero;
- score is formatted with four decimal places;
- descending sort is stable, so ties retain the integrated table's gene-ID
  order;
- `TOP_CANDIDATES_N` defaults to 100.

## Formal statistics and correlation behavior

Mark enrichment defines the universe as every gene present in the scored table
or gene-mark-stage evidence. Targets are DEG genes and machinery genes. Marked
sets are constructed separately for any peak and promoter peak, by observed
stage and by `all_observed_stages`. It reports a one-sided Fisher right-tail,
fold enrichment against the hypergeometric expectation and a Haldane-Anscombe
odds ratio with 0.5 added to all four cells. BH correction is performed once
over every emitted test, without stratification.

RNA/ChIP correlations are per exact gene/mark. Only stages declared assayed for
that mark are considered, and a zero is introduced only for an assayed stage
without a linked peak. Stages without RNA expression are skipped. At least two
stage points are required. Pearson and Spearman are calculated for total and
promoter peak counts; the statistic with greatest absolute value is selected.
Two-point results are labeled `low_stage_count`; constant vectors produce no
correlation and `constant_expression_or_chip_signal`.

The `functional` command is not a statistical enrichment test. It splits one
annotation field on comma, semicolon or pipe and reports descriptive counts for
terms found in the top-N candidate set.

## R visualization audit

`visualize_integrative.R` reads only fixed paths under the output root:

- class counts, candidate scores and machinery catalog;
- ChIP mark-stage metadata and RNA expression contexts;
- gene-mark-stage summary and peak-level links;
- stage-mark comparison, mark enrichment and correlations.

It produces each global plot as PNG, PDF and SVG, plus the same three formats
for selected gene panels, `gene_panel_index.tsv` and
`visualization_manifest.tsv`. Its only package dependency is `ggplot2`; it also
uses base R `grid` graphics.

R independently canonicalizes stages and marks. It additionally treats
`all_projects`, `combined`, and broad text prefixes such as `cercar*` as
canonical values, so it is not identical to the Python vocabulary. It performs
the following display transformations:

- weighted collapse of expression by canonical stage;
- promoter fraction `n_promoter_peaks / n_peaks`;
- display position classes derived from annotation strings;
- `integrated_evidence` as the unweighted sum of DEG-linked, machinery,
  WGCNA, Mfuzz, DTU and splicing counts;
- enrichment display score `-log10(q)`, falling back to p-value when all q
  scores are zero;
- ranking and truncation for plotting and panel selection.

These transformations affect visualization and the panel index, but do not
feed Python integration, scoring or statistical tables. Images are therefore
not golden byte artifacts. The panel index and manifest are semantic outputs.

## External-input map

| Evidence | Current producer | Legacy path/config | Required or guessed columns | Scientific meaning / future source |
|---|---|---|---|---|
| RNA counts | Import API | `RNA_COUNTS_MATRIX` | gene ID or first column | only contributes gene universe; future Import manifest |
| RNA abundance | Import API | `RNA_NORMALIZED_MATRIX` | gene ID plus sample columns | expression magnitude/context; Import abundance artifact |
| RNA differential expression | DE API | `RNA_DEG_RESULTS` | gene, contrast, LFC, padj; p-value/name optional | direction/significance per contrast; DE aggregate manifest |
| RNA metadata | Metadata/Import API | `RNA_METADATA_FILE` | guessed sample and stage columns | sample-to-stage association; native metadata manifest |
| Machinery catalog | RNA Gene Report or external curation | `RNA_GENE_CATALOG[_EXTRA]` | gene, optional group/name/query | curated regulatory-gene evidence; explicit catalog manifest |
| WGCNA/Mfuzz/DTU/splicing | no current common API | four optional paths | gene plus descriptive fields | boolean supplemental evidence; future optional evidence providers |
| ChIP metadata | ChIP Metadata API | `CHIP_METADATA_FILE` | sample, mark, condition; replicate/batch optional | assay availability and mark-stage identity |
| Annotated peaks | Peak Annotation API | `CHIP_ANNOTATED_PEAKS_GLOB` | coordinates, one gene, annotation; mark/stage optional | preferred peak-gene evidence; annotation aggregate manifest |
| Consensus/IDR BED | Consensus/IDR API | `CHIP_PEAK_BED_GLOB` | BED3+, optional ID | compatibility fallback only; semantic consensus manifest |
| Peak counts | Differential Binding counting | `CHIP_PEAK_COUNT_GLOB` | none | inventoried but never consumed (`LEGACY_BEHAVIOR`) |
| Differential binding | Differential Binding API | `CHIP_DIFF_BINDING_FILE` | gene/peak/mark, LFC, padj | gained/lost peak evidence; DB aggregate manifest |
| Gene annotation | Reference Bundle | `ANNOTATION_FILE` | GTF/GFF gene/mRNA/transcript records | coordinates, names, biotype and ID universe |
| Genome FASTA | Reference Bundle | `GENOME_FASTA` | none | configured but never consumed (`LEGACY_BEHAVIOR`) |
| Functional annotation | external/reference resource | `FUNCTIONAL_ANNOTATION` | gene plus one term-like column | gene description and descriptive functional summary |
| Genes of interest | user input | `GENES_OF_INTEREST_FILE` | first token per line | ranking bonus |
| Mark catalog | legacy repository | fixed `config/chip_marks_config.tsv` | mark, regulatory class, expected effect | annotations only; no concordance calculation |

## Architectural debt not to carry forward

- shell configuration as a scientific API;
- global environment variables and mutable process state;
- discovery by globs and numbered directories;
- filename-derived sample, mark and stage identity;
- guessed scientific columns;
- `.done` markers and a cache independent of Nextflow;
- Bash step wrappers and nested standalone Slurm submission;
- generic `LEGACY_STEP` status-file dependencies;
- implicit reads of previous output directories;
- required inputs that are not actually used;
- duplicate peak annotation and RNA/ChIP summarization already available from
  native upstream APIs;
- silent defaults for malformed values;
- absolute paths and timestamps in otherwise scientific outputs;
- permissive RNA-only completion when the requested product is multi-omic.

## Characterization fixture

`tests/integrative_legacy_characterization` contains the deterministic fixture,
runner, baseline manifest, golden tables and automatic comparison. It covers:

- two RNA contrasts, up/down/non-significant and conflicting-direction genes;
- activating, repressive and chromatin-reader marks over two stages;
- promoter, gene-body and distal peaks;
- differential and non-differential binding;
- all seven integrative classes;
- modality-specific genes, machinery and gene-of-interest bonuses;
- WGCNA, Mfuzz, DTU and splicing flags;
- Fisher/BH and RNA/ChIP correlations;
- descriptive functional terms and a timestamp/path-normalized report.

The local baseline environment has Python 3.13.5 and R 4.5.1. `ggplot2` is not
installed, so no dependency chain was added. Visual behavior is specified and
classified as non-byte-critical; core, statistics, scoring, functional and
renderer-without-figures outputs are executable without external packages.

## Initial future responsibility list

The next migration stage should define, without implementing here:

1. terminal RNA and ChIP run manifests;
2. Integration preflight and compatibility schema;
3. RNA Evidence and ChIP Evidence adapters;
4. versioned ID/stage/mark vocabularies;
5. Evidence Integration and class provider;
6. versioned Candidate Prioritization provider;
7. statistical enrichment/correlation provider;
8. optional Functional Evidence provider;
9. Visualization and Integration Report providers;
10. top-level Integration aggregate manifest.

