# RNA-seq Report API

Contract version: `1.0`

The RNA-seq Report API turns provider-neutral Import and Differential
Expression outputs into terminal scientific tables, figures and HTML. It never
discovers upstream results by directory name and never schedules upstream work.

## Request

Each request contains:

- `meta`: stable `id`, `provider`, `target_dir`, upstream import identity and
  differential-expression analysis identity;
- Import API `manifest.json`;
- gene-level abundance matrix (`gene_id` followed by ordered sample columns);
- Import API sample table whose `import_id` order exactly matches the matrix;
- reference annotation from the Reference Bundle;
- Differential Expression API `DEGs_all_results.tsv` and manifest;
- explicit candidate-gene group file;
- versioned provider parameters.

All files are `path` inputs and therefore participate in the Nextflow task
hash. The context process verifies manifest types, declared Import checksums,
sample order, unique gene IDs, numerical non-negative abundances, required DE
columns and candidate-gene syntax before the R provider runs.

Candidate groups use the unchanged legacy syntax:

```text
Receptors: gene_a, gene_b
Signalling: gene_c; gene_d
```

## Provider

`candidate_genes_v1` is the first provider. It executes the established
`gene_set_report.R` script unchanged with explicit arguments. The old
`gene_report_job.sh` scheduler wrapper is retired. DE input discovery is
confined to a task-local directory containing only the aggregate file supplied
by the Differential Expression API.

Parameters are:

- `title`;
- `expression_unit`: `TPM` or `CPM`;
- `life_stage_levels`;
- `stage_synonym_map`;
- `organism_specific`.

The production Salmon path defaults to `TPM`. Parameters that influence output
are explicit cache inputs and recorded in the context and final manifest.

## Response

The provider publishes a legacy-compatible `results/` tree containing:

- `gene_set_report.html`;
- `tables/` with the gene catalog, expression summaries and DEG hits;
- `plots/`, `genes/` and `groups/` scientific figures;
- `manifest.json`, `execution.json`, `versions.yml`, `sessionInfo.txt`,
  `context.json` and `report.log`.

The `rnaseq_report` manifest records provider, parameters, sample/gene/query
counts, upstream manifest checksums and a SHA-256 inventory. Report results are
presentation/exploration products; they do not feed DESeq2 inference.

The `candidate_genes_v1` runtime is certified as image `1.0.0`, pinned by OCI
digest in `nextflow.config`. Certification executes the real R provider and
requires its semantic table, figure, HTML, manifest and session assertions to
pass after every image build.

## Execution modes

The report is opt-in during `full` runs:

```bash
nextflow run . --workflow rnaseq --rnaseq_run_mode full \
  --rnaseq_report_enabled true \
  --rnaseq_report_genes /path/to/genes.txt
```

`--rnaseq_run_mode report` requests it explicitly. Both forms require native
Import and Differential Expression. `de` deliberately stops at DE aggregation.
The default publish root is `<outdir>/rnaseq/090-search-gene`; override it with
`--rnaseq_report_outdir`.

## Future providers

KEGG, GO, Reactome and organism-specific pathway enrichment belong in future
providers that consume the same manifests and gene universe. They must not be
silently embedded in `candidate_genes_v1`, and database version, identifier
mapping, background universe and multiple-testing policy must be explicit.
