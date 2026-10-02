# TRIM_GALORE_SINGLE

Native single-end companion to `TRIM_GALORE`. It accepts exactly one FASTQ,
uses the configured quality and minimum-length parameters, materializes the
legacy-compatible trimmed path, and emits the common report/version/status
envelope. It never invents a mate or fragment-length prior.
