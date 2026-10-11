# Quick Start

## 1. Environment smoke test

```bash
git clone https://github.com/GMiguelAlves/HelixForge.git
cd HelixForge
curl -fsSL https://get.nextflow.io | NXF_VER=25.10.7 bash
NEXTFLOW="$PWD/nextflow" bin/helixforge-doctor
./nextflow run . -profile test -stub-run \
  --workflow all \
  --outdir results/quickstart
```

This checks workflow composition, declared files, terminal contracts, and the
four public entry points without running scientific tools. It does not validate
biological correctness.

## 2. Small real Integrative example

The repository includes a deterministic synthetic fixture generator. It does
not contain patient or unpublished data.

```bash
python3 tests/integrative_workflow/prepare_fixture.py \
  --output /tmp/helixforge-integrative-fixture

./nextflow run tests/integrative_workflow/main.nf \
  -c tests/integrative_workflow/nextflow.config \
  --rna_manifest /tmp/helixforge-integrative-fixture/rna/rnaseq_run_manifest.json \
  --chip_manifest /tmp/helixforge-integrative-fixture/chip/chipseq_run_manifest.json \
  --outdir results/integrative-example
```

Expected terminal files:

```text
results/integrative-example/integration/integrative_run_manifest.json
results/integrative-example/integration/100-report/integrative_report/integrative_report.html
```

The example normally completes within a few minutes and runs real deterministic
Python transformations over reduced synthetic data. It is a software smoke
test, not a biological benchmark.

## 3. Individual public entry points

```bash
./nextflow run . -profile test -stub-run \
  --workflow rnaseq --rnaseq_run_mode full \
  --outdir results/rnaseq-stub

./nextflow run . -profile test -stub-run \
  --workflow chipseq --chipseq_run_mode full \
  --outdir results/chipseq-stub

./nextflow run . -profile test -stub-run \
  --workflow all \
  --outdir results/all-stub
```

The standalone Integrative entry point requires completed RNA and ChIP terminal
manifests and their sibling `integration_artifacts/` directories. The fixture
from step 2 satisfies this contract:

```bash
./nextflow run . -profile test -stub-run \
  --workflow integrative \
  --rna_manifest /tmp/helixforge-integrative-fixture/rna/rnaseq_run_manifest.json \
  --chip_manifest /tmp/helixforge-integrative-fixture/chip/chipseq_run_manifest.json \
  --outdir results/integrative-stub
```

## 4. Before real data

- Read the [workflow guide](workflows.md).
- Create explicit sample/configuration files; data download is outside the DAG.
- Pin references through the Reference Bundle contract.
- Select a supported execution profile.
- Keep scientific policy files under version control.
- Treat the test fixtures as structural examples only.
