# Native ChIP-seq Consensus/IDR tests

`test_consensus_api.py` exercises input identity, replicate-policy, support-threshold,
atomic-segment and pending-IDR contracts without external bioinformatics tools.

`run_stub.sh` checks the DSL wiring for a Consensus union and the honest IDR provider
abstraction. It does not execute BEDTools or an IDR statistical runtime.
