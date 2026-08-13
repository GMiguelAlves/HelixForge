# Native ChIP-seq Consensus/IDR tests

`test_consensus_api.py` exercises input identity, replicate-policy,
support-threshold, atomic-segment and statistical-IDR contracts without
external bioinformatics tools.

`run_stub.sh` checks the DSL wiring for Consensus union and the statistical IDR
provider. Unit tests cover IDR rank/threshold/seed command construction, output
normalization and Differential Binding acceptance. The real provider runtime is
validated by `run_real.sh` with the pinned OCI image. The production Slurm
harness accepts `HELIXFORGE_CHIPSEQ_CONSENSUS_METHOD=idr` for the complete DAG.
