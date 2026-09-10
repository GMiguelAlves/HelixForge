# Negative contract validation

## Executive Summary

All 14 frozen Integration API contract fixtures behaved as preregistered. The positive 10B/10C-derived baseline passed before mutation, all critical invalid inputs failed at their declared layer, and valid-but-unmatched evidence remained separate. No valid terminal integration output was produced by a failing fixture.

## Why 10E Was Executed Before 10D

The benchmark protocol numbering was not changed.

Stage 10E was executed before Stage 10D as an operational risk-reduction decision because contract fixtures are small and inexpensive, while 10D requires acquisition and processing of the real GSE133183 dataset.

No 10D or 10E criteria, fixtures, gates or scientific expectations were changed by this execution-order decision.

`10D_STATUS = NOT_STARTED`, `10D_SKIPPED_TEMPORARILY = YES`, `10D_CANCELLED = NO`.

## Frozen Design

The authoritative inventory SHA-256 remained `ba87581f3f6d8ce5ab58a510f801ad361844e239b2cab3941ccd3692be961014`. HelixForge target `dc0218ce902302da476910595bb133c82fee927c` and integration workflow `d0d1e7499e5b42be8294da3d85e402fa90a1cfe2` were unchanged.

## Positive Baseline

`BASELINE_VALIDATION = PASS`. Both run manifests passed JSON Schema, semantic, filesystem, checksum and reference compatibility validation before mutations.

## Fixture Inventory

| Test | Expected | Observed | Stage | Status |
|---|---|---|---|---|
| IC-CON-01 | FAIL | FAIL | semantic validation | PASS |
| IC-CON-02 | FAIL | FAIL | semantic validation | PASS |
| IC-CON-03 | PRESERVE_SEPARATELY | PRESERVE_SEPARATELY | harmonization | PASS |
| IC-CTX-01 | PRESERVE_SEPARATELY | PRESERVE_SEPARATELY | harmonization | PASS |
| IC-ENT-01 | FAIL | FAIL | harmonization | PASS |
| IC-MAN-01 | FAIL | FAIL | JSON Schema | PASS |
| IC-MAN-02 | FAIL | FAIL | JSON Schema | PASS |
| IC-MAN-03 | FAIL | FAIL | JSON Schema | PASS |
| IC-MARK-01 | NORMALIZE | NORMALIZE | harmonization | PASS |
| IC-MARK-02 | PRESERVE_SEPARATELY | PRESERVE_SEPARATELY | harmonization | PASS |
| IC-REF-01 | FAIL | FAIL | compatibility | PASS |
| IC-REF-02 | FAIL | FAIL | compatibility | PASS |
| IC-REF-03 | FAIL | FAIL | compatibility | PASS |
| IC-REF-04 | FAIL | FAIL | compatibility | PASS |

## Schema Validation

Malformed envelope, missing provenance and invalid artifact type were rejected by JSON Schema.

## Semantic Validation

Undeclared and self contrasts were rejected before scientific integration.

## Reference / Assembly Compatibility

Reference, genome and assembly mismatches failed at preflight compatibility validation.

## Annotation Compatibility

The annotation mismatch failed at preflight compatibility validation.

## Contrast Semantics

Invalid contrasts failed. Different valid RNA and ChIP contrasts produced one `RNA_ONLY` and one `CHIP_ONLY` mapping, with no matched or fused contrast.

## Entity Normalization and Collisions

Unambiguous frozen aliases/version/prefix rules normalized successfully. Two versioned source IDs collapsing to one assay-level ID failed loudly.

## Mark / Context Validation

`HP1` normalized to `SmHP1`, lowercase histone notation normalized to canonical case, and unknown non-empty mark/context values were preserved exactly.

## Provenance Validation

The frozen missing-provenance fixture was rejected by JSON Schema. Deeper lineage-conflict cases were not part of the authoritative 10E inventory.

## Filesystem / Checksum Validation

The positive baseline passed filesystem and checksum validation. Negative missing-file/checksum fixtures were not present in the frozen authoritative inventory and were not added post-freeze.

## Expected Failure Behavior

All expected failures returned explicit diagnostics and produced zero final scientific outputs.

## Valid Non-integrable Evidence

Different but individually valid contrasts were preserved separately as `RNA_ONLY` and `CHIP_ONLY`; no false combined class or cross-contrast merge was observed.

## IC Acceptance Criteria

| Criterion | Status | Fixtures |
|---|---|---|
| IC1 | PASS | IC-REF-01;IC-REF-02 |
| IC2 | PASS | IC-REF-03;IC-REF-04 |
| IC3 | PASS | IC-CON-01;IC-CON-02;IC-CON-03 |
| IC4 | PASS | IC-ENT-01 |
| IC5 | PASS | IC-MAN-01;IC-MAN-02;IC-MAN-03 |
| IC6 | PASS | IC-MARK-01;IC-MARK-02;IC-CTX-01 |

## Determinism

All fixtures were executed twice. Outcome, validation stage, error class/state and status were identical after path sanitization.

## Limitations

This arm is intentionally contract-level and uses the frozen 14-case inventory. Missing-artifact, checksum-mismatch, schema-version, duplicate-artifact and lineage-conflict cases are covered elsewhere by unit tests or remain candidates for a future preregistered contract expansion; they were not inserted into 10E after the freeze. Performance is descriptive on a shared Slurm cluster.

The first technical attempt used the public union schema's top-level diagnostic,
which correctly rejected all three malformed manifests but hid the frozen
field-level error substring. Before scientific interpretation, the harness was
restricted to the manifest's assay-specific schema so it could record the
underlying diagnostic. This changed neither input, expected behavior, gate nor
HelixForge core behavior; the first compact attempt was retained for audit.

## Final Classification

```text
TECHNICAL_EXECUTION = PASS
POSITIVE_BASELINE = PASS
SCHEMA_REJECTION = PASS
SEMANTIC_REJECTION = PASS
REFERENCE_COMPATIBILITY = PASS
ANNOTATION_COMPATIBILITY = PASS
CONTRAST_VALIDATION = PASS
VALID_CONTRAST_ISOLATION = PASS
ENTITY_COLLISION_HANDLING = PASS
NORMALIZATION_BEHAVIOR = PASS
PROVENANCE_VALIDATION = PASS
FILESYSTEM_INTEGRITY_VALIDATION = NOT_APPLICABLE
FAILURE_OUTPUT_SAFETY = PASS
DETERMINISM = PASS

NEGATIVE_CONTRACT_BENCHMARK = PASS
```

## Next Stage

Return to the frozen real biological integration stage (10D) after maintainer review. This report does not start 10D and does not authorize 10F or a tag.
