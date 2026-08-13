# Native RNA-seq Report API tests

- `test_report_api.py`: input contract, checksum/alignment validation and manifest finalization.
- `run_stub.sh`: two-process DSL2 `-stub-run` with the real provider wiring.

The full R provider is intentionally not installed during the small local test.
Container execution is certified separately before production use.
