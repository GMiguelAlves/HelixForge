# Real biological integration execution plan

```text
DATASET = GSE133183 / SRP211748 / PRJNA550207
SCIENTIFIC_TARGET = dc0218ce902302da476910595bb133c82fee927c
INTEGRATION_WORKFLOW_TARGET = d0d1e7499e5b42be8294da3d85e402fa90a1cfe2
HELIXFORGE_RELEASE = v1.0.0-rc.1

OPERATIONAL_STAGE_REORDERING = COMPLETE
10D_SKIPPED_TEMPORARILY = RESOLVED
SCIENTIFIC_EXECUTION = NOT_STARTED
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
`/scratch/Schisto-epigenetics/gustavo/`; only compact audit evidence is copied
to the named audit directory in home. Cleanup is restricted to verified paths
owned by this benchmark.

The RNA-seq production route is QC, Trim Galore, Salmon, tximport, DESeq2 and
reporting. STAR is excluded. The ChIP-seq route uses the frozen H3K27me3 broad
and H3K27ac narrow settings and the matched IgG libraries. Whenever possible,
the Integration API is entered from terminal manifests rather than upstream
work directories.

No biological result was inspected while preparing this execution plan. The
expectations and criteria remain those in
`datasets/real_integrative_biological_expectations.tsv` and
`protocol/interpretation_criteria.md`.
