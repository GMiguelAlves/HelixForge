# Controlled real validation report

The later native RNA-seq input-foundation pass is recorded in
[RNA-seq native foundation validation](rnaseq-foundation-validation.md).

Date: 2026-08-13
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
without modification. The RNA driver used the Java 23 runtime already present
in `rna-tools`; Java 25 was used only for one minimal cache probe.

The project declares Nextflow `>=24.10.0`; this pass used a newer runtime. The
cache result below must be repeated on native Linux storage and the production
Nextflow version before it is interpreted as a pipeline cache defect.

The final top-level ChIP-seq pass used the certified temporary runtime
Nextflow 25.10.7. It reused the cluster's existing `chipseq`, `r-analysis`,
`rna-tools`, and `python-list` environments without installing or modifying
packages. At most five scientific jobs were queued concurrently.

## Capacity and decision matrix

| Component | Real native evidence | Legacy comparison | Status | Blocker or qualification |
|---|---|---|---|---|
| Trim Galore | Yes, including Slurm | Yes | READY_TO_RETIRE | Minimal paired-end fixture only |
| FastQC | Yes, 0.12.1 | Contract/mock comparison only | CONDITIONAL | Real report generated; no real legacy pair in this pass |
| MultiQC | Yes on Slurm 1.30 and Docker 1.17 | Contract comparison | CONDITIONAL | Immutable OCI image certified on two reduced FastQC records; no real legacy pair in this pass |
| FASTQ merge | Native mock/regression evidence | Yes | CONDITIONAL | Not rerun with a fully real QC chain |
| STAR | Yes locally; cluster index blocked | Yes locally | CONDITIONAL | Cluster Conda STAR 2.7.11b aborts after index generation |
| Salmon | Yes, 1.10.3, including Slurm | Yes | READY_TO_RETIRE | Semantic outputs passed on compute nodes |
| Salmon Import | Yes, container and Slurm Conda runtime | Yes | CONDITIONAL | Workflow-level normalization/count policy still requires a release decision |
| STAR Import | Yes | Yes | CONDITIONAL | Native provider ran on host; current Python production image was unavailable |
| DESeq2 | Yes on Slurm and CI image | Yes | CONDITIONAL | Image 1.0.1 passed regression/cache tests; Slurm used the existing 1.42.1 environment |
| ChIP BAM processing | Yes, including Slurm | Expected metrics validated | CONDITIONAL | Reduced fixture passed; cache reuse remains unresolved |
| Bowtie2 index | Yes on Slurm, cluster 2.5.5 | Yes, same cluster runtime | CONDITIONAL | Direct compiled binary bypassed a broken Conda Perl wrapper |
| Bowtie2 alignment | Yes on Slurm, cluster 2.5.5 | Yes, same cluster runtime | CONDITIONAL | BAM records, flagstat and idxstats passed; pinned 2.5.4 image remains uncertified |
| MACS3 | Yes, 3.0.4, including top-level Slurm | No full legacy pair | CONDITIONAL | Four replicates and matched control passed |
| FRiP | Yes on top-level Slurm | Semantic invariants | CONDITIONAL | Four real BAM/peak pairs passed; no full legacy regression |
| Consensus | Yes, union on top-level Slurm | Semantic invariants | CONDITIONAL | Two conditions with two replicates each passed; IDR is still not implemented |
| Differential binding | Yes on top-level Slurm | Semantic invariants | CONDITIONAL | featureCounts, DESeq2, one requested contrast and aggregate passed in the available runtime |
| Annotation | Yes on Slurm | Semantic invariants | CONDITIONAL | Coordinates, configured promoter window and aggregate passed |
| Tracks | Yes on Slurm | Semantic invariants | CONDITIONAL | Three individual and one aggregate BigWig passed |
| Report | Yes on Slurm | Contract and content checks | CONDITIONAL | HTML passed and correctly discloses IDR as incomplete |
| Integrative | Manifest contract only | Legacy implementation retained | CONDITIONAL | No new analytic implementation was in scope |
| Top-level RNA-seq | Yes on Slurm | Scientific invariants | READY_TO_RETIRE | QC -> Salmon -> Import -> DESeq2 -> Gene Report passed; runtime cache remains an external operational issue |

