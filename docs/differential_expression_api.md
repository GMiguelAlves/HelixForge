# Differential Expression API

API version: `1.0`

The Differential Expression API consumes only the stable output envelope of
the Import API and projects provider-specific statistics into common semantic
roles. RNA-seq workflows call `DIFFERENTIAL_EXPRESSION`; they never call
DESeq2, edgeR, or limma directly.

## Input boundary

An analysis request has this logical shape:

```nextflow
tuple val(meta), path(import_manifest), path(counts), path(sample_metadata),
      path(analysis_spec), path(annotation)
```

Required `meta` fields are `id`, `provider`, `analysis_id`, and `target_dir`.
The API rejects FASTQ, BAM, `quant.sf`, STAR directories, Salmon directories,
and paths reconstructed from a provider-specific layout.

The Import manifest must declare the supplied count matrix and sample metadata
as available artifacts. Their SHA-256 values are validated before statistical
execution.

## Analysis specification

The versioned JSON specification contains:

```json
{
  "schema_version": "1.0",
  "provider": "deseq2",
  "test": "wald",
  "design": {
    "variable": "condition",
    "covariates": ["batch"],
    "formula": "~ batch + condition"
  },
  "contrasts": [
    {
      "id": "condition__treated_vs_control",
      "factor": "condition",
      "numerator": "treated",
      "denominator": "control",
      "description": "treated versus control",
      "direction": "treated/control"
    }
  ],
  "filter": {
    "method": "none"
  },
  "parameters": {
    "alpha": 0.05,
    "lfc_threshold": 1,
    "min_replicates": 2,
    "non_integer_counts": "round"
  }
}
```

The formula is explicit and ordered. Every contrast declares its factor,
numerator, denominator, description, and direction. Contrast IDs must be
unique and filename-safe.
At least one contrast is required. The pipeline never invents pairwise
comparisons. Filtering must select `none` or `total_count`; the latter requires
an explicit non-negative threshold and `>` or `>=`. Fractional counts require
an explicit `round` policy or the analysis fails.

## Preflight validation

Validation occurs before DESeq2 and fails when:

- count sample IDs or metadata `import_id` values are missing or duplicated;
- count and metadata sample sets differ;
- count values are non-numeric, non-finite, or negative;
- a design field is absent or empty;
- a contrast factor differs from the design variable;
- numerator or denominator levels do not exist;
- numerator equals denominator;
- a selected level has fewer than `min_replicates` samples;
- the model matrix is rank deficient.

Metadata values are preserved exactly. Empty design/covariate values, inadequate
replication for a requested contrast, and rank-deficient designs are fatal
input errors with an explanatory message.

For Salmon imports, preflight also validates the tximport strategy. Full-length
libraries require `scaledTPM` or `lengthScaledTPM` for this matrix-based
provider; 3′ tagged libraries require `countsFromAbundance=no`. Original
full-length counts without the tximport length offset are rejected. A future
provider will accept the complete tximport object and use
`DESeqDataSetFromTximport`.

## Provider contract

`DESEQ2_MODEL` receives one validated design bundle and emits:

- serialized provider model (`dds_<variable>.rds`);
- normalized counts;
- dispersions and coefficients;
- design/sample metadata;
- PCA and top-variable-gene heatmap;
- versions, session information, execution metadata, manifest, and status.

`DESEQ2_CONTRAST` receives one model and one explicit contrast and emits:

- a legacy-compatible result table;
- a common result table;
- contrast statistics and volcano plot;
- versions, execution metadata, partial manifest, and status.

Differential Expression API 1.0 implements Wald only. An `lrt` request fails
with an explicit unsupported-provider error because the legacy pipeline does
not run LRT. No synthetic LRT result is produced.

## Common outputs

Every successful contrast exposes:

| Role | Required fields |
|---|---|
| `results` | `gene_id`, `baseMean`, `log2FoldChange`, `lfcSE`, `statistic`, `pvalue`, `padj`, `contrast`, `design` |
| `metadata` | analysis, factor, numerator, denominator, direction, sample count, gene count |
| `normalized_counts` | gene-by-sample normalized count matrix, when the provider supports it |
| `versions` | R, Bioconductor, provider, plotting/runtime packages |
| `execution_metadata` | command, resources, profile, Git commit, hashes, elapsed time |
| `manifest` | input and output checksums plus semantic availability |
| `status` | complete, skipped, or failed validation |

DESeq2-specific artifacts remain additive and must not be required by generic
downstream consumers.

## Legacy fallback

The native provider retains default `DESeq()` Wald fitting and the established
result/plot layout, but it no longer copies unsafe implicit behavior. Legacy
scripts remain executable through `rnaseq_native_de=false`. That fallback may
still derive pairwise comparisons and filter at `rowSums > 10`, but the
top-level workflow now feeds it directly from quantification and never schedules
the legacy batch-correction step. The batch utilities remain available only for
manual exploratory comparison and their matrices are not inferential inputs.

Batch is retained in the model when declared by the analysis specification.
For example, `covariates=["batch"]` requires the exact ordered formula
`~ batch + condition`. The same preflight rejects missing values, complete
confounding, and rank-deficient model matrices.

## Cache boundary

Model cache keys include counts, sample metadata, design, model parameters,
annotation version, provider code, and runtime. A contrast is a separate task,
so changing one contrast reruns that contrast and its aggregate only, not the
fitted model or unrelated contrasts. Documentation files are never process
inputs and do not affect scientific cache keys.

## Future providers

edgeR and limma-voom providers must consume the same validated bundle and emit
the same common results. Provider-native measures such as edgeR `logCPM` or
limma `AveExpr` may be additive. Provider dispatch changes only inside
`DIFFERENTIAL_EXPRESSION`; RNA-seq wiring and downstream consumers remain
unchanged.
