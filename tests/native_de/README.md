# Native differential expression tests

The golden dataset has three conditions with three replicates each and a
balanced batch covariate. It exercises three explicit Wald contrasts.

- `run_stub.sh`: compiles and executes every native module stub.
- `run_regression.sh`: runs the preserved legacy R script and the native API
  in the same DESeq2 image, then compares tables and model estimates.
- `run_invalid_inputs.sh`: checks duplicate samples, missing design fields,
  invalid contrast levels, rank deficiency, and unsupported LRT.
- `run_cache_tests.sh`: checks contrast-only and model cache boundaries.
