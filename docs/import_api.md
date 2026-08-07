# Import API

Import API version: `1.0`

The Import API converts provider-specific quantification artifacts into a
stable gene-level representation. Downstream batch correction, differential
expression, and reporting consume only this representation and never inspect
Salmon or STAR files directly.

## Boundary

The RNA-seq adapter selects one provider according to the unchanged
`QUANT_METHOD` value and supplies content-tracked manifests and artifacts:

```nextflow
tuple val(meta), path(provider_manifests), path(provider_artifacts),
      path(sample_table), path(tx2gene), val(import_params)
```

Required global `meta` fields are `id`, `provider`, and `target_dir`. The
provider manifests and artifacts are inseparable. A provider adapter validates
each manifest, its sample identity, its semantic artifact role, and its SHA-256
before creating an import source. Import modules never search `QUANT_DIR` or
`STAR_QUANT_DIR` and never infer a filename from a physical directory layout.

The input sample table is ordered by `dataset, sample_id`, contains one row per
`import_id`, and maps every row to a validated import source. Compatibility
columns written to `quant_samples.tsv` retain the legacy order and values.

## TX2GENE provider

`TX2GENE_BUILD` has the independent input contract:

```nextflow
tuple val(meta), path(annotation), val(tx2gene_params)
```

Version 1.0 accepts GTF/GFF through `rtracklayer`. Its transformation is the
legacy transformation, in this order:

1. retain `type == "transcript"`;
2. select `transcript_id, gene_id`;
3. remove `transcript:` and transcript version suffixes;
4. normalize an erroneous `transcript:` gene prefix to `gene:`;
5. remove `gene:` and gene version suffixes;
6. retain first-occurrence order while removing duplicate or empty pairs.

The output is `tx2gene.tsv`. Its content is cached independently from imports.

## Provider implementations

### Salmon

`SALMON_IMPORT` is implemented by `TXIMPORT`. It receives one validated
`quant.sf` per sample and calls tximport with the exact legacy arguments:

```r
tximport(
  files,
  type = "salmon",
  tx2gene = tx2gene,
  countsFromAbundance = "no",
  ignoreTxVersion = TRUE,
  ignoreAfterBar = TRUE
)
```

It emits counts, abundance (TPM), effective length, and a
`SummarizedExperiment` containing those three assays.

### STAR gene counts

`STAR_IMPORT` receives the validated `gene_counts` role from the Alignment API.
It preserves the legacy STAR import behavior: column 2/3/4 selection,
`N_*` removal, gene-prefix/version normalization, outer sample join, integer
counts, and CPM calculation. STAR GeneCounts has no transcript effective-length
estimate; the length role is marked `available: false` and no values are
invented. A `SummarizedExperiment` is not emitted by this provider in v1.0.

Future providers bind their native artifacts to the same roles. Kallisto and
RSEM can reuse `TXIMPORT`; featureCounts can follow the direct gene-count
provider pattern; StringTie can add a provider adapter without changing RNA-seq
consumers.

## Outputs

Every provider exposes:

```nextflow
counts             // tuple(meta, gene count matrix)
abundance          // tuple(meta, TPM/CPM abundance matrix)
lengths            // tuple(meta, effective-length matrix), optional by provider
experiment         // tuple(meta, SummarizedExperiment RDS), optional by provider
metadata           // tuple(meta, quant_samples.tsv)
versions           // tuple(meta, versions.yml)
execution_metadata // tuple(meta, execution.json and sessionInfo.txt)
manifest           // tuple(meta, partial manifest.json)
status             // tuple(meta, status.json)
```

Existing consumers continue to receive `counts_matrix.tsv`, `tpm_matrix.tsv`
or `star_cpm_matrix.tsv`, `quant_samples.tsv`, and `tx2gene.tsv`. Salmon adds
`length_matrix.tsv` and `summarized_experiment.rds` without replacing any
legacy artifact.

## Manifest and provenance

The partial `import_manifest.json` records schema version, provider, sample
count, parameters, input-manifest checksums, and an availability/checksum entry
for every semantic output. STAR records `lengths.available` and
`experiment.available` as false.

Each import also records the command, input checksums, tx2gene checksum when
applicable, sample-table checksum, requested resources, elapsed time, pinned
container, package versions, and `sessionInfo()` for R processes.

Deep cache keys include every staged manifest and provider artifact. Changing a
GTF reruns `TX2GENE_BUILD` and Salmon import. Changing only `tx2gene.tsv`, an
import manifest, or an import parameter reruns only the selected import
provider. Changed FASTQs reach this API only through changed upstream artifacts.

## Scientific compatibility

Regression tests require exact IDs, row and sample order, selected STAR count
column, and legacy filenames. Numeric matrices use a tight tolerance only for
text serialization. Absolute paths, timestamps, elapsed time, R session text,
and RDS serialization metadata are compared semantically.
