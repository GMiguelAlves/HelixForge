# CHIPSEQ_EXECUTION_PLAN

Consumes normalized metadata, explicit stage selections and an optional DB
specification. Reuses the existing DB specification/design validators; rejects
missing contrasts, insufficient replication, mixed units and rank deficiency
before scientific producers can receive metadata. It does not fit a model.
Reports requested/not-requested components. Stub status never asserts validity.

Resources: one CPU, 1 GB, ten minutes, deep cache. Uses the existing metadata
container or the declared Conda environment; no runtime is installed by code.
