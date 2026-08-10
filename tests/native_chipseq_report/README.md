# Native ChIP-seq Report tests

- `test_report.py`: optional/required roles, IDR status, build and identity
  validation, order independence, schema/example agreement, and self-contained
  HTML behavior;
- `run_stub.sh`: isolated Report API, `-resume`, top-level native mode, and
  unchanged legacy fallback.

Fixtures are synthetic manifests. No scientific provider, biological dataset,
benchmark, Slurm executor, container, or legacy visual comparison is run.
