# IntegrateSeq pipeline

Generic, organism-agnostic integration pipeline for RNA-seq and ChIP-seq result
tables. It links gene expression, differential expression, ChIP peak
annotations, differential binding, functional annotations, candidate scoring,
visualizations, and a final HTML/Markdown report.

The pipeline is organism agnostic. Any organism can be used when the required
tabular inputs and optional annotation files are supplied in
`config/pipeline_config.sh`, `config/pipeline_config.local.sh`, or the job
environment.

## Directory layout

- `000-logs/`: Slurm or local step logs
- `010-input-validation/`: input checks and validation reports
- `020-prepared-inputs/`: normalized manifests and DEG tables
- `030-id-harmonization/`: `gene_master_table.tsv` and unmapped gene report
- `040-peak-gene-mapping/`: peak-to-gene links and summaries
- `050-rnaseq-summary/`: per-gene RNA-seq summaries and DEG long table
- `060-chipseq-summary/`: per-gene ChIP-seq summaries
- `070-integrated-tables/`: integrated gene and contrast tables
- `080-candidate-scoring/`: ranked candidate genes
- `090-visualizations/`: PNG/PDF/SVG figures generated with R/ggplot2
- `100-functional-analysis/`: offline functional summaries
- `110-reports/`: final `integrative_report.md` and `.html`
- `config/`: central configuration and templates
- `scripts/`: step wrappers plus the Python core engine
- `slurm/`: notes for HPC execution
- `envs/`: optional environment definitions

## Configuration

Edit `config/pipeline_config.sh`, or preferably create
`config/pipeline_config.local.sh` for machine-specific paths. The main config
centralizes:

- base project and output directories
- RNA-seq results directory
- ChIP-seq results directory
- genome FASTA and GTF/GFF3 paths, when available
- functional annotation and genes-of-interest files, when available
- count matrix, normalized expression matrix, DEG results, and metadata
- annotated peak tables, peak BEDs, peak count matrices, and differential
  binding results
- gene/sample/contrast/mark column names
- DEG, differential binding, peak-gene window, and promoter thresholds
- Slurm/runtime settings and execution mode

When RNA-seq and ChIP-seq run on an HPC server, configure this integration
pipeline on that same server, or point it to mounted/server-side result paths.
The local Windows working copy may contain only code and metadata drafts, not
the large generated ChIP outputs. Use:

```bash
bash scripts/server_inventory.sh /server/path/rnaseq_results /server/path/chipseq_results /server/path/chipseq_work
```

Then copy `config/pipeline_config.server.template.sh` to
`config/pipeline_config.local.sh` and fill in the discovered paths.

The default RNA-seq outputs expected from the inspected pipeline are:

- `050-quantification/counts_matrix.tsv`
- `050-quantification/tpm_matrix.tsv`
- `060-deg-analysis/DEGs_annotated_results.tsv`
- `025-parse/030-metadata_final/AllProjects_metadata_new.csv`

The default ChIP-seq outputs expected from the inspected pipeline are:

- `090-peak-annotation/*.annotated.tsv`
- `110-consensus-peaks/groups/*.consensus.bed`
- `110-consensus-peaks/counts/*.counts.tsv`
- `120-differential-binding/differential_binding_results.tsv`

ChIP-seq files can be absent during early development. Validation reports this
as a warning, and RNA-only integration outputs can still be generated.

### Adding PRJNA1090249 SmHP1 ChIPmentation

To add the SmHP1/HP1 data from PRJNA1090249 to a project that already contains
SRP034587 outputs, process PRJNA1090249 with the same genome build and ChIP-seq
workflow used for the current integration. The important point is to carry a
sample metadata table into the integration step with explicit factor labels:

```text
sample_id	mark_or_factor	condition	replicate	bioproject
<run_or_sample>	SmHP1	cercariae	1	PRJNA1090249
<run_or_sample>	SmHP1	sporocysts	1	PRJNA1090249
```

Recommended order:

1. Download the PRJNA1090249 SRA run table and FASTQ files on the Slurm server.
2. Process those FASTQs through the ChIP/ChIPmentation workflow: QC/trimming,
   alignment to the same S. mansoni genome, duplicate handling, peak calling,
   consensus/count generation, differential binding, and peak annotation.
