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

## Native RNA-seq QC

Run the two-run integration and regression fixture:

```bash
bash tests/native_qc/run_mock_regression.sh
```

It executes the legacy command sequence and the native Nextflow QC graph with
the same deterministic mock tools. It compares byte-level merged FASTQs,
FastQC reports, and the MultiQC data table, then writes `comparison.tsv` and
`benchmark.tsv` under `results/test/native-qc-regression/`.

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
validation is pinned to the tested official Nextflow 26.04.2 runtime; Docker
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
