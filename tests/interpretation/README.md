# Regulatory interpretation and prioritization tests

Run unit, contract and legacy-regression tests:

```bash
python -m unittest tests.interpretation.test_interpretation -v
```

Prepare molecular evidence and exercise the integration-to-prioritization test DAG:

```bash
python tests/molecular_integration/prepare_fixture.py --output /tmp/helixforge-interpretation-fixture
nextflow run tests/interpretation/main.nf -c tests/interpretation/nextflow.config \
  --rna_evidence /tmp/helixforge-interpretation-fixture/rna \
  --chip_evidence /tmp/helixforge-interpretation-fixture/chip
```

Add `-stub-run` to validate process contracts without executing Python logic.
This is a component test DAG, not the final Integrative coordinator.
