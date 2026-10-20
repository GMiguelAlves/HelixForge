# ChIP stage-composition tests

Run contract tests with:

```bash
python3 -m unittest tests.native_chipseq_composition.test_plan tests.native_chipseq_composition.test_continuation -v
```

The functional driver exercises the public workflow entry points:

```bash
python3 tests/native_chipseq_composition/run_functional.py --stub --output /path/to/new-stub-case
python3 tests/native_chipseq_composition/run_functional.py --output /path/to/new-real-case
```

Use a new output directory for each test. Set `NEXTFLOW_BIN` to the official
certified launcher when it is not on `PATH`. Real-tool execution requires the
existing ChIP-seq/report toolchain, DESeq2/jsonlite and a Python environment
with JSON Schema support and pyBigWig. The driver installs nothing; on HPC it
must run inside a compute allocation because its nested task executor is local.

Coverage includes DB enabled/disabled, consensus and IDR provider inputs,
metadata/control/replicate identity, mandatory checksums, missing/incompatible
inputs, omission semantics, terminal producer links, report-only isolation and
cached reuse of compatible QC/alignment/peak tasks when DB is enabled later.
The continuation regression checks fully materialized nested JSON maps before
fan-out: 128 plans are read by eight channels for both consensus and IDR.
It verifies producer identities and terminal artifact types without retrying
failed executions or weakening completeness checks. CI retains terminal
manifests and workflow logs when an execution fails.
Fixtures are artificial and do not measure biological accuracy or performance.
Use `--only-full` to check only full composition with DB disabled/enabled.
Unit tests use labelled placeholder files only to exercise checksum contracts;
the real fixture creates actual BAM/BAI files with samtools. A stub explicitly
does not certify file integrity or scientific outputs.
