# Native ChIP-seq Peak QC tests

- `test_peak_qc.py`: identity, reference-bound, filter, BED/BEDPE, peak parser,
  and manifest aggregation tests using pure functions.
- `run_stub.sh`: isolated Peak QC API stub with two independent treatment
  replicates.

Real SAMtools/BEDTools execution, functional FRiP validation, legacy comparison,
container execution, Slurm, and benchmark are intentionally deferred to the
final ChIP-seq validation stage.
