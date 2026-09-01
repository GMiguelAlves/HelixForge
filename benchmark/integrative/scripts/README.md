# Integrative benchmark scripts

Only compact, deterministic benchmark utilities belong here. They must not
import `integration.*` when producing truth or independent-reference results.

- `generate_synthetic_truth.py` creates the preregistered 1,000-entity truth
  table and its checksum manifest from `configs/synthetic_design.json`.
- `validate_design.py` performs administrative validation only: row counts,
  class totals, required states, frozen statuses, JSON parsing and checksums.

Future scientific launchers and independent-reference code must be added in
their execution PRs. No benchmark workflow is launched by these scripts.
