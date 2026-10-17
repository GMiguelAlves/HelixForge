# RNA-seq APIs

This overview connects the RNA-seq input, QC, analytical and reporting
boundaries. It is the counterpart to [ChIP-seq APIs](chipseq-api.md), not a
second specification of the individual contracts. API/model versions belong
to those contracts and are independent of the HelixForge software release.

## Boundary map

| Boundary | Declared inputs | Products and consumers | Contract reference |
|---|---|---|---|
| Metadata | Local samplesheet/FASTQs and selected configuration | Normalized metadata, QC plans and reference requests | [Foundation module contract](module_contracts.md), [single-end metadata](../guides/rnaseq-single-end.md#metadata-contract) |
| Reference Bundle | Transcriptome and GTF/GFF; genome when required by the selected provider | Validated reference identities and checksums, passed to index/Import consumers | [Module contract](module_contracts.md), [terminal reference identity](terminal_manifests.md#rna-seq) |
| QC | Per-run reads, layout and explicit trimming configuration | Read QC, trimmed technical runs, ordered sample-level FASTQs and MultiQC | [Native QC](../implementation/native-rnaseq-qc.md), [module contract](module_contracts.md) |
| Alignment | Reads, genome/annotation, index and alignment parameters | STAR BAM/BAI, gene counts, logs and provenance | [Shared Alignment API](alignment_api.md) |
| Quantification | Reads, transcriptome, index and quantification parameters | Salmon quantification and provider manifest | [Quantification API](quantification_api.md) |
| Import | Provider manifests/artifacts, annotation/tx2gene, metadata and policy | Gene matrices, sample table, applicable length/experiment products and manifest | [Import API](import_api.md), [scientific policy](../science/rnaseq_import_policy.md) |
| Differential Expression | Import manifest/counts, sample metadata and DE specification | Fitted model, independent contrasts, normalized counts and aggregate results | [Differential Expression API](differential_expression_api.md) |
| Report | Import/DE artifacts, annotation and candidate-gene groups | Exploratory tables, figures, HTML and report manifest | [RNA-seq Report API](rnaseq_report_api.md) |
| Terminal assay boundary | Declared reference, metadata, contrasts and producer artifacts | `rnaseq_run_manifest.json` and portable integration products | [Terminal manifests](terminal_manifests.md), [Integration API](integration_api.md) |

## Metadata and experimental units

The samplesheet identifies `dataset`, `sample_id` and `run_accession`.
Native metadata validation resolves the configured local reads and rejects
missing files, duplicated run identities and inconsistent sample layouts.
Design variables such as condition and batch must also satisfy the downstream
DE specification when inference is requested.

Technical sequencing runs are not independent biological replicates. QC
groups and orders compatible runs for sample-level quantification; Import
preserves the declared sample/library identity and checks metadata consistency.
If explicit technical-unit fields are used, provide them consistently rather
than allowing a missing value to invent a new biological observation.

Paired-end records require R1/R2. Single-end Salmon records require R1, an
explicit layout and a justified fragment-length mean/SD; datasets cannot mix
layouts. See the [single-end contract](../guides/rnaseq-single-end.md) for exact
field rules and support boundaries.

## References and index reuse

The reference boundary validates the supplied transcriptome and annotation,
and the genome where the selected path requires it. It records reference
identity and checksums without acquiring or modifying the input files. Input
acquisition is outside the scientific DAG; `pipeline_config.sh` is translated
by a compatibility context, not executed as a legacy scientific coordinator.

`TRANSCRIPTOME_INDEX` selects Salmon index construction or explicit prebuilt
validation. Supplying both `salmon_prebuilt_index` and its manifest allows
independent reuse without the originating work directory or task cache.
An existing directory alone is not evidence of a compatible index, and an
invalid supplied bundle does not silently trigger reconstruction. See
[Salmon index reuse](quantification_api.md#reusing-a-prebuilt-salmon-index).

## QC and provider selection

The native QC composition uses shared `FASTQC`, layout-aware Trim Galore,
FASTQ merge and `MULTIQC` tool modules. Raw/post-trim/post-merge checks have
distinct inputs. Ordered gzip-member concatenation preserves technical-run
reads without treating those runs as extra biological samples.

Salmon is the production quantification provider. STAR is an explicitly
selected experimental Alignment provider, not a prerequisite for Salmon.
`rnaseq_analysis_mode=both` fans out the same selected reads independently;
Import consumes the provider selected by the configured analysis contract.
Single-end STAR is not supported. The [Alignment API](alignment_api.md) is
shared with ChIP-seq Bowtie2, while quantification remains a separate boundary.

## Scientific downstream boundary

The [Import policy](../science/rnaseq_import_policy.md) determines the accepted
`countsFromAbundance`, identifier and library-protocol combinations. Do not
copy historical tximport arguments as implicit production defaults.
`TX2GENE_BUILD` and matrix import are separate tasks; downstream DE consumes
their provider-neutral outputs, never a guessed Salmon/STAR filename.

DESeq2 model fitting, each Wald contrast and aggregation are independent cache
boundaries. Batch belongs in an estimable formula such as
`~ batch + condition`, not in an automatically corrected inferential matrix.
Candidate-gene reports are exploratory presentation products and cannot modify
the inference. Batch assessment and pathway enrichment remain
[roadmap](../roadmap.md) items, not implemented providers advertised here.

## Modes, re-entry and provenance

The cumulative stop points are `qc`, `alignment`, `quantification` (`quant`),
`import`, `de` (`differential_expression`), `report` and `full`. Gene Report is
optional in `full` and explicitly requested by `report`.
The separate `report_reentry` route consumes retained Import/DE artifacts and
runs only the Report API; it does not need FASTQs or the old cache and does
not rewrite the accepted terminal assay manifest. Exact parameters are in the
[workflow guide](../guides/workflows.md#rna-seq) and
[Report re-entry contract](rnaseq_report_api.md#terminal-only-re-entry).

Complete assay runs project declared artifacts into the
[terminal manifest](terminal_manifests.md#rna-seq), not an inventory discovered
by scanning results directories. Keep that manifest with its sibling
`integration_artifacts/` for portable Integrative consumption. Stage-stop and
report-only outputs must not be mistaken for a complete assay bundle.

Task cache/work state is operational, not a scientific interchange format.
See [cache behavior](../guides/nextflow.md#cache-and-invalidation),
[RNA-seq architecture](../architecture/rnaseq-architecture.md), and
[current limitations](../guides/limitations.md) for composition and support
scope. Reduced fixture validation does not establish biological validity for
every study or library preparation.
