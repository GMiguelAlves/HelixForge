# DESEQ2_DB_CONTRAST

Evaluates exactly one named numerator/denominator Wald contrast from a cached
model. `lfc_threshold` is an explicit reporting/significance classification
threshold; it does not silently change the DESeq2 null hypothesis.

The input BED may contain the complete pre-filter peak universe. The module
requires every peak retained in the fitted model to have a unique matching
BED4 identity, restores those coordinates in model order, and excludes only
the peaks already removed by the model's explicit count filter.
