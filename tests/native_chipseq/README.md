# Native ChIP-seq foundation tests

- `test_metadata.py`: inputs, multiple samples, controls, biological and
  technical replicate identity and early failures.
- `run_stub.sh`: complete native QC + Bowtie2 alignment contract with three
  records and a matched control.
- `run_cache_tests.sh`: repeat stub execution with `-resume` and require cached
  tasks.

A real reduced Bowtie2/Samtools comparison is intentionally separate because
the required environment is not installed in the development host.

