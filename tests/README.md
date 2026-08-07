# Tests

`run_stub_tests.sh` compiles and executes the four workflow graphs with process
stub blocks. It does not run scientific tools.

The `validation/` datasets will hold golden scientific outputs. They are kept
separate from syntax/stub tests because byte-for-byte comparison is not valid
for every bioinformatics format.

## Native Trim Galore

Validate module mechanics without downloading scientific software:

```bash
bash tests/native_trim_galore/run_mock_integration.sh
```

Compare the legacy command and native process with the same pinned container:

```bash
bash tests/native_trim_galore/run_comparison.sh
```

The comparison checks decompressed FASTQ SHA-256 values, read counts, trimming
reports, and writes a small elapsed-time benchmark. It requires Docker access
to `quay.io`.
