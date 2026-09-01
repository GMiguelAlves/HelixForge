# Negative-contract harness correction

```text
VALIDATION_HARNESS_CORRECTION = PRE_SCIENTIFIC_INTERPRETATION
CORE_CHANGED = NO
FIXTURES_CHANGED = NO
EXPECTED_BEHAVIORS_CHANGED = NO
IC_GATES_CHANGED = NO
```

The first technical execution rejected all three `IC-MAN-*` fixtures, but the
harness evaluated the public Integration API union schema's outer `oneOf`
message. That message was generic and did not expose the frozen field-level
substring (`required property` or `not one of`), so the harness incorrectly
classified the three correct rejections as mismatches.

The executor was restricted to the assay-specific RNA run-manifest schema for
these three diagnostics. The schema documents and the HelixForge validators
were not modified. The first compact audit archive is retained as
`helixforge-integrative-negative-contracts-10e-20260901-attempt1.zip`.
