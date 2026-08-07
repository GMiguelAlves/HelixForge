# OmicsFlow

OmicsFlow is a compatibility-first Nextflow DSL2 skeleton for the existing
RNA-seq, ChIP-seq, and IntegrateSeq pipelines. The scientific Bash, Python, and
R implementations are preserved under `pipelines/*/legacy` and remain directly
executable.

This first version delegates scheduling to Nextflow while invoking each legacy
coarse step in local mode. It does not replace tools, algorithms, parameters,
filenames, or result layouts.

## Workflows

- `rnaseq`
- `chipseq`
- `integrative`
- `all`

## Quick start

```bash
nextflow run . -profile local --workflow rnaseq \
  --rnaseq_config /path/to/rnaseq/pipeline_config.sh
```

Inspect the complete graph without running scientific tools:

```bash
nextflow run . -profile test -stub-run --workflow all
```

Ask the existing orchestrators to print their own dry-run commands:

```bash
nextflow run . -profile local --workflow chipseq --legacy_dry_run true \
  --chipseq_config pipelines/chipseq/legacy/config/example_pipeline_config.sh
```

The default configs remain the versioned `config/pipeline_config.sh` files in
each legacy pipeline. Create their existing untracked user configuration files
before a real run.

See [docs/nextflow.md](docs/nextflow.md),
[docs/script-mapping.md](docs/script-mapping.md), and
[docs/limitations.md](docs/limitations.md).

