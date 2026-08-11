# Controlled real validation report

Date: 2026-08-11  
Branch: `contrib/final-validation`  
Overall decision: **BLOCKED for global legacy retirement**

This report records the first controlled real validation pass after the native
API consolidation. It distinguishes a missing test from a demonstrated defect.
No large dataset, Slurm cluster, Apptainer runtime, or Conda installation was
introduced for this pass.

## Environment

- Windows host with Ubuntu under WSL2.
- Nextflow 26.04.6, build 12646, executed from the existing local JAR.
- Java 21.0.11.
- Docker Engine 29.1.3.
- WSL filesystem: about 929 GB free; Windows volume: about 28 GB free at audit.
- No Slurm, Apptainer/Singularity, Conda/Mamba, or Micromamba runtime was added.
- R 4.3.3 and Python 3 with pandas 2.1.4 were already available in WSL.

The project declares Nextflow `>=24.10.0`; this pass used a newer runtime. The
cache result below must be repeated on native Linux storage and the production
Nextflow version before it is interpreted as a pipeline cache defect.

## Capacity and decision matrix

| Component | Real native evidence | Legacy comparison | Status | Blocker or qualification |
|---|---|---|---|---|
| Trim Galore | Yes | Yes | READY_TO_RETIRE | Minimal paired-end fixture only |
| FastQC | Yes, 0.12.1 | Contract/mock comparison only | CONDITIONAL | Real report generated; no real legacy pair in this pass |
| MultiQC | No real run | Mock comparison | BLOCKED | Fixed image did not finish downloading within the controlled limit |
| FASTQ merge | Native mock/regression evidence | Yes | CONDITIONAL | Not rerun with a fully real QC chain |
| STAR | Yes, 2.7.11b | Yes | READY_TO_RETIRE | Cache must be repeated on native Linux storage |
| Salmon | Yes, 1.10.3 | Yes | READY_TO_RETIRE | Cache must be repeated on native Linux storage |
| Salmon Import | Yes, current `helixforge-import:1.0.0` | Yes | CONDITIONAL | Workflow-level normalization/count policy still requires a release decision |
| STAR Import | Yes | Yes | CONDITIONAL | Native provider ran on host; current Python production image was unavailable |
| DESeq2 | No certified production run | Legacy began but failed in obsolete image | BLOCKED | Production image build did not complete; obsolete image has incompatible plotting packages |
| ChIP BAM processing | Yes | Expected metrics validated | CONDITIONAL | Scientific behavior passed; cache reuse failed in this environment |
| Bowtie2 index | Yes, 2.5.4 | No | CONDITIONAL | Index completed |
| Bowtie2 alignment | No | No | BLOCKED | Configured image lacks `samtools`, which the module invokes |
| MACS3 | Yes, 3.0.4, two replicates | No | CONDITIONAL | Real peaks passed; Python adapter container and cache remain unresolved |
| FRiP | Stub only | No | BLOCKED | No real SAMtools/BEDTools environment was assembled |
| Consensus | Stub only | No | BLOCKED | No real provider container configured |
| Differential binding | Stub only | No | BLOCKED | featureCounts container is unset and DESeq2 is not certified |
| Annotation | Contract/static evidence | No | BLOCKED | No controlled real run in this pass |
| Tracks | Stub only | No | BLOCKED | deepTools container is unset |
| Report | Stub/contract evidence | No visual regression | CONDITIONAL | Depends on blocked upstream components |
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

### Salmon Quantification API

The legacy command and native Salmon process passed semantic comparison for:

- `quant.sf` numeric values;
- `cmd_info.json` and `lib_format_counts.json`;
- the `aux_info` file set and `meta_info.json`;
- `ambig_info.tsv` and fragment-length distribution;
- Salmon log presence and mapping statistics.

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

The real Bowtie2 index completed. Alignment then failed at the first
`samtools` pipe because `quay.io/biocontainers/bowtie2:2.5.4--he20e202_1` does
not contain samtools. The module contract requires both Bowtie2 and samtools,
matching its Conda environment. A declarative composite image is required; the
existing image must not be patched in place.

### MACS3

MACS3 3.0.4 ran on two treatment replicates against one matched input. Each
replicate produced one valid narrowPeak plus summit and signal artifacts. The
manifests retained distinct biological replicate identifiers, fixed parameters,
checksums, metrics, caller version, and matched-control provenance.

The Python slim adapter image lacks `ps`, which Nextflow requires to collect
task metrics. For this isolated scientific test only, adapters ran on the WSL
host while MACS3 remained containerized. The production Docker profile needs a
small adapter image containing `procps` or an equivalent supported solution.

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
**CONDITIONAL**, not silently accepted. Repeat the same scripts on a native
Linux filesystem and on the production Slurm shared filesystem.

## Execution environments

- Docker: real execution validated for Trim Galore, FastQC, STAR, Salmon,
  current Salmon Import, Bowtie2 indexing, and MACS3.
- Slurm: configuration-only validation. `profiles/slurm.config` assigns the
  Slurm executor, queue size, and submit rate. No non-legacy native code invokes
  `sbatch`, `srun`, `qsub`, or `bsub`; nested submission was not found.
- Apptainer/Singularity: not tested because no runtime is installed.
- Conda: not tested because no runtime is installed.
- MultiQC: fixed image not available locally after the bounded pull attempt.

## Lint and static validation

Nextflow 26.04.6 linted 87 files without errors. One existing warning remains:
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

## Provenance assessment

The real runs emitted versions, command/execution metadata, manifests and
checksums at the tested API boundaries. The Import checksum validation detected
both line-ending changes before analysis, demonstrating fail-closed behavior.
Container digest recording is not yet uniform: tags remain in several execution
documents and the downloaded OCI digest is not propagated into every manifest.

## Retirement decision

The complete legacy pipelines must remain available. Component retirement can
start only for Trim Galore, STAR, and Salmon after review of this report.
Import is close but needs an explicit decision on workflow-level identifier and
`countsFromAbundance` policy. Global retirement is blocked by:

1. the unbuilt DESeq2 production image and incomplete real DE regression;
2. the Bowtie2 image missing samtools;
3. the missing real MultiQC run;
4. missing real FRiP, consensus, differential-binding, annotation, and track runs;
5. unresolved cache reuse on the target filesystem;
6. absence of a production Slurm run, which is intentionally not simulated.

The detailed decisions and deviations are tracked in
`docs/scientific-deviation-log.md`.

## Next controlled pass

1. Let CI build the declarative DESeq2 image, then run model/contrast regression.
2. Publish one declarative Bowtie2 2.5.4 + samtools 1.20 image and rerun alignment.
3. Make the metadata adapter image Nextflow-compatible by adding `procps`.
4. Obtain the pinned MultiQC image and run the complete native QC entrypoint.
5. Execute FRiP and consensus with the existing two-replicate MACS3 fixture.
6. Run featureCounts/DESeq2 differential binding only after item 1.
7. Repeat cache tests on native Linux and then on the actual Slurm filesystem.

