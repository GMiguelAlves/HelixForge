# HelixForge v1.0.0

HelixForge v1.0.0 is the first stable release of the organism-agnostic
Nextflow DSL2 framework. It promotes the validated `v1.0.0-rc.1` lineage
without changing scientific algorithms, contracts, defaults, or benchmark
thresholds. The overall benchmark classification is
**`PASS_WITH_LIMITATIONS`**.

## Highlights

- Native RNA-seq, ChIP-seq, and cross-assay Integrative workflows.
- Versioned terminal manifests as the stable interoperability boundary.
- Portable manifest re-entry without dependence on the originating Nextflow
  work directory or task cache.
- Explicit provenance, checksums, software versions, commands, and execution
  metadata.
- Local and Slurm execution, pinned OCI providers, and self-contained HTML
  reports.

## RNA-seq

The supported production path is QC, Salmon, tximport, DESeq2, and gene
reporting. The Import API applies the frozen `production_v1` policy and
preserves explicit sample, reference, and contrast contracts. STAR remains an
experimental Alignment API provider and is never selected implicitly.

The frozen RNA-seq baseline combines a Polyester synthetic truth experiment
with the complete eight-library GSE52778 biological dataset. Its classification
is `PASS_WITH_LIMITATIONS`.

## ChIP-seq

The supported path includes QC, Bowtie2, BAM processing, MACS3, FRiP, union
consensus or optional IDR, differential binding, annotation, tracks, and the
final report. The frozen baseline covers synthetic narrow, synthetic broad,
real K562 CTCF, and real K562 H3K27me3 arms. Its classification is
`PASS_WITH_LIMITATIONS`.

## Integrative workflow

RNA-seq and ChIP-seq terminal manifests are normalized through evidence
providers, reference compatibility checks, harmonization, molecular linkage,
regulatory interpretation, Candidate Score v1, statistics, functional
interpretation, visualization, and reporting. The frozen benchmark covers
synthetic truth, relocated-manifest re-entry, negative contracts, and complete
real biological integration. Its classification is `PASS_WITH_LIMITATIONS`.

## Manifest API and re-entry

Terminal manifests identify artifacts by semantic role and preserve reference,
contrast, checksum, and provenance identities. The re-entry benchmark showed
that an Integrative analysis can be reconstructed from declared manifests and
artifacts without the cache or work directory that produced them.

## Benchmark validation

| Area | Frozen evidence | Classification | Tag |
|---|---|---|---|
| RNA-seq | Polyester synthetic truth + GSE52778 | `PASS_WITH_LIMITATIONS` | `rnaseq-benchmark-v1.0.0-rc.1` |
| ChIP-seq | synthetic narrow/broad + real CTCF/H3K27me3 | `PASS_WITH_LIMITATIONS` | `chipseq-benchmark-v1.0.0-rc.1` |
| Integrative | synthetic truth + re-entry + negative contracts + real integration | `PASS_WITH_LIMITATIONS` | `integrative-benchmark-v1.0.0-rc.1` |

These benchmarks validate the declared scenarios; they do not claim universal
performance across organisms, protocols, executors, or sequencing designs.

## Known limitations

- Salmon 1.10.3 can produce small numerical differences under some threading
  conditions. The frozen benchmarks retained feature identity, direction,
  rankings, DEG sets, and scientific conclusions while keeping strict numeric
  failures visible.
- Synthetic broad ChIP-seq domains showed length-dependent fragmentation.
- Real-narrow RN3 was not evaluable under the frozen null-model requirements.
- The historical real-broad dataset showed strong replicate asymmetry.
- Integrative IB4 remained outside its frozen expected range because no
  H3K27me3 region passed the preregistered differential threshold.
- Integrative IB5 was not evaluable because the current statistics contract
  does not emit directional-concordance Fisher tests.
- Complete-workflow `-resume` persistence was unreliable in the tested shared
  HPC environment even though Nextflow 25.10.7 passed the minimal cache probe.
- Apptainer/Singularity and Conda profiles remain experimental. The tested
  cluster did not provide an administrator-supported Apptainer runtime with
  registry and mount access.
- STAR and single-end RNA-seq are not certified production paths in v1.0.0.

## Compatibility

The scientifically validated runtime is Nextflow 25.10.7 with Java 21 on Linux
x86_64. Docker is the supported local container profile. Slurm execution is
supported with site-specific configuration and shared storage visible to every
compute node. Newer Nextflow or Java versions, native Windows, Apptainer,
Singularity, and complete Conda execution are outside the certified matrix.

Scientific tool versions and immutable container identities are listed in the
[runtime inventory](runtime-inventory.md).

## Reproducibility

The release retains the RC tag, all three annotated benchmark tags, compact
machine-readable benchmark evidence, historical legacy tags, terminal-manifest
schemas, pinned providers, and audit-oriented documentation. Benchmark results
were not recomputed or modified for this stable release.