`READY_TO_RETIRE` now applies to the supported complete RNA-seq production path.
It does not apply to ChIP-seq or Integrative legacy pipelines.

## Real scientific results

### RNA-seq QC

Trim Galore produced identical decompressed FASTQ content and read counts for
the legacy command and native process:

| Mate | SHA-256 of decompressed output | Reads |
|---|---|---:|
| R1 | `98384f001538af22fc484c62836dd83ed21aec7a8c791100214b3ad73ac5a10e` | 2 |
| R2 | `7942f4a2e16a3090728cbfe0566275e55083858eb771915530c0c01c59298eac` | 2 |

FastQC 0.12.1 and MultiQC 1.30 ran through the complete native QC subworkflow
on Slurm. The top-level run covered raw and post-trim FastQC, four paired-end
Trim Galore tasks, merged FASTQs, merged-read FastQC, and a non-empty MultiQC
report. Re-execution exposed an idempotence defect when replacing an existing
MultiQC data directory; publication now uses Nextflow `publishDir`, including
inside Docker where arbitrary host paths are not automatically mounted.

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

The production Dockerfile creates one solver-consistent Micromamba environment
from `modules/local/deseq2_model/environment.yml` rather than mutating
`/usr/local` in a Biocontainers image. Image
`ghcr.io/gmiguelalves/helixforge-deseq2:1.0.1` adds `procps`, was built and
published by CI, and passed the native scientific regression and cache suite in
GitHub Actions run `31526144851`.

The pre-existing cluster `r-analysis` environment allowed the scientific code
to be tested independently of that image build. The legacy script and native
DE API produced semantically equivalent aggregate results for one model and
three contrasts (jobs 12107-12114). R reported 4.3.3, Bioconductor 3.18.1, and
DESeq2 1.42.1. This validates the model/contrast/aggregation architecture but
uses a different package patch level from the separately certified OCI image.

The top-level RNA-seq validation subsequently exercised one DESeq2 model and
one contrast after Salmon/tximport. It found and fixed missing optional
`Name`/`biotype` handling in sparse GFF3 annotations. The final contrast table
was produced for 30 genes without changing the Wald test, design, thresholds,
or count policy.

### Official top-level RNA-seq path

Case `rnaseq-production-03` completed the official production path on Slurm:

`FASTQ -> native QC -> Salmon -> Import/tximport -> DESeq2 -> results`

STAR was explicitly disabled. Four paired-end samples and 30 genes passed.
Per-sample count correlations ranged from 0.9999999999999998 to
1.0000000000000002, and total-count ratios ranged from 0.9999999999999997 to
1.0000000000000002. Salmon mapped more than 98% of processed fragments for
every sample, the Import API emitted all three matrices plus a
`SummarizedExperiment`, and DESeq2 emitted the requested contrast table.

The final release fixture, case `rnaseq-final-synthetic-20260813-02`, extended
that path through the native Gene Report. All 58 processes completed with zero
failures and peak concurrency of five. It retained the same four samples and
30 genes, used design `~ batch + condition`, preserved count correlations and
totals effectively equal to 1.0, and produced a complete report manifest,
HTML, 12 non-empty scientific PNGs and 24 report files. See
`docs/rnaseq-final-validation.md`.

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

### Official top-level ChIP-seq path

Case `chipseq-production-real-06` completed the supported production path on
the institutional Slurm cluster:

`FASTQ -> FastQC/MultiQC -> Bowtie2 -> BAM processing -> MACS3 -> FRiP/QC -> union consensus -> Differential Binding -> Annotation -> Tracks -> Report`

