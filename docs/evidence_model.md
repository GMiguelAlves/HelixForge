# Standardized Evidence Model v1

Contract identifier: `helixforge.evidence_model`  
Contract version: `1.1`

Version 1.1 adds the complete Integration API `reference` object to the
Evidence Manifest. Version 1.0 remains structurally readable, but cross-assay
integration requires 1.1 because a bare `reference_id` cannot prove organism,
assembly, genome and annotation compatibility.

The Evidence Model is the anti-corruption boundary between terminal assay
outputs and the molecular evidence integration engine. RNA and ChIP providers
translate artifacts independently; joining and harmonization are performed only
by the downstream [Cross-Assay Integration v1](cross_assay_integration.md).
Providers do not classify regulation, score candidates or perform enrichment.

## Physical contract

Provider metadata is JSON and row-oriented evidence is TSV. This combination is
portable between Python and R, diffable in reviews, streamable for larger
datasets and requires no Arrow/database dependency. The manifest validates with
`schemas/evidence/evidence-manifest.schema.json`; each TSV record type has a
matching row schema in the same directory.

```text
terminal run manifest + explicit artifact bindings
                    |
                    +--> evidence_manifest.json
                    +--> typed TSV datasets that are actually available
```

Empty optional datasets are omitted. The manifest catalog contains each source
artifact and its producer provenance once. Evidence rows reference it through
`source_artifact_id`, avoiding repeated tool/container metadata in every row.

## Common identity

Every row has a stable `evidence_id`, a typed scientific entity and its
`source_artifact_id`. Gene-bearing rows preserve `source_entity_id` exactly.
`normalized_entity_id` is empty and `normalization_rule=none` in v1: version
stripping, alias resolution and cross-assay namespace harmonization are deferred
to a reviewed harmonization provider.

Conditions, stages and marks come from the terminal manifest or explicit table
columns. The provider does not infer them from filenames, aliases or substrings.

## RNA evidence

| Type | Source artifact | Meaning and unit | Required scientific fields |
|---|---|---|---|
| `expression` | `gene_counts` | imported gene counts; `counts` | gene, sample, value, unit |
| `expression` | `gene_abundance` | imported gene abundance; `TPM` | gene, sample, value, unit |
| `expression` | `normalized_counts` | DE model exploratory abundance; `normalized_counts` | gene, sample, value, unit |
| `differential_expression` | DE result/summary | producer effect and tests, normally DESeq2 | gene, declared contrast, log2 fold change; p-value/padj/base mean/SE/statistic when available |

Units remain separate per row and are never summed by the provider. Valid NA
statistics are represented as empty TSV fields. No new significance threshold,
direction class or effect interpretation is applied.

Outputs, when populated:

```text
rnaseq_evidence/
├── evidence_manifest.json
├── expression.tsv
└── differential_expression.tsv
```

## ChIP evidence

| Type | Source artifact | Meaning |
|---|---|---|
| `peak` | replicate `peak_set` | exact interval and available narrowPeak/broadPeak metrics |
| `peak_gene` | `peak_gene_annotation` | existing Peak Annotation API association; mapping is not repeated |
| `consensus` | `consensus_peaks` or `idr_peaks` | condition/mark interval with strategy and support when supplied |
| `differential_binding` | contrast or aggregate DB results | exact regional effect and test statistics from the producer |

Narrow and broad peaks retain different `peak_type` values. Missing narrowPeak
summit or score fields remain missing and are not invented. A gene on a binding
record is optional because the native DB API is region-level; association is a
separate evidence type.

Outputs, when populated:

```text
chipseq_evidence/
├── evidence_manifest.json
├── peaks.tsv
├── peak_gene.tsv
├── consensus.tsv
└── differential_binding.tsv
```

## Terminal artifact classification

| Artifact | Classification | v1 behavior |
|---|---|---|
| expression, DE, peaks, consensus/IDR, peak-gene, DB | `INTEGRATION_EVIDENCE` | converted when explicitly bound |
| BAM and peak QC | `SUPPORTING_ARTIFACT` | catalog only |
| BigWig/signal tracks | `VISUALIZATION_ARTIFACT` | catalog only |
| final reports and remaining terminal products | `PROVENANCE_ONLY` | catalog only |

The modules should stage only integration evidence. Catalog classification does
not authorize a process to open a non-bound artifact.

## Input bindings and Nextflow

The terminal manifest describes semantic locations, including
`producer_relative` locations, but a task must not dereference those locations
outside its work directory. The DSL2 modules therefore receive:

```text
run_manifest + bindings.json + declared_artifacts (path inputs)
```

Each binding maps `artifact_id` to `declared_index` and optionally a
`relative_path` within a staged directory. The provider rejects any resolved
file outside the declared inputs. This makes caching, staging and lineage
visible to Nextflow while keeping the scientific API independent of a published
results layout.

## Validation

- **Schema:** manifest envelope and typed record schemas.
- **Semantic:** unique evidence and observations, known contrasts and source
  artifacts, p-values in `[0,1]`, required gene/peak/mark identity, and valid
  interval coordinates.
- **Filesystem:** declared bindings, produced files, record counts and SHA-256.

Scientifically valid NA values are accepted. Duplicate gene/contrast or
peak/contrast observations from the same artifact are rejected.

## Legacy equivalence map

| Legacy output | Standardized source | Equivalence used in tests |
|---|---|---|
| `rna_deg_long.tsv` | `differential_expression.tsv` | gene + contrast; effect, p-value and padj numeric equality |
| `rna_expression_by_context.tsv` | `expression.tsv` | mean of explicit TPM sample rows grouped by manifest stage |
| `rna_gene_summary.tsv` | expression + DE rows | derived summary, intentionally not a provider output |
| `chip_differential_long.tsv` | `differential_binding.tsv` | peak/gene effect and padj equality |
| `chip_gene_summary.tsv` | peak-gene + DB rows | derived summary, intentionally not a provider output |
| `chip_mark_stage_metadata.tsv` | terminal manifest samples | assay inventory, not duplicated as molecular evidence |

The legacy `prepare` path manifest disappears. Legacy threshold classes
(`up/down`, `gained/lost`) are reproducible derived projections but are not
primary evidence. Absolute paths, glob matches, filename-derived identity and
`.done` files are intentionally excluded.

## Provider limits

- Providers do not perform cross-assay ID, condition, stage or mark
  harmonization; the downstream engine owns those operations.
- A peak-gene dataset can be validated against bound peak datasets; if the
  terminal run exposes only aggregate annotation, referential validation is
  limited to non-empty peak identity.
- Consensus support is available only when the declared artifact contains it;
  a BED-only terminal artifact cannot supply support values.
- External producers must use the same Integration API semantics and explicit
  bindings; format-specific external adapters are not part of v1.