3. Add the annotated peak tables, BEDs, count matrices, and differential binding
   table to the existing ChIP result globs in `config/pipeline_config.local.sh`.
4. Set `CHIP_METADATA_FILE` to the table containing `mark_or_factor=SmHP1` and
   `condition=cercariae` or `sporocysts`.
5. Re-run the integration from `validate` onward, using `--force` for completed
   steps that need to be regenerated.

The pipeline now canonicalizes `HP1`, `SmHP1`, `Sm-HP1`, `CBX`, and
`Smp_179650` as `SmHP1`. Any remaining `unknown_ChIP` labels after re-running
usually mean that a ChIP file or metadata row still lacks a recognizable
mark/factor label.

## Running

Dry-run the full workflow:

```bash
bash integrative_pipeline.sh --all --dry-run
```

Run selected steps:

```bash
bash integrative_pipeline.sh --step validate --step prepare --step harmonize
```

Run the full workflow:

```bash
bash integrative_pipeline.sh --all
```

The Slurm chain is:

```text
validate -> prepare -> harmonize -> map-peaks -> summarize-rna -> summarize-chip -> integrate -> score -> visualize -> functional -> report
```

Each step writes a `.done` marker. Use `--force` to re-run completed steps.

## Expected input tables

RNA-seq DEG tables should contain at least:

- `gene_id`
- `log2FoldChange` or equivalent
- `padj` or equivalent

Optional useful columns are `contrast_id`, `gene_name`, `baseMean`, `lfcSE`,
`stat`, and `pvalue`.

Annotated ChIP-seq peak tables should contain at least:

- `peak_id`
- `chrom`
- `start`
- `end`
- `gene_id` or `nearest_gene_id`

Optional useful columns are `gene_name`, `mark_or_factor`, `condition`,
`distance_to_tss`, and `genomic_annotation`. If annotated peak tables are not
available, the pipeline can use BED-like peak files plus a gene master table
with genomic coordinates to create window-based links.

## Integrative classes

The pipeline assigns genes to transparent, configurable classes:

- `DEG_only`
- `ChIP_only`
- `DEG_with_promoter_peak`
- `DEG_with_gene_body_peak`
- `DEG_with_distal_peak`
- `DEG_with_differential_peak`
- `unchanged`

The current implementation records association classes conservatively. Mark
biology is documented in `config/chip_marks_config.tsv` and can be extended for
project-specific concordance interpretation.

## Candidate score

`080-candidate-scoring/candidate_gene_scores.tsv` reports a transparent additive
score using:

- DEG adjusted p-value
- RNA-seq absolute log2 fold change
- promoter peak presence
- differential peak presence
- user-provided gene-of-interest membership
- significance across multiple contrasts
- evidence across multiple ChIP marks/factors

The score is designed for ranking and triage, not as a statistical test.

## Outputs

Key outputs are:

- `030-id-harmonization/gene_master_table.tsv`
- `040-peak-gene-mapping/peak_to_gene.tsv`
- `040-peak-gene-mapping/gene_to_peak_summary.tsv`
- `050-rnaseq-summary/rna_gene_summary.tsv`
- `050-rnaseq-summary/rna_expression_by_context.tsv`
- `050-rnaseq-summary/rna_sample_group_mapping.tsv`
- `060-chipseq-summary/chip_gene_summary.tsv`
- `070-integrated-tables/integrated_gene_table.tsv`
- `070-integrated-tables/integrated_by_contrast.tsv`
- `070-integrated-tables/gene_mark_stage_links.tsv`
- `080-candidate-scoring/candidate_gene_scores.tsv`
- `080-candidate-scoring/top_candidates.tsv`
- `080-candidate-scoring/ranked_gene_mark_stage_evidence.tsv`
- `080-candidate-scoring/stage_mark_comparison.tsv`
- `080-candidate-scoring/candidate_regulators.tsv`
- `080-candidate-scoring/mark_enrichment_tests.tsv`
- `080-candidate-scoring/gene_mark_stage_signal_matrix.tsv`
- `080-candidate-scoring/gene_mark_stage_correlations.tsv`
- `090-visualizations/gene_position_mark_map.png`
- `090-visualizations/stage_mark_integrated_evidence.png`
- `090-visualizations/mark_enrichment_tests.png`
- `090-visualizations/gene_mark_stage_correlations.png`
- `090-visualizations/gene_panels/<gene_id>_gene_panel.png`
- `090-visualizations/gene_panel_index.tsv`
- `090-visualizations/visualization_manifest.tsv`
- `110-reports/integrative_report.html`

