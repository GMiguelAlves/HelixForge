# Benchmarks

Benchmarks consume Nextflow `trace.tsv` files and record duration, CPU,
peak RSS, read/write volume, and output size for fixed scenarios. They should
run on controlled infrastructure or on releases, not block ordinary CI on
shared runners.

## Benchmark areas

- [`rnaseq/`](rnaseq/README.md): scientific validation protocol for the
  `v1.0.0-rc.1` Salmon production path, including synthetic truth, public data,
  subsampling, external-reference concordance and Slurm resource measurement.
- [`chipseq/`](chipseq/README.md): frozen `v1.0.0-rc.1` baseline covering
  controlled narrow/broad enrichment and public K562 CTCF/H3K27me3 data.
- [`integrative/`](integrative/README.md): preregistered integration benchmark
  covering synthetic truth, manifest re-entry, negative contracts and a matched
  public RNA × ChIP dataset. Scientific execution has not started.
- [`scenarios/`](scenarios/): focused migration and implementation scenarios.
- [`reports/`](reports/): compact benchmark reports approved for versioning.
