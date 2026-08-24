# Contributing to HelixForge

Thank you for improving HelixForge. Contributions must preserve scientific
meaning, explicit contracts and reproducibility.

## Before opening a change

1. Open or reference an issue describing the user/scientific need.
2. Branch from `master` using a short `contrib/` name.
3. Keep commits small, descriptive and in English.
4. Do not combine scientific-policy changes with unrelated refactoring.

## Required checks

```bash
python3 -m pip install -r requirements-dev.txt
bin/helixforge-doctor
python3 tests/run_unit_tests.py
nextflow lint .
```

Add the smallest appropriate stub, contract, functional or regression test.
Fixtures must be synthetic or redistributable and must not contain credentials,
personal paths or private research data.

## Scientific changes

A pull request that changes algorithms, statistical models, defaults,
thresholds, ID normalization, biological interpretation or output semantics
must state:

- the scientific rationale and references;
- the affected contract/model version;
- expected changes in results;
- the validation dataset and comparison method;
- whether the scientific deviation log and user documentation changed.

Do not treat visually improved plots as validation. Preserve biological signal,
design estimability, numerical tolerance and the declared universe of each
statistical test.

## Pull requests

Use the repository template. A reviewer should be able to distinguish:

- software behavior from scientific behavior;
- tested facts from untested assumptions;
- stable public interfaces from experimental/internal implementation;
- byte-exact from semantic regression expectations.

Do not create release tags in feature pull requests. See
`docs/release-checklist.md` for release authority and gates.
