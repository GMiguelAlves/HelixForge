# Standardized Evidence Model v1 tests

Run unit, contract and semantic-regression checks from the repository root:

```bash
python -m unittest tests.evidence_providers.test_evidence_providers -v
```

Compile and exercise each thin DSL2 module without scientific runtimes:

```bash
nextflow run tests/evidence_providers/main.nf -c tests/evidence_providers/nextflow.config --assay rnaseq -stub-run
nextflow run tests/evidence_providers/main.nf -c tests/evidence_providers/nextflow.config --assay chipseq -stub-run
```

Omit `-stub-run` for the dependency-free integration fixture. Inputs are bound
by artifact ID and staged as `path` inputs; no result-tree scan is permitted.
