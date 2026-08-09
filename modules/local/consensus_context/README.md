# CONSENSUS_CONTEXT

Validates one experiment group before consensus or IDR dispatch. It enforces
complete grouping identity, deterministic biological/technical replicate keys,
matched Peak Calling/Peak QC manifests, exact peak type, and explicit strategy
parameters. It never merges replicates or consolidates intervals.
