# DESEQ2_DB_MODEL

Fits one DESeq2 Wald model from raw integer peak counts. Filtering is explicit
and audited. DESeq2 estimates median-of-ratios size factors; normalized counts
are an output, never the test input. Batch is supported only through the
validated `~ batch + condition` design.
