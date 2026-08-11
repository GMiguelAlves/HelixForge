# Controlled real validation report

Date: 2026-08-11  
Branch: `contrib/final-validation`  
Overall decision: **BLOCKED for global legacy retirement**

This report records the first controlled real validation pass after the native
API consolidation. It distinguishes a missing test from a demonstrated defect.
No large dataset or new dependency chain was introduced for this pass. After
the local pass, the reduced fixtures were also executed on an institutional
Slurm cluster using pre-existing Conda environments.

## Environment

- Windows host with Ubuntu under WSL2.
- Nextflow 26.04.6, build 12646, executed from the existing local JAR.
- Java 21.0.11.
- Docker Engine 29.1.3.
- WSL filesystem: about 929 GB free; Windows volume: about 28 GB free at audit.
- No Apptainer/Singularity, Conda/Mamba, or Micromamba runtime was added.
- R 4.3.3 and Python 3 with pandas 2.1.4 were already available in WSL.

The controlled Slurm pass used Nextflow 26.04.6 on the head node strictly as
the scheduler driver. Every scientific command ran in Slurm allocations on
compute nodes. Work and results were isolated under a new validation directory
on shared storage; no pre-existing scratch data was removed. The existing
`rna-tools`, `chipseq`, and `r-analysis` environments were inspected and used
without modification.

The project declares Nextflow `>=24.10.0`; this pass used a newer runtime. The
cache result below must be repeated on native Linux storage and the production
Nextflow version before it is interpreted as a pipeline cache defect.

## Capacity and decision matrix

| Component | Real native evidence | Legacy comparison | Status | Blocker or qualification |
|---|---|---|---|---|
| Trim Galore | Yes, including Slurm | Yes | READY_TO_RETIRE | Minimal paired-end fixture only |
| FastQC | Yes, 0.12.1 | Contract/mock comparison only | CONDITIONAL | Real report generated; no real legacy pair in this pass |
| MultiQC | No real run | Mock comparison | BLOCKED | Fixed image did not finish downloading within the controlled limit |
| FASTQ merge | Native mock/regression evidence | Yes | CONDITIONAL | Not rerun with a fully real QC chain |
| STAR | Yes locally; cluster index blocked | Yes locally | CONDITIONAL | Cluster Conda STAR 2.7.11b aborts after index generation |
| Salmon | Yes, 1.10.3, including Slurm | Yes | READY_TO_RETIRE | Semantic outputs passed on compute nodes |
| Salmon Import | Yes, container and Slurm Conda runtime | Yes | CONDITIONAL | Workflow-level normalization/count policy still requires a release decision |
| STAR Import | Yes | Yes | CONDITIONAL | Native provider ran on host; current Python production image was unavailable |
| DESeq2 | Yes on Slurm Conda runtime | Yes | CONDITIONAL | Scientific regression passes; production image remains unbuilt |
| ChIP BAM processing | Yes, including Slurm | Expected metrics validated | CONDITIONAL | Reduced fixture passed; cache reuse remains unresolved |
| Bowtie2 index | Yes on Slurm, cluster 2.5.5 | Yes, same cluster runtime | CONDITIONAL | Direct compiled binary bypassed a broken Conda Perl wrapper |
| Bowtie2 alignment | Yes on Slurm, cluster 2.5.5 | Yes, same cluster runtime | CONDITIONAL | BAM records, flagstat and idxstats passed; pinned 2.5.4 image remains uncertified |
| MACS3 | Yes, 3.0.4, including Slurm | No full legacy pair | CONDITIONAL | Two replicates and matched control passed |
| FRiP | Yes on Slurm | Semantic invariants | CONDITIONAL | Two real BAM/peak pairs passed; no full legacy regression |
| Consensus | Yes, union on Slurm | Semantic invariants | CONDITIONAL | Two-replicate union passed; IDR is still not implemented |
| Differential binding | Yes on Slurm | Semantic invariants | CONDITIONAL | featureCounts, DESeq2, two contrasts and aggregate passed in the available runtime |
| Annotation | Yes on Slurm | Semantic invariants | CONDITIONAL | Coordinates, configured promoter window and aggregate passed |
| Tracks | Yes on Slurm | Semantic invariants | CONDITIONAL | Three individual and one aggregate BigWig passed |
| Report | Yes on Slurm | Contract and content checks | CONDITIONAL | HTML passed and correctly discloses IDR as incomplete |
| Integrative | Manifest contract only | Legacy implementation retained | CONDITIONAL | No new analytic implementation was in scope |

`READY_TO_RETIRE` applies to the named component, not to the complete RNA-seq
or ChIP-seq legacy pipeline.

## Real scientific results

### RNA-seq QC

