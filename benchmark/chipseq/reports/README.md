# Planned ChIP-seq benchmark reports

No scientific report is generated during design freeze. After execution, each
arm must produce a compact report assembled only from frozen metric tables and
the top-level provenance manifest.

Required future reports:

- `synthetic_narrow_benchmark.md`: per-replicate, consensus and IDR truth
  accuracy, score curves, summit error, signal strata and fragmentation;
- `synthetic_broad_benchmark.md`: base accuracy, domain recovery, IoU, boundary
  error, fragmentation/merging topology and width/signal strata;
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
