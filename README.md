# OmicsFlow

OmicsFlow is a compatibility-first Nextflow DSL2 implementation for the existing
RNA-seq, ChIP-seq, and IntegrateSeq pipelines. The scientific Bash, Python, and
R implementations are preserved under `pipelines/*/legacy` and remain directly
executable.

The RNA-seq QC layer is native: FastQC before trimming, Trim Galore, FastQC
after trimming, per-sample FASTQ merge, merged-read FastQC, and MultiQC are
separate DSL2 processes. Download and metadata preparation remain wrappers,
and STAR, Salmon, tximport, DESeq2, batch correction, and final reports remain
unchanged behind compatibility wrappers. Existing filenames and result
directories are preserved.

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
[docs/native-trim-galore.md](docs/native-trim-galore.md),
[docs/native-rnaseq-qc.md](docs/native-rnaseq-qc.md),
[docs/module_contracts.md](docs/module_contracts.md),
[docs/script-mapping.md](docs/script-mapping.md), and
[docs/limitations.md](docs/limitations.md).
