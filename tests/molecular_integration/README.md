# Cross-Assay Harmonization and Molecular Integration tests

Unit, contract and semantic-regression tests:

```bash
python -m unittest tests.molecular_integration.test_molecular_integration -v
```

Prepare small Stage 3 evidence bundles, then run the two Stage 4 modules:

```bash
python tests/molecular_integration/prepare_fixture.py --output /tmp/helixforge-integration-fixture
nextflow run tests/molecular_integration/main.nf \
  -c tests/molecular_integration/nextflow.config \
  --rna_evidence /tmp/helixforge-integration-fixture/rna \
  --chip_evidence /tmp/helixforge-integration-fixture/chip
```

Add `-stub-run` to validate only the DSL2 output contracts. This is a test DAG,
not the future top-level Integrative workflow.
