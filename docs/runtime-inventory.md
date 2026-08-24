# Runtime and container inventory

This inventory groups the module-declared runtimes used by the v1 release
candidate. `nextflow.config` and `nextflow_schema.json` are the executable
sources of truth; every process records its observed tool/version metadata.

## Production scientific runtimes

| Purpose / processes | Image | Reproducibility state |
|---|---|---|
| FastQC | `quay.io/biocontainers/fastqc:0.12.1--hdfd78af_0` | exact Bioconda build tag |
| Trim Galore | `quay.io/biocontainers/trim-galore:0.6.10--hdfd78af_0` | exact Bioconda build tag |
| MultiQC | `quay.io/biocontainers/multiqc@sha256:fb7d...de9` | digest pinned |
| Salmon index/quant | `quay.io/biocontainers/salmon@sha256:f83e...f08e` | digest pinned |
| RNA Import / tximport / tx2gene | `ghcr.io/gmiguelalves/helixforge-import:1.0.0@sha256:e8bc...05f7` | digest pinned, amd64 |
| DE adapters / STAR import | `ghcr.io/gmiguelalves/helixforge-import-python:1.0.0@sha256:f09b...e456` | digest pinned, amd64 |
| DESeq2 | `ghcr.io/gmiguelalves/helixforge-deseq2:1.0.1@sha256:0356...61eb` | digest pinned, amd64; SBOM/provenance published |
| RNA gene report | `ghcr.io/gmiguelalves/helixforge-rnaseq-report:1.0.0@sha256:ec88...f863` | digest pinned |
| Bowtie2 and BAM processing | `ghcr.io/gmiguelalves/helixforge-chipseq-alignment:1.0.0@sha256:9c4e...928e` | digest pinned |
| MACS3 | `quay.io/biocontainers/macs3:3.0.4--py312h71493bf_0@sha256:1559...51cb` | digest pinned |
| FRiP / interval consensus | `ghcr.io/gmiguelalves/helixforge-chipseq-intervals:1.0.0@sha256:9b22...e479` | digest pinned |
| IDR | `quay.io/biocontainers/idr:2.0.4.2--py39h031d066_12@sha256:d6fb...61eb` | digest pinned |
| featureCounts peak matrix | `ghcr.io/gmiguelalves/helixforge-chipseq-counts:1.0.0@sha256:0820...fbf7` | digest pinned |
| deepTools tracks | `ghcr.io/gmiguelalves/helixforge-chipseq-tracks:1.0.0@sha256:eb8a...b843` | digest pinned |
| ChIP report | `python:3.11.9-slim-bookworm@sha256:8fb0...c317` | digest pinned; report logic is repository staged |
| Integrative engine / manifests / annotation | `python:3.12.10-slim@sha256:fd95...88db` | digest pinned; algorithms are repository staged |

The abbreviated digests above are for readability only. Never copy them into a
configuration; use the full values in `nextflow.config`.

## Supporting runtimes

Small context/metadata/FASTQ-concatenation processes use exact version tags for
`debian:12.5-slim` or `python:3.12.4-slim-bookworm`. These processes do not
embed scientific algorithms, but digest-pinning them is a post-RC supply-chain
hardening item. STAR uses its declared Seqera image and remains experimental.

## Apptainer and Conda

Apptainer/Singularity references are declared alongside their OCI providers,
and module Conda environments are versioned in module directories. They remain
**experimental** because the validation cluster did not provide an
administrator-supported Apptainer runtime with GHCR/Quay and required mount
access, and a complete clean Conda smoke was not run.

## Container build workflows

Repository GitHub Actions build/certify the custom DESeq2, report, MultiQC and
ChIP images. Build jobs may test a version tag immediately after publishing it;
the released runtime configuration uses the reviewed digest. Full-SHA pinning
of third-party GitHub Actions is tracked separately as post-RC supply-chain
hardening.
