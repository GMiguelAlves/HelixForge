# Native Peak Annotation tests

- `test_peak_annotation.py`: small parameter, coordinate, priority, seqname,
  and invalid-build tests;
- `run_stub.sh`: subworkflow stub, `-resume`, and top-level
  `chipseq_run_mode=annotation` stub.

## Regional-catalog integration

`test_regional_annotation.py` checks complete candidate coordinates, genes
outside a one-base core, an unfilled one-base gap, empty catalogs, checksum
substitution failures and candidate semantics through aggregation and HTML.
The existing non-regional contract tests remain applicable.

For a reduced native execution, generate the interval fixture:

```bash
python3 tests/native_chipseq_peak_annotation/generate_regional_fixture.py --outdir /path/to/fixture
nextflow run tests/native_chipseq_peak_annotation/regional_report.nf \
  -c tests/native_chipseq_peak_annotation/nextflow.config \
  --fixture_dir /path/to/fixture --outdir /path/to/results
python3 tests/native_chipseq_peak_annotation/validate_regional_result.py --results /path/to/results
```

Use an execution profile/site configuration with Python and BEDTools available
for the real run. The entry point also supports `-stub-run`; the scientific
output validator is for the real run, not mock outputs. An identical run with
`-resume` should cache all nine eligible tasks. No FASTQs, alignment, peak
calling, new significance threshold or biological benchmark is involved.
