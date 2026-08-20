# Tests

Run all dependency-free Python tests through standard discovery:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

CI uses `python3 tests/run_unit_tests.py`, which applies the same discovery
pattern and fails explicitly if zero tests are found.

Run the dependency-free consolidation checks with:

```bash
python tests/architecture/test_consolidation.py
```

`run_stub_tests.sh` compiles and executes the four workflow graphs with process
stub blocks. It does not run scientific tools.

`native_chipseq_differential_binding/` adds pure contract tests and isolated/
top-level stubs. It does not run featureCounts, DESeq2, containers, Slurm,
biological regression or benchmarks.

The `validation/` datasets will hold golden scientific outputs. They are kept
separate from syntax/stub tests because byte-for-byte comparison is not valid
for every bioinformatics format.

## Integrative legacy characterization

Run the dependency-free scientific characterization baseline with:

```bash
python tests/integrative_legacy_characterization/test_characterization.py
```

The fixture exercises every legacy Integrative class, the fixed candidate-score
heuristic, Fisher/BH statistics, RNA/ChIP correlations, functional summaries
and the report renderer. Its 38 normalized golden artifacts are also discovered
by `tests/run_unit_tests.py`. Plot bytes are deliberately excluded because
visual outputs are not regression-critical and the baseline host had no
`ggplot2` installation.

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

## Native RNA-seq QC

Run the two-run integration and regression fixture:

```bash
bash tests/native_qc/run_mock_regression.sh
```

It executes the legacy command sequence and the native Nextflow QC graph with
the same deterministic mock tools. It compares byte-level merged FASTQs,
FastQC reports, and the MultiQC data table, then writes `comparison.tsv` and
`benchmark.tsv` under `results/test/native-qc-regression/`.

Run the reusable MultiQC module with the certified immutable OCI image and two
deterministic FastQC records:

```bash
tests/native_multiqc/run_real.sh
```

This Docker test validates the HTML/data outputs, sample inventory, versions,
status, trace, and repository digest. It is also executed by the dedicated
GitHub Actions certification workflow.

## Native Alignment API / STAR

Run the real legacy-versus-native regression with the same pinned container:

```bash
bash tests/native_alignment/run_regression.sh
```

It compares BAM records, BAI/idxstats, gene-count categories, flagstat, MAPQ,
and normalized STAR logs, then writes `comparison.tsv` and `benchmark.tsv`
under `results/test/native-alignment-regression/`.

Validate cache reuse and parameter/read invalidation:

```bash
bash tests/native_alignment/run_cache_tests.sh
```

## Native Quantification API / Salmon

Validate the channel and output contract without scientific software:

```bash
bash tests/native_quantification/run_stub.sh
```

Run Salmon 1.10.3 through the unchanged legacy command and the native API,
then compare `quant.sf`, JSON metadata, `aux_info`, logs, and mapping statistics:

```bash
bash tests/native_quantification/run_regression.sh
```

Validate deep-cache reuse and invalidation by parameter, FASTQ, and
transcriptome content:

```bash
bash tests/native_quantification/run_cache_tests.sh
```

The regression writes `comparison.tsv` and `benchmark.tsv` under
`results/test/native-quantification-regression/`. The fragment-length
distribution is compared semantically because Salmon samples that distribution
stochastically even when the command and inputs are identical.

Set `NEXTFLOW_BIN` or `NEXTFLOW_JAR` when Nextflow is not on `PATH`. Cache
validation is pinned to the certified official Nextflow 25.10.7 runtime; Docker
must be available.

## Native Import API

Compile both providers without scientific software:

```bash
bash tests/native_import/run_stub.sh
```

Compare STAR gene-count import against the unchanged legacy Python script:

```bash
bash tests/native_import/run_star_regression.sh
```

Compare Salmon import against the unchanged legacy R script, including
tx2gene, counts, TPM, sample metadata, and semantic validation of the new
length matrix and `SummarizedExperiment`:

```bash
bash tests/native_import/run_salmon_regression.sh
```

Validate full cache reuse plus provider-parameter, manifest, and GTF
invalidation:

```bash
bash tests/native_import/run_cache_tests.sh
```

Both regressions write `comparison.tsv` and `benchmark.tsv` under their
respective `results/test/native-import-*-regression/` directories.

## Native ChIP-seq foundation

Run metadata, input, control and replicate validation:

```bash
python -m unittest tests/native_chipseq/test_metadata.py
```

Compile the three-record raw-QC and Bowtie2 alignment graph without scientific
software, then optionally verify `-resume` cache reuse:

```bash
bash tests/native_chipseq/run_stub.sh
bash tests/native_chipseq/run_cache_tests.sh
```

Run the real reduced SAMtools BAM-processing fixture and expected compatibility
failures without downloading software:

```bash
bash tests/native_chipseq_bam/run_functional.sh
bash tests/native_chipseq_bam/run_invalid_inputs.sh
```

Validate Peak Calling API context, formats and error paths, then compile the
two-replicate treatment/control graph:

```bash
python -m unittest tests/native_chipseq_peaks/test_peak_api.py
bash tests/native_chipseq_peaks/run_stub.sh
```

When MACS3 3.0.4 is already available, run the deterministic functional and
cache-invalidation suites. They exit 77 rather than downloading software when
the caller is absent:

```bash
bash tests/native_chipseq_peaks/run_functional.sh
bash tests/native_chipseq_peaks/run_cache_tests.sh
```

Validate Peak QC identity, explicit filters, fragment conversion, peak
statistics and manifest aggregation, then compile the two-replicate Peak QC
graph and its deep-cache boundaries without scientific tools:

```bash
python -m unittest tests/native_chipseq_peak_qc/test_peak_qc.py
bash tests/native_chipseq_peak_qc/run_stub.sh
```

Real SAMtools/BEDTools FRiP validation is deferred to the final ChIP-seq
functional validation stage.
