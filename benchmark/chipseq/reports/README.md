# ChIP-seq benchmark reports

Reports are assembled only from frozen metric tables and provenance evidence.
All four scientific arms and the administrative consolidation are complete in
the source tree.

- [`synthetic_narrow_benchmark.md`](synthetic_narrow_benchmark.md): completed
  per-replicate and IDR ground-truth benchmark (`PASS_WITH_LIMITATIONS`);
- [`synthetic_broad_benchmark.md`](synthetic_broad_benchmark.md): completed
  broad-domain ground-truth benchmark (`PASS_WITH_LIMITATIONS`), including
  exact independent-path concordance and the frozen fragmentation limitation;
- [`real_narrow_benchmark.md`](real_narrow_benchmark.md): completed K562 CTCF
  biological benchmark (`PASS_WITH_LIMITATIONS`), including exact independent
  concordance and the frozen RN3 control-capacity limitation;
- [`real_broad_benchmark.md`](real_broad_benchmark.md): completed K562
  H3K27me3 biological benchmark (`PASS_WITH_LIMITATIONS`), with exact
  independent-path concordance and all frozen RB1-RB5 dispositions;
- [`chipseq_benchmark_final_report.md`](chipseq_benchmark_final_report.md):
  cross-arm classification, evidence, limitations and release assessment.

Figures must link to their source TSV/JSON and rendering command. A report may
not recompute or redefine metrics. Missing evidence is displayed as missing or
blocked; it is never represented by placeholder scientific values.
