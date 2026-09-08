# Runtime amendment — Bowtie2 Perl launcher

The first H3K27me3 alignment attempt stopped before producing any alignment.
The Conda environment itself was installed below the institutional home path
`/home/CLUSTER_USER/`. That absolute prefix was embedded in
Perl's `Config_heavy.pl`; Perl interpreted `@bio` inside double-quoted
configuration strings and the upstream `bowtie2` launcher could not compile.
The downstream `samtools` errors were consequences of receiving no SAM header.

This is an operational runtime-path conflict, not an input, index, resource or
scientific-method failure. The same installed Bowtie2 2.5.5 core binary is now
invoked by a minimal Bash launcher with the upstream `--wrapper basic-0`
contract. It selects the small or large index binary from the actual index
extension. Bowtie2 arguments, index bytes, FASTQs and every frozen scientific
parameter remain unchanged.

The failed alignment jobs were `16771`–`16775`; no BAM was produced. FastQC job
`16770` was cancelled by Nextflow fail-fast after the alignment error, while
the other 15 FastQC tasks completed. The failed Nextflow session again exposed
no reusable task-cache database, so the corrected attempt is a separately
identified retry rather than a claim of successful `-resume` reuse.

```text
CONFLICT = RUNTIME_PATH_INCOMPATIBILITY
DISCOVERED = BEFORE_SUCCESSFUL_ALIGNMENT
SCIENTIFIC_RESULTS_INSPECTED = NO
SCIENTIFIC_PARAMETERS_CHANGED = NO
BIAS_RISK = NONE
STATUS = RESOLVED_FOR_RETRY
```

## R runtime selection for differential binding

The corrected H3K27me3 run completed the upstream scientific path through peak
counting, then stopped before fitting the differential-binding model. The
general ChIP-seq environment exposed R 4.5.3 and DESeq2 1.50.2 but did not
contain `jsonlite`, which is a declared dependency of `DESEQ2_DB_MODEL`. The
benchmark already retained the certified analysis runtime used by HelixForge:
R 4.3.3, Bioconductor 3.18.1, DESeq2 1.42.0 and jsonlite 1.8.8.

The launcher verifies all four versions before Nextflow starts. A minimal
`Rscript` dispatcher is placed in the benchmark runtime directory that was
already first in the frozen global `PATH`; the `PATH` value and the Nextflow
configuration therefore remain byte-for-byte unchanged. The dispatcher
selects the certified R runtime only when an R script is invoked. No package
was installed, no environment was modified and no scientific input, model,
contrast, filter or parameter changed. The retry resumes the same Nextflow work
directory so eligible completed tasks can be recovered without deliberately
resubmitting the heavy upstream branch.

Because two diagnostic resume attempts were stopped before heavy processing,
the launcher also accepts `HELIXFORGE_RESUME_SESSION`. The recovery selects the
original partial execution (`serene_edison`) explicitly instead of implicitly
selecting the most recent cancelled session.

```text
CONFLICT = DECLARED_R_DEPENDENCY_NOT_SELECTED
DISCOVERED = BEFORE_DIFFERENTIAL_BINDING_MODEL
SCIENTIFIC_PARAMETERS_CHANGED = NO
RUNTIME_REUSED = CERTIFIED_R_ANALYSIS_RC
STATUS = RESOLVED_FOR_RESUME
```

The original task cache remained unavailable even when the original session,
project directory, commit, command, configuration and `PATH` were restored.
Diagnostic attempts were cancelled after context/reference submission and
before any repeated alignment. The benchmark therefore continues through an
explicit native re-entry at the already published peak-count matrix. This
re-entry executes only `DESEQ2_DB_MODEL`, `DESEQ2_DB_CONTRAST` and
`DB_AGGREGATE`; it does not recompute FASTQ QC, alignment, BAM processing, peak
calling, peak QC or consensus.

## Filtered peak identity contract

The real H3K27me3 model completed successfully with the frozen explicit filter:
526,451 input peaks were reduced to 467,451 fitted peaks. The contrast then
stopped because its identity guard required the unfiltered BED and the fitted
model to contain identical sets, even though filtering is an intentional part
of `DESEQ2_DB_MODEL`.

The general `DESEQ2_DB_CONTRAST` contract was corrected in commit `60e8486`.
The input BED may be a superset after model filtering, but it must contain every
fitted peak exactly once. The contrast deterministically reorders and subsets
the BED to the fitted model identities before attaching coordinates. Missing
or duplicate identities still fail. No count, coordinate, model, contrast,
threshold or statistical parameter changed.

The isolated re-entry completed `DESEQ2_DB_MODEL`, `DESEQ2_DB_CONTRAST` and
`DB_AGGREGATE` successfully in Slurm jobs 16948-16950. This correction is part
of the general ChIP-seq module and is therefore the frozen scientific code
target for the remaining real ChIP-seq arm.

```text
CONFLICT = POST_FILTER_IDENTITY_CONTRACT_TOO_STRICT
DISCOVERED = AFTER_MODEL_FIT_AND_BEFORE_CONTRAST_RESULT
INPUT_PEAKS = 526451
FITTED_PEAKS = 467451
SCIENTIFIC_PARAMETERS_CHANGED = NO
GENERAL_MODULE_FIX = 60e8486
STATUS = RESOLVED_AND_VALIDATED
```
