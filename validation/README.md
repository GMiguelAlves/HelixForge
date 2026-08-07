# Reproducibility validation

Each workflow has `input/` and `expected/` directories. Future validation tests
will compare deterministic tables semantically, use numeric tolerances for
floating-point results, and validate binary formats with format-aware tools.

The first Trim Galore golden baseline must be generated with
`tests/native_trim_galore/run_comparison.sh`. Production baselines still require
the unchanged legacy and hybrid pipelines to run against the same input data,
configuration, Trim Galore version, and compute environment.
