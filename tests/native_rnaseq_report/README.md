# Native RNA-seq Report API tests

- `test_report_api.py`: input contract, checksum/alignment validation and manifest finalization.
- `run_stub.sh`: two-process DSL2 `-stub-run` with the real provider wiring.
- `run_real.sh`: executes the module-owned R provider in its pinned container
  against two genes and four samples, then validates tables, figures, HTML,
  manifest and R session semantically.

The full R provider is not installed for unit/stub tests. The real test is the
container certification gate.
