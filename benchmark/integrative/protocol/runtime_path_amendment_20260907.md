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
