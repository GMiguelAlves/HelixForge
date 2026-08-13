# RNASEQ_CONTEXT

Compatibility adapter that reads `pipeline_config.sh` once and materializes its
RNA-seq input locations as tracked files. It does not download data, prepare
references, submit jobs, or run scientific software.

This adapter is temporary: native command-line parameters or a declarative run
manifest can replace it without changing `RNASEQ_METADATA` or
`REFERENCE_BUNDLE`.
