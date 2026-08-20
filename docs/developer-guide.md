# Developer guide

## Local checks

```bash
python3 -m pip install -r requirements-dev.txt
NEXTFLOW=/path/to/nextflow bin/helixforge-doctor
python3 tests/run_unit_tests.py
nextflow lint .
```

Use Nextflow 25.10.7 and Java 21 for release decisions. Unit-test discovery is
centralized in `tests/run_unit_tests.py`; CI must report the actual number of
tests rather than accept an empty discovery run.

## Contracts

Read these before adding a provider:

1. [Public API](public-api.md)
2. [Module contracts](module_contracts.md)
3. [Versioning](versioning.md)
4. The relevant scientific API document
5. [Terminal manifests](terminal_manifests.md)

Processes are single-responsibility wrappers around providers. Workflows
consume channels and manifests, not hard-coded result paths. A new provider
normalizes its outputs to the existing API rather than leaking tool-specific
formats downstream.

## Tests

- Unit/contract: Python tests under `tests/`.
- Stub: every public workflow and native module must compose without tools.
- Functional: reduced deterministic data and actual provider execution.
- Regression: semantic or byte-exact comparison according to artifact class.
- Operational: container, Slurm, cache/resume and clean-clone validation.

Test data must be synthetic or redistributable, generated reproducibly, small
enough for CI, and documented. Never commit credentials, institutional paths,
private datasets, Nextflow caches, or large generated artifacts.

## Scientific changes

Any change to algorithms, defaults, thresholds, statistical models, identifier
normalization or output semantics requires:

- an explicit scientific rationale;
- a contract/model version decision;
- updated regression expectations;
- an entry in the scientific deviation log when behavior changes;
- review distinct from mechanical refactoring.

See `CONTRIBUTING.md` for the pull-request checklist and
`docs/release-checklist.md` for release gates.
