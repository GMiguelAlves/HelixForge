# ChIP-seq benchmark reports

Reports are assembled only from frozen metric tables and provenance evidence.
An absent report indicates that its benchmark arm has not yet been executed.

Required future reports:

- [`synthetic_narrow_benchmark.md`](synthetic_narrow_benchmark.md): completed
  per-replicate and IDR ground-truth benchmark (`PASS_WITH_LIMITATIONS`);
- [`synthetic_broad_benchmark.md`](synthetic_broad_benchmark.md): completed
  broad-domain ground-truth benchmark (`PASS_WITH_LIMITATIONS`), including
  exact independent-path concordance and the frozen fragmentation limitation;
- `real_narrow_benchmark.md`: QC, FRiP, replicate concordance, IDR, CTCF motif
  centrality, reference overlap and declared locus inspection;
- `real_broad_benchmark.md`: QC, FRiP, coverage concordance, replicate-support
  domains, reference overlap, annotation summary and declared locus views;
- `performance_report.md`: Slurm accounting, Nextflow trace, storage and
  independent-path overhead;
- `chipseq_benchmark_summary.md`: independent arm classifications, deviations,
  limitations, retained evidence and cleanup receipt.

Figures must link to their source TSV/JSON and rendering command. A report may
not recompute or redefine metrics. Missing evidence is displayed as missing or
blocked; it is never represented by placeholder scientific values.
