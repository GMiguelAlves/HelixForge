# DE_PREFLIGHT

Validates the Differential Expression API boundary before a statistical
provider starts. It verifies Import API checksums, sample identity, numeric
counts, factors, replication, contrasts, and model-matrix rank. Compatibility
mode generates the same pairwise contrasts as the legacy DESeq2 script.

The module uses only the Python standard library and performs no statistical
fit.
