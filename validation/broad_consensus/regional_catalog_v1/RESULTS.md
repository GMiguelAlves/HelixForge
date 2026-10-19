# Regional catalog 1.0.0: validation results

The prospective protocol passed all 18 cases (three seeds, six scenarios). No acceptance criterion or seed was changed after execution. These are new synthetic aligned-read data, not a rerun or reclassification of a historical benchmark.

| Scenario | Seeds passed | Minimum supported base precision | Shared-domain recall | Regional fragmentation | Atomic-core fragmentation | Merging |
|---|---:|---:|---:|---:|---:|---:|
| balanced | 3/3 | 100.0000% | 100.00% | 0.00% | 0.00%–4.17% | 0.00% |
| heterogeneous | 3/3 | 100.0000% | 100.00% | 0.00% | 54.17%–70.83% | 0.00% |
| discordant | 3/3 | 100.0000% | 100.00% | 0.00% | 62.50%–75.00% | 0.00% |
| library_specific | 3/3 | 99.9111% | 100.00% | 0.00% | 45.83%–45.83% | 0.00% |
| variable_signal | 3/3 | 99.8257% | 100.00% | 0.00% | 79.17%–83.33% | 0.00% |

All three null cases produced zero candidates and zero supported regions. Private domains were not recovered as shared domains under the frozen 50%-coverage recovery definition. Small false-positive base extensions were still present in some positive cases; exact false-positive bases and unrounded metrics are retained in [validation_summary.json](validation_summary.json).

All three width classes passed the separate recall gates. Candidate coverage matched the original-call union exactly; the exported core matched an independent BEDTools calculation, and no original call was split into multiple catalog records.

The 36 contract tests passed. Native Nextflow 25.10.7 passed stub and real execution; an identical resume was CACHED, while provider-source and threshold changes reexecuted the task. The full context → catalog → aggregate route completed and then cached all three processes on resume.

## Interpretation and boundaries

This validates separation of regional candidates, spatial support and core for the declared synthetic challenge. It does not turn every candidate into true occupancy, estimate occupancy FDR, certify a physical fragment model in biological libraries, or prove generalization to repeats or alignment artifacts. It does not establish that the caller itself never fragments real domains.

The data are independent of the previous development inputs, and the interval evaluator does not import production geometry. Simulation and implementation share the same development team; this is not independent external validation.

The provider remains opt-in. No historical benchmark, pinned result or default was replaced. The recorded runtime uses an existing Conda environment; OCI/Apptainer and a fresh solve of environment.yml were not certified by this validation.
