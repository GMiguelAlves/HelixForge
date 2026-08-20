# ChIP-seq legacy retirement

Status: **retired from the current source tree**.

The final executable snapshot was preserved before removal:

- annotated tag: `chipseq-legacy-v1.0.0`;
- target commit: `b641d76a0c91666b84fc613bd238e7dbaa90499b`;
- tag message: `Final ChIP-seq legacy snapshot`.

## Retirement gate

The native `chipseq_run_mode=full` path completed the reduced synthetic Slurm
validation from FASTQ QC through Bowtie2, BAM processing, MACS3, FRiP, Consensus,
Differential Binding, Annotation, Tracks and Report. IDR 2.0.4.2 also completed
as an optional Consensus strategy. Provider containers have independent OCI
certification. The tested cluster exposes no supported Apptainer or other
container runtime on its compute nodes; this external operational limitation is
recorded in `docs/chipseq-container-certification.md` and is not a scientific
release gate.

## Removed from the main branch

- the shell ChIP-seq coordinator and scripts under `pipelines/chipseq/legacy`;
- ChIP-seq `LEGACY_STEP` aliases and dedicated fallback branches;
- the legacy reference, QC/alignment and peak-analysis subworkflows;
- `chipseq_native_*` compatibility switches;
- `chipseq_continue_legacy_peaks`;
- the implicit `chipseq_duplicate_mode=legacy` policy.

The versioned configuration engine and templates moved unchanged to
`pipelines/chipseq/config`. The shared `LEGACY_STEP` module was subsequently
removed when Integrative retired; no active workflow imports it.

## Historical recovery

Do not mix tagged legacy outputs with current native outputs inside one run.
For audit or regression, inspect the immutable snapshot in a separate checkout:

```bash
git worktree add ../helixforge-chipseq-legacy chipseq-legacy-v1.0.0
```

The current branch accepts only explicit native ChIP-seq modes and providers.
Reviewed biological regressions remain a post-release validation milestone, as
decided before retirement.