Trim Galore produced identical decompressed FASTQ content and read counts for
the legacy command and native process:

| Mate | SHA-256 of decompressed output | Reads |
|---|---|---:|
| R1 | `98384f001538af22fc484c62836dd83ed21aec7a8c791100214b3ad73ac5a10e` | 2 |
| R2 | `7942f4a2e16a3090728cbfe0566275e55083858eb771915530c0c01c59298eac` | 2 |

FastQC 0.12.1 ran through the native process and emitted a non-empty HTML
report, process log, status, trace, and `versions.yml`. Peak RSS was 118.9 MB.
The full real FastQC -> Trim Galore -> FastQC -> merge -> MultiQC chain was not
certified because the MultiQC image was unavailable within the download limit.

The same Trim Galore fixture passed on Slurm using jobs 12088 and 12089. A
provenance defect was found: the multiline `trim_galore --version` banner was
parsed by taking the first non-empty line. The parser now selects the explicit
`version` line and records Trim Galore 0.6.10 and Cutadapt 5.1. Scientific
FASTQ content and report statistics were unchanged.

### STAR Alignment API

The legacy command and native STAR process were semantically equivalent for:

- `ReadsPerGene.out.tab`;
- flagstat and idxstats;
- sorted BAM records;
- MAPQ distribution;
- `Log.final.out`;
- presence of `Log.out` and `Log.progress.out`.

The real test found and fixed an orchestration bug: an unescaped Bash regex end
anchor in `STAR_ALIGN` shifted subsequent Nextflow interpolations. No STAR
algorithm or scientific parameter changed.

On the target Slurm cluster, the pre-existing Conda STAR 2.7.11b binary aborted
with `double free or corruption` after writing the suffix-array index. The same
failure occurred with its AVX2 and plain binaries and with the working directory
on shared scratch (jobs 12097-12099). No native alignment job was submitted.
This is an environment/runtime blocker, not evidence against the locally
validated Alignment API.

### Salmon Quantification API

The legacy command and native Salmon process passed semantic comparison for:

- `quant.sf` numeric values;
- `cmd_info.json` and `lib_format_counts.json`;
- the `aux_info` file set and `meta_info.json`;
- `ambig_info.tsv` and fragment-length distribution;
- Salmon log presence and mapping statistics.

The Slurm regression (jobs 12094-12096) repeated every semantic check and
passed. Both native processes recorded Salmon 1.10.3. The native index and
quantification ran sequentially with a one-task queue limit.

### Import API

Salmon Import passed with the current production-name image
`ghcr.io/gmiguelalves/helixforge-import:1.0.0`:

- counts: maximum delta 0;
- abundance: maximum delta 0;
- sample table and manifest: equivalent;
- `tx2gene`: equivalent;
- length matrix and `SummarizedExperiment`: present and validated.

STAR Import passed with identical counts and CPM values, sample metadata, and
provider manifest. The legacy side used the already installed host pandas
2.1.4; no package installation occurred.

The regression fixtures exposed missing LF policies for `.sf` and `.tab`.
Those extensions are now normalized so manifest checksums remain stable across
Windows and Linux checkouts.

The Salmon Import regression also passed on Slurm. Two source adapters,
`TX2GENE_BUILD`, sample-table construction, and `TXIMPORT` ran as five
sequential tasks. Counts and abundance had maximum delta 0, `tx2gene` had two
identical rows, and the emitted `SummarizedExperiment` contained the expected
counts, abundance, and length assays in the expected sample order.

### DESeq2

The original fixture was statistically degenerate and DESeq2 correctly refused
to fit the dispersion curve. The synthetic matrix was adjusted to include
realistic replicate variability while preserving three conditions, three
replicates per condition, and `~ batch + condition`.

The obsolete local image then failed while drawing the volcano plot because its
ggrepel/ggplot2 combination calls the unavailable `replace_null` function. That
image contains ggplot2 3.4.4 and is not the declared production environment.
It is not valid release evidence.

The production Dockerfile was changed to create one solver-consistent
Micromamba environment from `modules/local/deseq2_model/environment.yml` rather
than mutating `/usr/local` in a Biocontainers image. One controlled local build
was attempted and stopped after five minutes without producing an image. The
CI must build and run the regression before DE can be certified.

The pre-existing cluster `r-analysis` environment allowed the scientific code
to be tested independently of that image build. The legacy script and native
DE API produced semantically equivalent aggregate results for one model and
three contrasts (jobs 12107-12114). R reported 4.3.3, Bioconductor 3.18.1, and
DESeq2 1.42.1. This validates the model/contrast/aggregation architecture but
does not certify the still-unbuilt image or its exact declared package set.

### ChIP-seq BAM processing

The real paired-end fixture validated:

