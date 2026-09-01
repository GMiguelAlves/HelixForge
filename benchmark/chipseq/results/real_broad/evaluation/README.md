# Real Broad compact evaluation

Compact evidence from the frozen K562 H3K27me3 benchmark evaluated on Slurm.
`benchmark_summary.json` is the classification entry point; `metrics.json`
contains all retained metrics and `null_overlap.tsv` records every frozen RB3
rotation. The trace and QC table are retained for audit. FASTQs, BAMs, genome
indexes and work directories are intentionally excluded from Git.

Figures are rendered from these files with:

```bash
python benchmark/chipseq/scripts/real_broad/render_real_broad_figures.py \
  --metrics benchmark/chipseq/results/real_broad/evaluation/metrics.json \
  --null-overlap benchmark/chipseq/results/real_broad/evaluation/null_overlap.tsv \
  --output-dir benchmark/chipseq/results/real_broad/figures
```
