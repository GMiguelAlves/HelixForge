# HelixForge RNA-seq benchmark

This directory defines the scientific benchmark for the HelixForge
`v1.0.0-rc.1` RNA-seq production path. It contains protocol, metadata and
small configuration files only. Raw FASTQs, generated reads, references,
Nextflow work directories and result trees must never be committed.

## Frozen subject

| Item | Frozen value |
|---|---|
| HelixForge | `v1.0.0-rc.1` |
| Git commit | `fc38ada8f592bb57a13467965a718ce0df7fb6ce` |
| Nextflow | `25.10.7` |
| Java | `21` |
| RNA-seq mode | `full` |
| Analysis provider | Salmon only; STAR is excluded |
| Import policy | `production_v1` |
| Library protocol | `full_length` |
| `countsFromAbundance` | `lengthScaledTPM` |
| Transcript ID handling | preserve versions; no bar/version stripping |
| Statistical provider | DESeq2 Wald |

The benchmark measures this immutable RC. A scientific code or parameter
change creates a new benchmark subject and requires rerunning affected cases.

## Three levels

1. **A — synthetic ground truth:** 1,200 human genes, two conditions, three
   replicates per condition, paired-end reads and known transcript/gene truth.
2. **B — public biological dataset:** untreated versus dexamethasone-treated
   airway smooth muscle cells from four paired donors, `GSE52778` /
   `SRP033351`.
3. **C — coverage robustness:** deterministic 100%, 50%, 25% and 10% subsets
   of a 5,000,000-pair-per-sample public-data benchmark base.

## Authoritative documents

- [Full protocol](protocol/benchmark_protocol.md)
- [Metrics](protocol/metrics.md)
- [Interpretation and release gates](protocol/interpretation_criteria.md)
- [Expected Slurm cost](protocol/cost_estimate.md)
- [Risks and limitations](protocol/risks_and_limitations.md)
- [Stage 9B.1 protocol/implementation audit](protocol/9b1_protocol_discrepancies.md)
- [Dataset registry](datasets/dataset_registry.md)
- [Dataset provenance](datasets/dataset_provenance.tsv)
- [Public sample manifest](datasets/airway_samples.tsv)
- [Synthetic design](configs/synthetic_design.json)
- [Frozen run matrix](configs/run_matrix.tsv)
- [Subsampling plan](configs/subsampling_plan.tsv)
- [Required scripts](scripts/README.md)
- [Provenance model](provenance/README.md)
- [Report template](reports/benchmark_report_template.md)

## Execution boundary

All scientific executions occur on the institutional Slurm cluster. The head
node runs only the Nextflow driver, read-only inspection and lightweight Slurm
commands. Scientific tools, simulation, subsampling, metric calculation and
reference runs execute in allocations.

Concurrency starts at five jobs. It may increase to ten only when the recorded
preflight shows at least one compute node completely `IDLE`, the user's queue
is empty or small, and the shared queue is not under visible pressure. The
decision and the exact `sinfo`/`squeue` snapshot are provenance. Ten is a
ceiling, not a target.

## Status

Stage 9A freezes the design. It does **not** download FASTQs or execute the
benchmark. Scripts listed under `scripts/` are implementation requirements for
Stage 9B and must be reviewed before the first scientific job.
