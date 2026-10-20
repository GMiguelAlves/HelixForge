# NFCORE_CONSENSUS

Explicit `nfcore_2_1` policy, pinned to nf-core/chipseq 2.1.0. The original
BEDTools merge/column-collapse command and unmodified upstream helper determine
regional boundaries and presence filtering. Inputs are grouped by the existing
HF dataset/experiment/condition/target/reference/peak-type key; different marks
or conditions are not silently pooled.

An explicit `min_replicates` from 1 to the library count is required. Library
tokens are mapped reversibly to stable metadata IDs before the upstream helper
runs; original peak names and quantitative fields remain available. BEDTools
merges overlapping **and bookended** intervals (`-d 0`); connected chains may
span several source peaks. No positive gap distance is introduced.

`consolidated_peaks.bed` contains regional candidates, not confirmed occupancy.
`support_by_library.tsv` describes all libraries, including zero support.
`support_core.bed` separately retains atomic bases supported by at least
`max(2, min_replicates)` libraries. Shared bases and regional presence answer
different questions; neither is a statistical test of occupancy.

The process stages its adapter and the checksummed upstream helper as inputs.
It provides Conda/OCI configuration, deep caching, stub execution, versions,
commands and resource metadata. See the [policy guide](../../../docs/guides/nfcore-consensus-homer.md).
