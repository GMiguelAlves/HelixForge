# Integrative benchmark scripts

Only compact, deterministic benchmark utilities belong here. They must not
import `integration.*` when producing truth or independent-reference results.

- `generate_synthetic_truth.py` creates the preregistered 1,000-entity truth
  table and its checksum manifest from `configs/synthetic_design.json`.
- `validate_design.py` performs administrative validation only: row counts,
  class totals, required states, frozen statuses, JSON parsing and checksums.
- `prepare_synthetic_fixture.py` materializes positive RNA/ChIP terminal
  manifests, evidence artifacts and fixture-only policies without importing
  HelixForge code or exposing truth labels to the workflow.
- `evaluate_synthetic_integration.py` independently reconstructs joins,
  missing states, regulatory classes, Candidate Score components, Fisher/BH
  tests and correlations, then applies the frozen `IS*` criteria.
- `compare_synthetic_runs.py` compares the two required executions after
  semantic normalization and records byte identity only where appropriate.
- `run_synthetic_benchmark_slurm.sh` is the auditable Slurm launcher for the
  two official workflow executions and their compute-node evaluations.

These utilities are specific to the synthetic execution arm. They do not run
manifest re-entry, real biological integration, negative contracts or the
baseline freeze.
