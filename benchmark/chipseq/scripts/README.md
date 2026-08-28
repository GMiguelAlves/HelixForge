# Planned benchmark script contracts

This directory intentionally contains contracts, not implementations. Scripts
are added only after this design is approved and must not silently modify the
frozen protocol.

| Planned command | Inputs | Outputs | Responsibility |
|---|---|---|---|
| `prepare_synthetic_reference` | narrow/broad JSON | FASTA, FAI, repeats BED, reference manifest | Deterministic `synthetic_chip_v1` construction and validation |
| `generate_narrow_truth` | reference manifest, narrow JSON | narrow truth, summits, negatives, manifest | Declare balanced point-like truth before simulation |
| `generate_broad_truth` | reference manifest, broad JSON | broad truth, negatives, manifest | Declare balanced continuous domains before simulation |
| `simulate_chips` | reference, truth, frozen ChIPs parameters | replicate/Input FASTQs, logs, manifest | Invoke ChIPs v2.4 without embedding scientific logic elsewhere |
| `download_public_data` | sample/reference registries | immutable source files, receipt | Download only declared URLs and validate size/MD5 |
| `validate_dataset` | registries, files, truth/config | validation TSV/JSON | Fail on missing, extra or inconsistent artifacts |
| `run_independent_chipseq` | raw FASTQ, reference, frozen parameters | BAMs, peaks, QC, logs, manifest | Execute the separately launched Bash/Python comparison path |
| `evaluate_narrow` | truth, HelixForge and independent peaks | metrics TSV/JSON, matched pairs | Apply the frozen bipartite matching and AUPRC definitions |
| `evaluate_broad` | truth, calls and coverage | metrics TSV/JSON, topology graph | Apply union, IoU, fragmentation and merging definitions |
| `evaluate_real_data` | declared outputs and external references | plausibility metrics and plots | Evaluate only predeclared biological expectations |
| `collect_performance` | Nextflow trace, Slurm accounting | performance TSV | Record wall time, CPU, memory and storage without polling heavily |
| `render_figures` | frozen metrics tables | SVG/PNG figures | Render figures without recalculating scientific statistics |

Each implementation must support `--help`, validate inputs, use explicit seeds
where applicable, write atomically, emit software versions and return non-zero
on a contract violation. Scripts must never submit nested Slurm jobs or delete
files outside the run-specific scratch directory.
