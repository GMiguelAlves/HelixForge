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
  "parameters": {
    "alpha": 0.05,
    "lfc_threshold": 1,
    "min_replicates": 2,
    "min_total_count": 10
  }
}
```

The formula is explicit and ordered. Every contrast declares its factor,
numerator, denominator, description, and direction. Contrast IDs must be
unique and filename-safe.

Compatibility mode derives one specification per available legacy test
variable. It generates all pairwise level combinations in the same order as
the legacy R script and retains the legacy direction `level_a vs level_b`.

## Preflight validation

Validation occurs before DESeq2 and fails when:

- count sample IDs or metadata `import_id` values are missing or duplicated;
- count and metadata sample sets differ;
- count values are non-numeric;
- a design field is absent or empty;
- a contrast factor differs from the design variable;
- numerator or denominator levels do not exist;
- numerator equals denominator;
- a selected level has fewer than `min_replicates` samples;
- the model matrix is rank deficient.

In compatibility mode, variables with fewer than two sufficiently replicated
levels and rank-deficient designs retain the legacy behavior: they are emitted
as skipped analyses in the summary rather than treated as fatal global input
errors.

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

## Legacy compatibility

The DESeq2 provider preserves:

- integer rounding and negative-count truncation;
- strict `rowSums(counts) > 10` filtering;
- per-variable models;
- minimum two replicates per retained level;
- covariate pruning and formula ordering;
- default `DESeq()` Wald fitting;
- `results(..., alpha=0.05)` behavior;
- `padj < 0.05 && abs(log2FoldChange) >= 1` significance;
- annotation normalization, plots, filenames, and aggregate table layout.

Compatibility outputs remain under `<DEG_DIR>/<scope>/<correction>/`. The
legacy scripts remain executable through `rnaseq_native_de=false`.

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
