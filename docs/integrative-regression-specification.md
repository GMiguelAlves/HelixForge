# Integrative legacy regression specification

This specification defines how future native Integration providers are compared
with the frozen stage-1 legacy baseline. It deliberately distinguishes
scientific identity from volatile presentation metadata.

## Equivalence classes

| Class | Rule |
|---|---|
| `BYTE_EXACT` | file bytes must match after documented line-ending normalization |
| `TABLE_EXACT` | header, row order, strings, IDs and classes must match |
| `TABLE_NUMERIC_TOLERANCE` | table shape/order/text fields match; finite numeric values use absolute tolerance `1e-8` and relative tolerance `1e-7` |
| `SET_EQUALITY` | same normalized records independent of row order |
| `ORDERED_RANKING` | same ordered gene IDs and equal score values within numeric tolerance |
| `SEMANTIC_EQUIVALENCE` | required fields/assertions match after removing declared volatile fields |
| `VISUAL_NOT_REGRESSION_CRITICAL` | existence/manifest/semantic inputs are checked; image bytes are not compared |

## Golden-output policy

The golden tree stores normalized small text artifacts only. Normalization:

- converts CRLF to LF;
- replaces the absolute fixture root with `<FIXTURE_ROOT>`;
- replaces generated ISO timestamps with `<TIMESTAMP>` in reports;
- ignores `.done`, scheduler logs, temporary files and resource telemetry.

No numeric value, ID, class, mark, stage, rank, p-value or q-value is changed by
normalization.

## Output comparison matrix

| Output family | Representative files | Future equivalence |
|---|---|---|
| prepared DEG and metadata | `rnaseq_deg_normalized.tsv`, `metadata_combined.tsv` | TABLE_EXACT |
| gene harmonization | `gene_master_table.tsv`, `unmapped_genes.tsv`, machinery catalog | TABLE_EXACT |
| peak-gene mapping | `peak_to_gene.tsv`, promoter/distal links, gene summary | TABLE_EXACT; source paths normalized |
| RNA summaries | gene, context, sample mapping and DEG-long tables | TABLE_NUMERIC_TOLERANCE |
| ChIP summaries | gene summary, DB-long and mark-stage tables | TABLE_NUMERIC_TOLERANCE |
| integrated tables | gene, contrast, class counts, gene-mark-stage tables | TABLE_EXACT except formatted numeric columns may use tolerance |
| candidate score | candidate table and top candidates | ORDERED_RANKING; component string exact |
| secondary ranking | by contrast, mark, gene-mark-stage and regulators | TABLE_EXACT / ORDERED_RANKING |
| Fisher/BH | `mark_enrichment_tests.tsv` | TABLE_NUMERIC_TOLERANCE; test universe and row order exact |
| correlations | signal matrix and correlations | TABLE_NUMERIC_TOLERANCE; stages and selected best statistic exact |
| functional summary | `functional_enrichment.tsv` | TABLE_EXACT |
| Markdown report | normalized Markdown | SEMANTIC_EQUIVALENCE |
| HTML report | normalized HTML | SEMANTIC_EQUIVALENCE; required sections/tables |
| plots | PNG/PDF/SVG | VISUAL_NOT_REGRESSION_CRITICAL |
| visualization inventory | panel index and visualization manifest | SEMANTIC_EQUIVALENCE |

## Intentional future deviations

A future implementation may fix a `POTENTIAL_BUG` or remove a compatibility
heuristic only through an explicit scientific-deviation record. The regression
must first show the legacy difference, then assert the reviewed new behavior.
Silent baseline updates are forbidden.

Known candidates for reviewed deviation are:

- `max_abs_log2FC` computed without an absolute value in gene-mark-stage links;
- gene-list lines beginning with `gene` being discarded;
- metadata substring and filename-based identity inference;
- unused promoter-window parameters and nearest-boundary BED rescue;
- machinery genes receiving both gene-interest and machinery score bonuses;
- descriptive functional counts being named enrichment;
- Python/R stage and mark canonicalization differences.

