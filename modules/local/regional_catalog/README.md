# REGIONAL_CATALOG 1.0.0

Opt-in broadPeak consolidation using the existing BEDTools runtime. Select
`--chipseq_consensus_method regional_catalog --chipseq_min_replicates 2`.
Existing union, intersection, replicate-support and IDR semantics are unchanged.

The catalog joins touching called intervals; it never fills a positive gap.
Every candidate retains its full envelope. `core_supported.bed` contains the
separate atomic segments covered by at least the explicit number of evidence
units. `regional_support.tsv` records called bases and fraction for every
candidate/library pair, including zeros. It is spatial support, not read depth.
Transitive overlap may produce long envelopes; multiple units touching different
parts do not establish co-occupancy of the entire region. Inspect the core
fraction and per-unit coverage rather than treating the envelope as uniformly supported.

Classification:

- `candidate`: called in at least one unit, no qualifying core;
- `spatially_supported_candidate`: contains a qualifying core; its tails need
  not have replicated support;
- `occupancy_status=not_assessed`: neither class asserts reproducible biological
  occupancy. No IP/Input ratio is converted to significance or FDR.

`supported_regions.bed` retains the complete envelopes in the second class.
`consolidated_peaks.bed` is the **entire candidate catalog**, not an accepted
occupancy set. Downstream gene associations must preserve this interpretation.
Scores/p-values are preserved per original call, not combined across libraries.

Resources: 2 CPUs, 4 GB, 2 hours, deep cache, no automatic retries. The existing
consensus Docker/Apptainer image settings are reused; Conda pins Python 3.12.4
and BEDTools 2.31.1. The provider source is staged explicitly as a cache input.

Tests: [contract tests](../../../tests/native_chipseq_consensus/test_regional_catalog.py)
and [separate scientific validation](../../../validation/broad_consensus/regional_catalog_v1/README.md).
The [18-case prospective synthetic validation](../../../validation/broad_consensus/regional_catalog_v1/RESULTS.md)
and native Nextflow stub/real/cache/integration tests passed. This validates the
declared synthetic challenge, not biological occupancy or universal broad-mark
performance. The provider remains opt-in and does not retrospectively replace
a frozen benchmark or pinned run.
