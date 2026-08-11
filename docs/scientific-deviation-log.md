# Scientific deviation log

This log records discovered differences, their scientific relevance, and the
decision required before retiring a legacy component. No entry is waived merely
because a native process completes.

| ID | Component | Observation | Scientific impact | State | Required action |
|---|---|---|---|---|---|
| SD-001 | Trim Galore fixture | FASTQ qualities were two bases longer than their sequences. | Test could not exercise trimming. No production algorithm impact. | RESOLVED | Fixture corrected; real regression passes. |
| SD-002 | STAR | Unescaped `$` in a Bash regex shifted Nextflow template substitutions. | Index, reads, threads and output arguments were rendered incorrectly. | RESOLVED | End anchor escaped; legacy/native semantic regression passes. |
| SD-003 | BAM blacklist | Valid CRLF BED was rejected as non-numeric. | Cross-platform blacklist inputs could fail before filtering. | RESOLVED | Strip terminal CR before strict BED/contig validation. |
| SD-004 | Cache | Identical inputs and scripts were submitted again under `-resume` on WSL and Slurm; local head-node cache storage did not fix the Slurm miss. | Reproducibility is intact, but compute reuse and invalidation claims are unproven. | OPEN-BLOCKED | Run two bounded Slurm executions with `-dump-hashes` and compare hash entries before larger tests. |
| SD-005 | Import checksums | `.sf` and `.tab` were converted to CRLF on Windows while manifests stored LF hashes. | Import correctly failed closed, but fixtures were not portable. | RESOLVED | Added LF attributes and normalized only affected fixtures. |
| SD-006 | Import regression policy | Regression configured prefix preservation while legacy strips transcript/gene prefixes and versions. | Gene/transcript identifiers differed despite equal numeric values. | RESOLVED-TEST | Regression now selects the API's `legacy` normalization policy. |
| SD-007 | RNA workflow Import policy | Production context uses `ignoreTxVersion=false`, `ignoreAfterBar=false`, prefix preservation, STAR `preserve`, and requires an explicit non-null `countsFromAbundance`; legacy used `no` and normalized IDs. | May intentionally improve semantics, but outputs and downstream identifiers can differ from legacy. | OPEN-DECISION | Document and approve provider-specific release defaults; add both import-only `no` and DE-compatible scaled-count regression scenarios. |
| SD-008 | DESeq2 container | Previous image mutates an existing Biocontainers `/usr/local`; replacement local build timed out. | No certified DE execution environment exists. | BLOCKED | Build the single declarative environment in CI and publish its digest. |
| SD-009 | DESeq2 obsolete image | ggplot2 3.4.4/ggrepel failed with missing `replace_null` after the model fit. | Analysis cannot complete and report artifacts are absent. | BLOCKED | Do not patch around obsolete image; validate declared ggplot2 3.5.1 environment. |
| SD-010 | DE fixture | Initial synthetic counts caused the known all-dispersions-near-minimum failure. | Test measured a degenerate dataset, not provider behavior. | RESOLVED | Added replicate variability and updated manifest checksum. |
| SD-011 | Bowtie2 container | Configured Bowtie2 image lacks samtools used by `BOWTIE2_ALIGN`. | No BAM can be produced; ChIP alignment is blocked. | BLOCKED | Publish declarative Bowtie2 2.5.4 + samtools 1.20 image and record digest. |
| SD-012 | Metadata adapters | Python slim image lacks `ps`, required by Nextflow task metrics. | Docker profile fails before adapter logic. | BLOCKED | Build a small Python adapter image with procps, or use a documented supported base image. |
| SD-013 | MultiQC | Pinned image did not complete download within the bounded attempt. | Full real QC orchestration remains unverified. | BLOCKED-ENVIRONMENT | Retry in CI/registry-capable environment; do not install a host dependency chain. |
| SD-014 | MACS3 | Real two-replicate calling passes, but adapters ran on host and cache did not reuse. | Peak calling itself is supported; complete Docker/cache certification is not. | OPEN-CONDITIONAL | Resolve SD-004 and SD-012, then rerun unchanged fixture. |
| SD-015 | ChIP downstream | FRiP, consensus, differential binding, annotation and tracks have only stub/contract evidence in this pass. | Global ChIP legacy retirement is unsupported. | BLOCKED | Validate sequentially from the real MACS3 manifests; do not infer success from stubs. |
| SD-016 | Trim Galore provenance | Multiline version output was parsed as `failed.` instead of 0.6.10. | Scientific outputs were unaffected, but recorded provenance was false. | RESOLVED | Parse the explicit `version` line; real Slurm regression records 0.6.10. |
| SD-017 | STAR cluster runtime | Conda STAR 2.7.11b aborts with heap corruption after writing a tiny index using both AVX2 and plain binaries. | Target-cluster alignment cannot be certified with this runtime. | BLOCKED-ENVIRONMENT | Test the pinned production image or an administrator-supported STAR build; do not install an ad hoc replacement. |
| SD-018 | DESeq2 runtime | Slurm regression passes, but the existing environment reports DESeq2 1.42.1 and newer plotting/helper packages than the declared image. | Scientific architecture is validated; exact production runtime remains uncertified. | OPEN-CONDITIONAL | Build the declarative image and repeat the unchanged golden regression. |
| SD-019 | Slurm allocation | The cluster allocated two CPUs for jobs requesting one. | No scientific impact; tiny benchmark efficiency is distorted. | DOCUMENTED | Keep conservative queue limits and report allocated resources from `sacct`. |

## Acceptance rule

An open scientific difference requires one of: correction, explicit documented
release policy, or a justified tolerance with evidence. Environment blockers may
be conditional, but they cannot be promoted to scientific equivalence.
