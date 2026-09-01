# ChIP-seq benchmark scripts

The scripts are retained as reproducibility and audit material for the frozen
v1.0.0-rc.1 benchmark. They are organized by benchmark arm so that the active
surface no longer mixes dataset construction, evaluators and historical
methods experiments in one directory.

| Directory | Purpose |
|---|---|
| [`common/`](common/) | Shared manifest aggregation, broad consensus and baseline validation helpers. |
| [`synthetic_narrow/`](synthetic_narrow/) | Construction, execution, evaluation, figures and audit packaging for Synthetic Narrow. |
| [`synthetic_broad/`](synthetic_broad/) | Construction, execution, coverage evaluation, figures and audit packaging for Synthetic Broad. |
| [`real_narrow/`](real_narrow/) | Download validation, reference preparation, execution, CTCF evaluation and audit packaging. |
| [`real_broad/`](real_broad/) | Download validation, reference preparation, execution, H3K27me3 evaluation and audit packaging. |
| [`archive/rn3_null_methods/`](archive/rn3_null_methods/) | Frozen, non-active RN3 null-method attempts retained to prevent undocumented repetition. |

Slurm launchers, runtime builders, preflight collectors and audit packagers
were removed after their evidence was captured in the reports and manifests.
Generated Python bytecode and cache directories are not benchmark artifacts
and are excluded.

These scripts document the completed benchmark and are not an alternative
user interface to HelixForge. Site-specific paths in retained evidence are
historical runtime examples; users should execute the supported pipeline entry
points documented in the main project documentation.

No active benchmark script submits jobs or performs cleanup. Reproduction uses
the portable preparation, execution, evaluation and rendering scripts; cluster
submission is deliberately left to the site-specific operator.