| Stage | Before | After | Removed |
|---|---:|---:|---:|
| Selection | 12 | 8 | 4 |
| Duplicate removal | 8 | 6 | 2 |
| Fragment blacklist | 6 | 4 | 2 reads / 1 template |

Both final BAMs passed `samtools quickcheck`; blacklist-disabled behavior was
also exercised. BED validation now accepts CRLF without changing coordinates.

### Bowtie2

The configured Docker image remains unsuitable because it contains Bowtie2 but
not samtools. On Slurm, the existing `chipseq` Conda environment supplied both.
Its Perl dispatch wrapper was broken because the absolute environment prefix
contains `@`; Perl interpreted the path while loading `Config_heavy.pl`.

One isolated compatibility directory under the validation root exposed the
unchanged compiled `bowtie2-align-s` and `bowtie2-build-s` binaries. The same
compatibility path was used by the reference command and the native API. The
index and alignment passed on compute nodes: BAM records were semantically
identical, and flagstat/idxstats were byte-identical. The runtime reports
Bowtie2 2.5.5, so this is strong orchestration evidence but not certification
of the pinned 2.5.4 production image.

The run also found a test-workflow integration defect: the STAR-only
`--outTmpDir` default was forwarded to Bowtie2. Provider-specific
`bowtie2_extra_args` now defaults independently. No scientific parameter was
changed.

### MACS3

MACS3 3.0.4 ran on two treatment replicates against one matched input. Each
replicate produced one valid narrowPeak plus summit and signal artifacts. The
manifests retained distinct biological replicate identifiers, fixed parameters,
checksums, metrics, caller version, and matched-control provenance.

The Python slim adapter image lacks `ps`, which Nextflow requires to collect
task metrics. For this isolated scientific test only, adapters ran on the WSL
host while MACS3 remained containerized. The production Docker profile needs a
small adapter image containing `procps` or an equivalent supported solution.

The same two-replicate fixture then passed on Slurm with MACS3 3.0.4. Five
native tasks validated context, two independent peak calls and their aggregate
outputs. Peak files were non-empty, used the ten-column narrowPeak format, and
retained matched-control identity.

### ChIP-seq downstream APIs

The Slurm pass connected real reduced artifacts rather than independent stubs:

- BAM processing ran eight native tasks. Selection reduced 12 reads to 8,
  duplicate removal detected 2, fragment blacklist filtering removed 2 reads,
  and final counts were 4 with blacklist and 8 without it.
- FRiP and peak statistics ran for both MACS3 replicates. Each FRiP was in
  `(0, 1]`, and the two-record aggregate passed.
- Consensus union consumed those same peak and FRiP manifests. One group with
  two biological replicates emitted a non-empty consolidated BED. A staging
  collision between homonymous `manifest.json` files was fixed with unique
  staging directories.
- Differential binding used 30 reduced peaks and four biological samples.
  featureCounts, the DESeq2 model, both reciprocal contrasts and the aggregate
  passed. The original two-peak fixture was correctly rejected by DESeq2 as
  statistically degenerate; the provider algorithm was not weakened. A real
  `args.models`/`args.model` typo in the aggregate was fixed.
- Peak annotation completed context, provider, statistics and aggregate. With
  the configured 2 kb/500 bp promoter window on the 100 bp fixture, all three
  peaks correctly associated with `gene1` as promoters.
- Track generation completed four contexts, four providers, four statistics
  tasks and one aggregate. Three individual and one aggregate BigWig were
  non-empty and opened with `pyBigWig` with exact `chrTest:2000` metadata.
- Report context, aggregation and HTML generation passed. The self-contained
  report contains Differential Binding, Annotation and Tracks sections. Its
  manifest deliberately reports `incomplete` because IDR is declared
  `not_implemented`; this is expected fail-honest behavior.

The annotation/track/report pass exposed missing executable bits on packaged
resource scripts. Directly invoked resource executables now carry Git mode
`100755`; stages that pipe validators through `tee` also use `pipefail`, so
permission or provider errors cannot be masked.

## Cache and invalidation

`-resume` did not reuse STAR, Salmon, BAM, or MACS3 tasks in this environment.
The focused STAR diagnostic showed:

- the resumed run reused the same Nextflow session UUID;
- `cache 'deep'` was active;
- the complete dumped input fingerprint was identical;
- the prior work directory and outputs existed;
- Nextflow nevertheless submitted a new task.

This is consistent with a cache-store/filesystem compatibility problem involving
Nextflow 26.04.6 and WSL/NTFS. Cache and invalidation are therefore
**CONDITIONAL**, not silently accepted.