`gene_mark_stage_links.tsv` is the main association table for the biological
question. It links each gene to mark/factor, stage/condition, peak ID, peak
coordinates, relative position to the TSS when available, and RNA evidence.
`ranked_gene_mark_stage_evidence.tsv` adds the candidate score, WGCNA, Mfuzz,
DTU, splicing, epigenetic machinery class, and functional annotation fields.
`stage_mark_comparison.tsv` summarizes those links by life-cycle stage and
epigenetic mark.
`mark_enrichment_tests.tsv` formally tests whether ChIP marks are enriched in
DEGs and epigenetic machinery genes, separately for any linked peak and promoter
peaks. `gene_mark_stage_signal_matrix.tsv` and
`gene_mark_stage_correlations.tsv` correlate mean RNA expression with linked
ChIP evidence by gene and mark across assayed stages; zeros are included only
when a mark was assayed in that stage and no linked peak was found.
Peak files whose names indicate pooled/global calls, such as `all`, are labeled
as `all_stages`; truly unresolved ChIP labels remain `unknown_ChIP` or
`unknown`.
The visualization step also creates gene-specific RNA + ChIP panels for the
top `GENE_PANEL_TOP_N` linked candidates. Set `GENE_PANEL_GENES` to a
comma-separated list of gene IDs to force specific genes into this panel set.
Set `GENE_PANEL_TOP_N=0` to skip those per-gene panels during quick test runs.
Use `GENE_PANEL_WIDTH` and `GENE_PANEL_HEIGHT` to make the generated panels
larger when preparing final figures.
The global `gene_position_mark_map.png` uses a separate limit:
`GENE_POSITION_MAP_TOP_N` controls how many ranked genes appear in that overview
plot. Use `GENE_POSITION_MAP_WIDTH` and `GENE_POSITION_MAP_HEIGHT` when many
genes are shown and the map needs more space.
In those panels, detailed RNA contexts are collapsed to canonical life-cycle
stages so expression, ChIP mark, and peak-position evidence can be compared in
one readable view.

## Troubleshooting

- Missing RNA matrices are fatal. Missing ChIP outputs are warnings so the
  integration can proceed while the ChIP-seq pipeline is still being generated.
- If RNA expression appears only as `unknown` in gene panels, inspect
  `050-rnaseq-summary/rna_sample_group_mapping.tsv`. The `mapping_status`
  column shows whether each expression matrix column was matched to metadata,
  matched by substring, inferred from the sample name, or left unmapped.
- If the RNA metadata uses non-standard stage columns, set
  `RNA_STAGE_COLUMNS` to a comma-separated list of those columns before running
  `summarize-rna`.
- If no GTF/GFF3 is provided, `gene_master_table.tsv` is built from gene IDs
  found in RNA-seq, DEG, ChIP, functional annotation, and genes-of-interest
  files.
- The visualization step uses R/ggplot2. On servers that already run the
  RNA-seq pipeline, set `ENV_BACKEND=conda`, `CONDA_BASE`, and
  `VISUALIZATION_CONDA_ENV=r-analysis`.
- If Slurm reports `Required command not found in PATH: Rscript`, point
  `VISUALIZATION_CONDA_ENV` to the RNA-seq/R conda environment that contains
  `Rscript`, or set `RSCRIPT_BIN` to the full `Rscript` path.

## Adapting to another organism

1. Provide organism-specific FASTA/GTF/GFF3 only if peak mapping or coordinates
   are needed.
2. Point RNA and ChIP input variables in `config/pipeline_config.local.sh` to
   your result tables.
3. Adjust column names and thresholds in the same config.
4. Edit `config/chip_marks_config.tsv` for marks/factors in your experiment.
5. Run `bash integrative_pipeline.sh --all --dry-run`, then run locally or via
   Slurm.
