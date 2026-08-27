# GSE52778 benchmark results

This directory contains the small, version-controlled evidence from the
full-size GSE52778 RNA-seq benchmark. Raw reads, references, Nextflow work
directories and complete audit logs are intentionally excluded.

- `sample_qc.tsv` and `qc_summary.json`: per-sample and aggregate QC.
- `metrics/`: quantitative concordance, DEG overlap and ranking metrics.
- `biological-expectations.*`: preregistered response and control-gene checks.
- `performance_summary.*`: descriptive Slurm performance with private paths and
  compute-node names removed.
- `gse52778-run-validation.json`: structural and terminal-output validation.
- `independent-comparison-summary.json`: independent Salmon/tximport/DESeq2
  comparison, including the accepted numerical limitation.

The scientific interpretation and limitations are documented in
`../../reports/gse52778_full_benchmark.md`.

