# 090-search-gene

Optional exploratory report for genes or gene groups of interest. It combines
the configured expression matrix, sample metadata, GFF/GTF annotation, and DEG
results.

The expression matrix is selected by `EXPRESSION_MATRIX_FILE`:

- Salmon mode uses `050-quantification/tpm_matrix.tsv` and reports TPM.
- STAR mode uses `050-quantification/star_cpm_matrix.tsv` and reports CPM.

When a GFF3 or GTF annotation is available, the report tables include gene
name, biotype, description, chromosome, start, end, strand, and genomic
location.

## Before You Run

Confirm these exist:

```text
050-quantification/tpm_matrix.tsv or 050-quantification/star_cpm_matrix.tsv
050-quantification/quant_samples.tsv
060-deg-analysis/
010-reference/data/<annotation.gff3-or.gtf>
```

Create a gene list:

```text
090-search-gene/genes.txt
```

Format:

```text
Group A: GENE0001, GENE0002
Group B: annotated_gene_name, another_gene
```

Gene entries can be IDs present in the expression matrix or names available in
the GFF/GTF annotation.

## Optional Organism-Specific Ordering

The report is generic by default. To impose an organism-specific stage order,
set these in `config/pipeline_config.sh`:

```bash
export LIFE_STAGE_LEVELS="stage1,stage2,stage3,unknown"
export STAGE_SYNONYM_MAP="regex1=stage1,regex2=stage2"
```

Set `ORGANISM_SPECIFIC_REPORTS=1` only when the optional hard-coded panel is
meaningful for the organism and metadata.

## Run

Normally `rnaseq_pipeline.sh` submits this step when `RUN_GENE_REPORT=1`. To run manually:

```bash
bash scripts/090-search-gene/run_gene_report_slurm.sh \
  --genes "$PWD/090-search-gene/genes.txt" \
  --title "Candidate genes"
```

The wrapper uses `EXPRESSION_MATRIX_FILE`, `EXPRESSION_UNIT`, and
`GENE_REPORT_ANNOTATION_FILE` from `config/pipeline_config.sh`. Override them
only when running a custom report:

```bash
bash scripts/090-search-gene/run_gene_report_slurm.sh \
  --genes "$PWD/090-search-gene/genes.txt" \
  --tpm "$PWD/050-quantification/star_cpm_matrix.tsv" \
  --expression-unit CPM \
  --gff "$PWD/010-reference/data/annotation.gtf"
```

Without Slurm:

```bash
bash scripts/090-search-gene/run_gene_report_slurm.sh \
  --genes "$PWD/090-search-gene/genes.txt" \
  --title "Candidate genes" \
  --local
```

Preview only:

```bash
bash scripts/090-search-gene/run_gene_report_slurm.sh \
  --genes "$PWD/090-search-gene/genes.txt" \
  --sbatch-dry-run
bash scripts/090-search-gene/run_gene_report_slurm.sh \
  --genes "$PWD/090-search-gene/genes.txt" \
  --local \
  --sbatch-dry-run
```

## Outputs

- `090-search-gene/results/gene_set_report.html`
- `090-search-gene/results/tables/gene_catalog.tsv`
- `090-search-gene/results/tables/gene_expression_summary.tsv`
- `090-search-gene/results/tables/expression_long.tsv`
- `090-search-gene/results/tables/expression_summary_by_context.tsv`
- `090-search-gene/results/tables/deg_hits.tsv`
- `090-search-gene/results/plots/`
- `090-search-gene/results/groups/<group>/`
- `090-search-gene/results/genes/<group>/<gene>/`
