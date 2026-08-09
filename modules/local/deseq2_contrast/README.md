# DESEQ2_CONTRAST

Evaluates exactly one explicit Wald contrast from a previously fitted
`DESEQ2_MODEL`. The legacy table remains unchanged; `common_results.tsv` adds
the provider-neutral `statistic` and `design` fields.

Changing a contrast invalidates this process and aggregation, but not model
fitting. LRT is deliberately unsupported because it is absent from the legacy
RNA-seq pipeline.
