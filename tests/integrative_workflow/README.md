# Native Integrative workflow tests

Prepare the portable terminal-manifest fixture and run the complete manifest-to-report DAG:

```bash
python tests/integrative_workflow/prepare_fixture.py --output /tmp/helixforge-integrative-fixture
nextflow run tests/integrative_workflow/main.nf -c tests/integrative_workflow/nextflow.config \
  --rna_manifest /tmp/helixforge-integrative-fixture/rna/rnaseq_run_manifest.json \
  --chip_manifest /tmp/helixforge-integrative-fixture/chip/chipseq_run_manifest.json
```

Add `-stub-run` for the deterministic contract DAG and `-resume` for the local cache probe. This workflow does not read or execute `pipelines/integrative/legacy`.
