# RNASEQ_REPORT_CONTEXT

Validates the tracked Import and Differential Expression API artifacts used by
the RNA-seq Report API. It also normalizes provider parameters into a context
document and a shell environment consumed by the report provider.

The same contract supports cumulative `report`/`full` execution and the
terminal-only `report_reentry` mode. Re-entry verifies the retained abundance,
ordered sample table, and aggregate DE table against their upstream manifests
before rendering.

The module does not discover files in output directories and does not perform
scientific analysis.
