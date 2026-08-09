# Native ChIP-seq Differential Binding tests

The unit suite validates preflight design, contrast, replicate, identity and
count-provider helpers without R, featureCounts or biological data. `run_stub.sh`
executes the isolated multi-contrast graph and the top-level ChIP-seq
`differential_binding` mode. No scientific result is validated.
