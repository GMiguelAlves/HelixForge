# Integrative benchmark scripts

`execute_negative_contract_validation.py` derives the frozen 10E mutations
from the positive synthetic baseline, exercises the declared validation layer
twice, compares deterministic outcomes and writes compact contract results.
`run_negative_contracts_slurm.sh` is the guarded Slurm launcher; it refuses
scratch roots outside the dedicated HelixForge contract-benchmark namespace.

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

The manifest/re-entry equivalence utilities are:

- `prepare_reentry_fixture.py` verifies the exact 10B input bytes, relocates
  the public manifest bundles and validates contracts before execution;
- `compare_reentry_routes.py` applies the frozen `IR1`–`IR4` comparisons;
- `finalize_reentry_benchmark.py` creates compact provenance, checksums and
  the audit package;
- `validate_reentry_results.py` performs administrative validation without
  requiring Git on compute nodes;
- `run_reentry_benchmark_slurm.sh` coordinates the two isolated Slurm routes.

These utilities do not run real biological integration, negative contracts or
the baseline freeze.
