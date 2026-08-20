# Integrative RNA-seq + ChIP-seq report

Generated: <TIMESTAMP>

## Inputs

- RNA counts matrix: ok
- RNA normalized matrix: ok
- RNA DEG results: ok
- RNA metadata: ok
- RNA epigenetic machinery catalog: ok
- RNA supplemental epigenetic catalog: warning missing or empty
- RNA expression by context: warning missing or empty
- RNA WGCNA hits: ok
- RNA Mfuzz hits: ok
- RNA DTU hits: ok
- RNA splicing hits: ok
- ChIP metadata: ok
- ChIP differential binding: ok
- Genome annotation: ok
- Functional annotation: ok
- ChIP annotated peaks: ok 1 matching file(s)
- ChIP peak BEDs: warning 0 matching file(s)
- ChIP peak counts: warning 0 matching file(s)
- RNA matrix gene overlap: ok 8 genes
- RNA DEG/expression gene overlap: ok 8 genes

## Summary

- Genes in integrated table: 8
- Epigenetic machinery genes in catalog: 2
- ChIP mark/stage metadata combinations: 6
- Gene-mark-stage links from annotated peaks: 9
- Formal mark enrichment tests: 34
- Gene-mark RNA/ChIP stage correlations: 6

### ChIP marks by stage/condition

- adult: H3K27ac (1 sample[s])
- adult: H3K27me3 (1 sample[s])
- adult: SmHP1 (1 sample[s])
- cercariae: H3K27ac (1 sample[s])
- cercariae: H3K27me3 (1 sample[s])
- cercariae: SmHP1 (1 sample[s])

### Integrative classes

- ChIP_only: 2
- DEG_only: 1
- DEG_with_differential_peak: 1
- DEG_with_distal_peak: 1
- DEG_with_gene_body_peak: 1
- DEG_with_promoter_peak: 1
- unchanged: 1

### Top candidates

- geneA score=16.0000 class=DEG_with_differential_peak
- geneB score=8.8979 class=DEG_with_promoter_peak
- geneF score=5.7458 class=ChIP_only
- geneC score=5.1990 class=DEG_with_gene_body_peak

### Gene-mark-stage outputs

- `070-integrated-tables/gene_mark_stage_links.tsv`: one row per peak-gene-mark-stage association.
- `070-integrated-tables/gene_mark_stage_summary.tsv`: collapsed catalog by gene, mark, and stage.
- `070-integrated-tables/mark_to_gene_catalog.tsv`: marks with linked genes and epigenetic machinery counts.
- `080-candidate-scoring/ranked_gene_mark_stage_evidence.tsv`: ranked gene-mark-stage associations with RNA, WGCNA, Mfuzz, DTU, and splicing evidence.
- `080-candidate-scoring/stage_mark_comparison.tsv`: stage-by-mark comparison table.
- `080-candidate-scoring/candidate_regulators.tsv`: high-priority regulators supported by epigenetic machinery or RNA network/isoform evidence.
- `080-candidate-scoring/mark_enrichment_tests.tsv`: formal mark enrichment tests in DEG and epigenetic machinery gene sets.
- `080-candidate-scoring/gene_mark_stage_correlations.tsv`: stage-by-stage RNA expression versus ChIP evidence correlations by gene and mark.
- `080-candidate-scoring/gene_mark_stage_signal_matrix.tsv`: long RNA/ChIP signal matrix used for the correlations.
- `090-visualizations/gene_panel_index.tsv`: index of gene-specific RNA + ChIP figure panels.

## Limitations

- ChIP-seq links are associations between peaks and genes, not proof of causality.
- Concordance depends on mark/factor biology configured in config/chip_marks_config.tsv.
- Offline functional analysis uses supplied annotation only.

## Key generated files

- 030-id-harmonization/gene_master_table.tsv
- 040-peak-gene-mapping/peak_to_gene.tsv
- 070-integrated-tables/integrated_gene_table.tsv
- 080-candidate-scoring/candidate_gene_scores.tsv
- 080-candidate-scoring/mark_enrichment_tests.tsv
- 080-candidate-scoring/gene_mark_stage_correlations.tsv
- 090-visualizations/gene_panel_index.tsv
- 090-visualizations/visualization_manifest.tsv
- 100-functional-analysis/functional_enrichment.tsv