The production Slurm pass reproduced the miss for both stub and real Trim
Galore tasks. Session UUID, input checksums, generated command scripts, and
work directories were stable, but task hashes changed and new jobs were
submitted. Moving `NXF_CACHE_DIR` from NFS to head-node local storage did not
restore reuse. The compatibility guard then skipped already materialized
FASTQs, but this is not a Nextflow cache hit. A focused two-run
`-dump-hashes` analysis is required; no additional jobs were spent on it in
this pass.

## Execution environments

- Docker: real execution validated for Trim Galore, FastQC, STAR, Salmon,
  current Salmon Import, Bowtie2 indexing, and MACS3.
- Slurm: real submission validated. Preflight job 12083 ran on a compute node;
  RNA-seq plus Bowtie2, BAM processing, MACS3, FRiP, consensus, Differential
  Binding, annotation, tracks, and report tasks completed under the Nextflow
  Slurm executor. No scientific command ran directly on the head node and no
  nested submission was found in native modules.
- Apptainer/Singularity: not tested because no runtime is installed.
- Local WSL Conda profile: not tested because no runtime is installed there.
- Conda on Slurm: existing environments were used without installation.
  Results are conditional where their package versions differ from declared
  module environments.
- MultiQC: fixed image not available locally after the bounded pull attempt.

## Lint and static validation

Nextflow 26.04.6 linted 127 files without errors. One existing warning remains:
`LEGACY_STEP` accesses `projectDir` inside a process. This warning belongs to
the compatibility wrapper and does not affect native scientific processes.

## Preliminary benchmark

These values measure tiny fixtures and mostly reflect container and Nextflow
startup. They must not be used as performance claims.

| Component | Legacy ms | Native ms |
|---|---:|---:|
| Trim Galore | 4,063 | 16,035 |
| STAR | 4,978 | 31,249 |
| Salmon | 4,810 | 20,572 |
| Salmon Import | 24,414 | 126,983 |
| STAR Import | 2,448 | 17,356 |

Slurm task elapsed times are scheduler measurements rounded to seconds:

| Component | Legacy ms | Native task ms |
|---|---:|---:|
| Trim Galore | 10,013 | 25,904 end-to-end driver |
| Salmon | 11,000 | 1,000 summed tasks |
| Salmon Import | 15,000 | 20,000 summed tasks |
| DESeq2 | 17,000 | 48,000 summed tasks |
| Bowtie2 | 1,000 | 2,000 summed tasks |

Additional ChIP-seq native task sums on Slurm were: BAM processing 1,000 ms,
MACS3 4,000 ms, Peak QC 2,000 ms, consensus union 1,000 ms, Differential
Binding 32,000 ms, annotation 1,000 ms, tracks 14,000 ms, and report 1,000 ms.

The cluster allocates a minimum of two CPUs even when one CPU is requested, so
these fixtures are correctness evidence rather than efficiency claims.

## Provenance assessment

The real runs emitted versions, command/execution metadata, manifests and
checksums at the tested API boundaries. The Import checksum validation detected
both line-ending changes before analysis, demonstrating fail-closed behavior.
Container digest recording is not yet uniform: tags remain in several execution
documents and the downloaded OCI digest is not propagated into every manifest.

## Retirement decision

The complete legacy pipelines must remain available. Component retirement can
start only for Trim Galore and Salmon after review of this report.
Import is close but needs an explicit decision on workflow-level identifier and
`countsFromAbundance` policy. Global retirement is blocked by:

1. the unbuilt DESeq2 production image, despite a passing conditional Slurm regression;
2. the Bowtie2 production image missing samtools, despite the passing conditional Slurm regression;
3. the missing real MultiQC run;
4. IDR remaining explicitly not implemented;
5. unresolved cache reuse on the target filesystem;
6. STAR 2.7.11b crashing during index generation in the available cluster runtime;
7. no production-scale, top-level ChIP-seq regression against a reviewed biological dataset.

The detailed decisions and deviations are tracked in
`docs/scientific-deviation-log.md`.

## Next controlled pass

1. Let CI build the declarative DESeq2 image, then repeat the passing model/contrast regression.
2. Publish one declarative Bowtie2 2.5.4 + samtools 1.20 image and rerun alignment.
3. Make the metadata adapter image Nextflow-compatible by adding `procps`.
4. Obtain the pinned MultiQC image and run the complete native QC entrypoint.
5. Implement and validate IDR, or explicitly exclude it from the first release.
6. Repeat Differential Binding with the declarative DESeq2 image after item 1.
7. Run a bounded `-dump-hashes` cache diagnostic on Slurm before any large dataset.
8. Validate STAR with the pinned production image/runtime rather than the crashing cluster package.
9. Run the top-level ChIP-seq workflow on one reviewed reduced biological dataset before reconsidering legacy removal.