The execution used five paired-end records: one input and two biological
replicates for each of the control and treated conditions. It completed 100
scientific process executions across four supported top-level modes (71 + 4 +
22 + 3). All commands ran in Slurm allocations; the head node hosted only the
Nextflow scheduler driver.

Semantic validation passed for ten FastQC archives, one real MultiQC report,
five indexed BAMs, four non-empty MACS3 peak sets, four FRiP values from
0.8339 to 0.9146, two union consensus groups, one DESeq2 contrast with 14
reported regions, 29 annotated peaks, seven BigWigs including two aggregates,
and a 32,397-byte self-contained report. The ten source FASTQ checksums were
unchanged.

Summed task realtime from the Nextflow traces was 107.380 seconds for the
foundation-through-differential-binding stage, 1.073 seconds for annotation,
33.687 seconds for tracks, and 0.899 seconds for report generation. These are
small-fixture task totals, not a production throughput benchmark.

The pass found three validation-harness defects and one fixture limitation:
Python/R environment precedence, the published Differential Binding manifest
path, use of individual `consensus` manifests where the Report API requires
the aggregate `consensus_idr` manifest, and an initially degenerate four-region
DESeq2 fixture. Each was corrected without changing pipeline algorithms or
scientific parameters. IDR itself was not exercised; union remains the
validated consensus provider.

## Cache and invalidation

`-resume` did not reuse scientific tasks in this environment. Focused and
top-level diagnostics showed:

- the resumed run reused the same Nextflow session UUID;
- `cache 'deep'` was active;
- the complete dumped input fingerprint was identical;
- the prior work directory and outputs existed;
- Nextflow nevertheless submitted a new task.

Cache and invalidation are therefore **BLOCKED**, not silently accepted.

The initial production Slurm pass reproduced the miss for the complete RNA
workflow. A one-process probe then demonstrated that:

- the same session UUID and logical cache hash were reused;
- every hash entry reported by `-dump-hashes json` was identical;
- all declared outputs and `.exitcode` files remained present in the workdir;
- the task cache database contained run indexes but no persisted task records;
- both NFS (`/home`) and head-local ext4 (`/tmp`) cache stores behaved the same;
- Nextflow 26.04.4 and 26.04.6, Java 21, 23 and 25, and syntax parsers v1 and
  v2 reproduced the miss;
- the same probe resumed correctly with Nextflow 25.10.7 on both Java 21 and
  Java 23 (`cached: 1`, with the original work hash and no second Slurm task).

The controlled version/JVM matrix was:

| Nextflow | JVM | Identical `-resume` | Interpretation |
|---|---|---|---|
| 25.10.7 | Temurin 21.0.12 | PASS | Task recovered from cache |
| 25.10.7 | Conda OpenJDK 23.0.2 | PASS | Task recovered from cache |
| 26.04.6 | Temurin 21.0.12 | FAIL | Task submitted again |
| 26.04.6 | Conda OpenJDK 23.0.2 | FAIL | Task submitted again |
| 26.04.4/26.04.6 | Conda OpenJDK 25.0.2 | FAIL | Prior focused probes |

