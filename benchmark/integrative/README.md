# HelixForge integrative benchmark

This directory preregisters the integration benchmark for HelixForge
`v1.0.0-rc.1`. It tests the boundary that joins already validated RNA-seq and
ChIP-seq evidence; it does not repeat Salmon, DESeq2, Bowtie2, MACS3, IDR or
broad-consensus validation.

## Frozen scientific subject

| Item | Frozen value |
|---|---|
| HelixForge version | `1.0.0-rc.1` |
| Scientific target / current `master` | `dc0218ce902302da476910595bb133c82fee927c` |
| Integration workflow implementation | `d0d1e7499e5b42be8294da3d85e402fa90a1cfe2` |
| Release-candidate tag target | `fc38ada8f592bb57a13467965a718ce0df7fb6ce` |
| RNA-seq baseline | `rnaseq-benchmark-v1.0.0-rc.1` → `9a4367c3839b4f7f929b14157fcde7011df837e6` |
| ChIP-seq baseline | `chipseq-benchmark-v1.0.0-rc.1` → `1679610f7649c0fcaf98a2e132c96bf76cbbe3b1` |

The baseline tags include their respective scientific and administrative
freezes. The integrative target is the later current `master`, which contains
both baseline merges and the deterministic artifact-binding implementation.
The older RC tag remains the release lineage anchor; it is not substituted for
the exact benchmark target commit.

## Preregistered arms

1. **Synthetic ground truth:** 1,000 genes with independently generated
   evidence states, regulatory classes, normalization cases and priority tiers.
2. **Manifest re-entry:** semantic equivalence between direct terminal-manifest
   inputs and a relocated manifest-backed re-entry.
3. **Real biological integration:** K562 DMSO versus 5 µM GSK343 RNA-seq,
   H3K27me3 and H3K27ac from GEO `GSE133183`.
4. **Negative contracts:** fast fixtures for incompatible references, invalid
   manifests, collisions and normalization behavior.
5. **Baseline freeze:** final classification and annotated tag only after all
   preceding arms are executed and reviewed.

## Documents

- [Complete protocol](protocol/benchmark_protocol.md)
- [Design freeze report](protocol/design_freeze_report.md)
- [Metrics](protocol/metrics.md)
- [Acceptance criteria](protocol/interpretation_criteria.md)
- [Cost estimate](protocol/cost_estimate.md)
- [Risks and limitations](protocol/risks_and_limitations.md)
- [Dataset registry](datasets/dataset_registry.tsv)
- [Synthetic truth](datasets/synthetic_truth.tsv)
- [Real dataset candidates](datasets/real_dataset_candidates.tsv)
- [Frozen biological expectations](datasets/real_integrative_biological_expectations.tsv)
- [Negative-contract cases](datasets/negative_contract_cases.tsv)
- [Scientific target provenance](provenance/scientific_target.json)

No scientific benchmark has been run from this directory. No FASTQ, BAM,
reference, Nextflow work directory or result was added during the design
freeze.

**Status: design and preregistered truth frozen; scientific execution not
started.**
