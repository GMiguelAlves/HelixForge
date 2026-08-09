# Tests

Pure BED/BEDPE conversion tests live in
`tests/native_chipseq_peak_qc/test_peak_qc.py`. The Nextflow fixture provides a
stub contract test. Real SAMtools/BEDTools validation is deferred to the final
ChIP-seq validation stage.
