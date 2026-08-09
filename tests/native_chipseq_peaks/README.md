# Native ChIP-seq peak calling tests

- `test_peak_api.py`: context, control association, schema semantics and peak format validation.
- `run_stub.sh`: isolated Peak Calling API stub.
- `run_functional.sh`: deterministic paired-end fixture, two treatment replicates, matched input, real MACS3, output validation and resume.
- `run_cache_tests.sh`: deep-cache invalidation for q-value, peak type, treatment BAM and control BAM changes.

The functional script exits with code 77 and an explicit reason when MACS3 is not already available. It does not install software or pull containers automatically.