This proves that 26.04.x regressed even the one-task case in this environment
and excludes Java 23/25 as the sole cause. It did not yet prove that 25.10.7
would persist a larger workflow cache. The official
[Caching and resuming](https://docs.seqera.io/nextflow/cache-and-resume)
documentation states that completed tasks are automatically persisted and
that a resumed task requires both its task-cache entry and preserved workdir
outputs. The 25.10.7 probe demonstrated both conditions; 26.04.x preserved the
workdir but failed to persist the matching task entry.

The full RNA workflow was subsequently rerun with Nextflow 25.10.7, Java 23,
an explicit persistent `NXF_CACHE_DIR` on `/home`, and the existing workdir on
`/scratch`. The baseline completed through QC, Salmon, Import and DESeq2 and
passed the scientific validator. Its identical resume kept session UUID
`3170ba4a-cc0e-4f7c-bfa1-3fb1080ce718`, but began submitting scientific tasks
again. The dedicated LevelDB contained run indexes but no task records: its
log remained zero bytes and no SST task table was created. The repeated run
was stopped as soon as re-submissions were established, with no more than five
jobs active concurrently.

Therefore 25.10.7 is certified here for complete scientific execution and is
temporarily pinned to hold the runtime stable, but **top-level cache and
selective invalidation remain BLOCKED-RUNTIME**. The FASTQ, transcriptome,
contrast, QC-parameter and module-script scenarios were deliberately not run
after the unchanged prerequisite failed. The 26.04.x behavior is still a
regression relative to the one-task probe, while the full-DAG result indicates
an additional task-cache persistence interaction involving workflow scale,
configuration or the shared environment. No system or Conda environment was
modified. The retained probe and driver are ready for administrator or
upstream reproduction.

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
- MultiQC: real Slurm execution passed with the existing 1.30 runtime. The
  production 1.17 BioContainer was independently certified with Java 21,
  Nextflow 25.10.7 and Docker in GitHub Actions run `31726522504`, then pinned
  by OCI digest `sha256:fb7d6625fb5adaed43ced8bd051a875038714180bcfcd7c8e467204f72882de9`.

## Lint and static validation

Nextflow 26.04.6 linted 87 project files without errors. One existing warning remains:
`LEGACY_STEP` accesses `projectDir` inside a process. This warning belongs to
the compatibility wrapper and does not affect native scientific processes.

Python discovery is no longer ambiguous: `tests/run_unit_tests.py` and the
GitHub Actions run `31520434883` both reported `Discovered 62 tests`, `Ran 62
tests`, and `OK`. The clean DESeq2 1.0.1 build plus regression/cache workflow
passed in run `31526144851`. The current branch revision was then revalidated
successfully by contracts, unit tests, and the published image regression in
run `31532483855`. After the runtime pin, manual branch run `31537899176`
confirmed Nextflow 25.10.7 installation, 62 unit tests, contract/lint checks and
the published DESeq2 image regression.

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

The successful top-level RNA baseline ran 58 processes with zero failures,
peak concurrency of five tasks, five requested CPUs, and 10 GB requested
memory. Nextflow reported 2m22s of summed successful task duration; wall time
was about six minutes including Slurm polling and report generation.

## Provenance assessment

The real runs emitted versions, command/execution metadata, manifests and
checksums at the tested API boundaries. The Import checksum validation detected
both line-ending changes before analysis, demonstrating fail-closed behavior.
Container digest recording is not yet uniform: tags remain in several execution
documents and the downloaded OCI digest is not propagated into every manifest.

## Retirement decision

The RNA-seq legacy path is ready for retirement after the production Import
policy, native foundation, certified MultiQC, DESeq2 batch design and native
Gene Report were completed. The annotated `rnaseq-legacy-v1.0.0` tag preserves
its final executable snapshot. ChIP-seq and Integrative legacy pipelines must
remain available. Their global retirement is blocked by:

1. the Bowtie2 production image missing samtools, despite the passing conditional Slurm regression;
2. IDR remaining explicitly not implemented;
3. unresolved task-cache persistence in the available Nextflow runtime;
4. STAR 2.7.11b crashing during index generation in the available cluster runtime;
5. no production-scale, top-level ChIP-seq regression against a reviewed biological dataset.

The detailed decisions and deviations are tracked in
`docs/scientific-deviation-log.md`.

## Next controlled pass

1. Reproduce the one-process cache probe with an administrator-supported
   Nextflow installation and, if necessary, report the empty task DB upstream.
2. Publish one declarative Bowtie2 2.5.4 + samtools 1.20 image and rerun alignment.
3. Implement and validate IDR, or explicitly exclude it from the first release.
4. Repeat Differential Binding with the certified DESeq2 1.0.1 image.
5. Validate STAR with the pinned production image/runtime rather than the crashing cluster package.
6. Run the top-level ChIP-seq workflow on one reviewed reduced biological dataset before reconsidering legacy removal.
