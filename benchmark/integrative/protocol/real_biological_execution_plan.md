# Real biological integration execution plan

```text
DATASET = GSE133183 / SRP211748 / PRJNA550207
SCIENTIFIC_TARGET = dc0218ce902302da476910595bb133c82fee927c
INTEGRATION_WORKFLOW_TARGET = d0d1e7499e5b42be8294da3d85e402fa90a1cfe2
HELIXFORGE_RELEASE = v1.0.0-rc.1

OPERATIONAL_STAGE_REORDERING = COMPLETE
10D_SKIPPED_TEMPORARILY = RESOLVED
SCIENTIFIC_EXECUTION = PASS_WITH_LIMITATIONS
```

The real arm uses the 16 preregistered GEO samples in
`datasets/real_sample_selection.tsv`: RNA-seq, H3K27me3, H3K27ac and IgG from
K562 cells exposed to DMSO or 5 uM GSK343, with two biological replicates per
assay and condition. This file materializes the already frozen design; it does
not add or replace samples.

Before any FASTQ transfer, a Slurm metadata preflight must cross-check ENA,
NCBI RunInfo and GEO, freeze run-level URLs, sizes and checksums, and replace
the provisional storage estimate with an accession-level plan. Unavailable or
mismapped accessions stop execution as `DATASET_AVAILABILITY_CONFLICT`.

Heavy acquisition, upstream RNA-seq and ChIP-seq production, integration and
evaluation run only through Slurm. The run uses at most five concurrent jobs by
default and may use up to ten only when an execution node is confirmed free.
Large inputs and work directories remain under the dedicated benchmark path in
`/scratch/HELIXFORGE_WORKSPACE/`; only compact audit evidence is copied
to the named audit directory in home. Cleanup is restricted to verified paths
owned by this benchmark.

The RNA-seq production route is QC, Trim Galore, Salmon, tximport, DESeq2 and
reporting. STAR is excluded. The ChIP-seq route uses the frozen H3K27me3 broad
and H3K27ac narrow settings and the matched IgG libraries. Whenever possible,
the Integration API is entered from terminal manifests rather than upstream
work directories.

The two mark-specific ChIP-seq terminal manifests are composed before
integration into one portable multi-mark terminal manifest. This benchmark
adapter deduplicates the four identical shared IgG records, normalizes only the
dataset label, and carries forward exactly the three integration artifacts per
mark (`consensus_peaks`, `differential_binding` and
`peak_gene_annotation`). Every source and copied artifact is SHA-256 verified;
scientific table contents, contrasts and mark identities are not transformed.
This clarification was fixed before integrated biological results were
generated.

The first technical launch exposed a basename collision before biological
evidence was produced: both mark-specific producers legitimately used names
such as `consolidated_peaks.bed`. The current provider stages declared files by
basename, so the adapter assigns a mark-qualified portable filename while
preserving the original relative location in metadata. File contents and
SHA-256 checksums remain unchanged. This is a pre-result transport correction,
not a scientific transformation.

The following contract-gated launch exposed a second pre-result mismatch. The
terminal ChIP manifests carried condition-specific consensus peak IDs, an
aggregate annotation spanning both conditions, and Differential Binding region
IDs from the comparison universe. Those three namespaces are individually
valid but cannot form a verifiable gene-level differential evidence graph.
The benchmark therefore projects the Differential Binding table's own
`peak_id`, `chrom`, `start` and `end` columns to a one-to-one BED catalog and
annotates those exact regions with the frozen native provider. Row order,
region identity, Differential Binding values and statistical results remain
unchanged. The adapter records checksums, row counts, the annotation policy and
Slurm provenance. Relaxing the unknown-peak validation or silently dropping
unmatched rows is explicitly prohibited.

No biological result was inspected while preparing this execution plan. The
expectations and criteria remain those in
`datasets/real_integrative_biological_expectations.tsv` and
`protocol/interpretation_criteria.md`.

## Final outcome

The fresh terminal-manifest integration completed all 12 Slurm processes and
produced the report and final manifest. IB1–IB3 and IB6–IB8 passed. IB4 did not
meet its frozen expected range because the independently confirmed H3K27me3
Differential Binding result contains zero significant regions. IB5 is
`NOT_EVALUABLE` because no directional-concordance Fisher tests are emitted by
the current statistics contract. The result is therefore frozen as
`PASS_WITH_LIMITATIONS`; thresholds and observed outputs were not modified.

See `../reports/real_biological_integration.md` and
`../results/real/evaluation/` for the reviewed summary and checksummed evidence.
