# ChIP-seq benchmark scripts

The scripts are retained as reproducibility and audit material for the frozen
v1.0.0-rc.1 benchmark. They are organized by benchmark arm so that the active
surface no longer mixes dataset construction, Slurm launchers, evaluators and
historical methods experiments in one directory.

| Directory | Purpose |
|---|---|
| [`common/`](common/) | Shared manifest aggregation, broad consensus and ChIPs toolchain helpers. |
| [`synthetic_narrow/`](synthetic_narrow/) | Construction, execution, evaluation, figures and audit packaging for Synthetic Narrow. |
| [`synthetic_broad/`](synthetic_broad/) | Construction, execution, coverage evaluation, figures and audit packaging for Synthetic Broad. |
| [`real_narrow/`](real_narrow/) | Download validation, reference preparation, execution, CTCF evaluation and audit packaging. |
| [`real_broad/`](real_broad/) | Download validation, reference preparation, execution, H3K27me3 evaluation and audit packaging. |
| [`archive/rn3_null_methods/`](archive/rn3_null_methods/) | Frozen, non-active RN3 null-method attempts retained to prevent undocumented repetition. |

The two obsolete Real Broad partial-runtime helpers were removed during the
administrative freeze. Generated Python bytecode and cache directories are not
benchmark artifacts and are excluded.

These scripts document the completed benchmark and are not an alternative
user interface to HelixForge. Site-specific Slurm paths are historical runtime
examples; users should execute the supported pipeline entry points documented
in the main project documentation.

No script submits a nested Slurm job from a Nextflow process. Destructive
cleanup helpers are scoped to the benchmark-specific scratch directory and
must be reviewed before reuse at another site.
