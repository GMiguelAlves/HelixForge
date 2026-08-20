# RUN_MANIFEST

Builds one `rnaseq_run_manifest.json` or `chipseq_run_manifest.json` conforming
to Integration API v1. Inputs are normalized metadata, a Reference Bundle
manifest, explicit upstream manifests, explicit artifact paths and semantic
descriptors supplied by the DAG. The module never searches a result tree.
The Integration API schema directory is a tracked process input, so validation
does not depend on an implicit repository mount inside a container.

The process computes SHA-256 values for tracked artifact inputs, preserves the
producer-declared published location and records compact provenance. Schema,
semantic and filesystem validation are independently available through
`bin/validate_integration_manifest.py`.
