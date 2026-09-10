# Manifest / re-entry equivalence benchmark

## Executive Summary

The direct terminal-manifest route and the independently relocated manifest-relative re-entry route produced scientifically equivalent Integrative results. All frozen IR1–IR4 release gates passed.

## Benchmark Question

Given the same frozen scientific evidence, does manifest-based re-entry produce the same integrative scientific result as the direct path? **Yes.**

## Frozen Design

- HelixForge: `v1.0.0-rc.1`
- Scientific target: `dc0218ce902302da476910595bb133c82fee927c`
- Integration workflow: `d0d1e7499e5b42be8294da3d85e402fa90a1cfe2`
- 10B benchmark commit: `d4f8347`

## 10B Scientific Baseline

Route A compatibility with the frozen 10B scientific tables: **PASS**.

## Route A — Native Integration

The original frozen terminal manifests and their declared sibling artifacts were consumed directly.

## Route B — Manifest Re-entry

Byte-identical manifests and scientific artifacts were relocated to an independent root. Route A work, cache and Nextflow home were removed before Route B execution.

## Manifest Validation

Schema, semantic, filesystem, checksum, reference and portability validation: **PASS**.

## Isolation / Portability

`ISOLATED_REENTRY = PASS`. No original workdir, cache, hidden session state or absolute machine-specific artifact binding was available to Route B.

## Entity Equivalence

Route A: 1000 entities; Route B: 1000; A-only: 0; B-only: 0; duplicates: 0.

## Schema Equivalence

All 16 compared structured tables retained identical columns, order and row counts: **PASS**.

## Missing-State Equivalence

Compared 16584 state values with 0 disagreements: **PASS**.

## Regulatory-Class Equivalence

Compared 1000 regulatory rows with 0 disagreements: **PASS**.

## Statistical Equivalence

Maximum absolute numerical difference: `0`; maximum relative difference: `0`. Frozen IS8–IS10 tolerances were respected: **PASS**.

## Candidate Score Equivalence

Maximum score difference: `0.0`; exact rank identity: `YES`; top-10/25/50/100 identity: `1.0/1.0/1.0/1.0`.

## Provenance Comparison

Scientific terminal-manifest fields and source lineage: **PASS**. Runtime-only differences: `NONE`.

## Byte-Level Comparison

All deterministic scientific TSVs required by the frozen protocol were SHA-256 identical: **PASS**. HTML and volatile runtime metadata were not release-gated by byte identity.

## Performance

Route A wall time: `82.844` s; Route B wall time: `83.318` s. Performance is descriptive only.

## IR Acceptance Criteria

| Gate | Status |
|---|---|
| IR1 | PASS |
| IR2 | PASS |
| IR3 | PASS |
| IR4 | PASS |

## Validation

The complete suite executed 190 tests with 185 passes, 5 expected skips and no failures. JSON, TSV, links, manifests, checksums, script syntax, heavy-file and Git-hygiene checks passed.

## Limitations

This benchmark uses frozen synthetic integration-level evidence and Integration API schema version 1.0. It validates the public manifest contracts and their current scientific outputs, not future schema versions. Runtime metadata and final HTML are compared semantically where byte identity is inappropriate.

## Final Classification

```text
TECHNICAL_EXECUTION = PASS
MANIFEST_VALIDATION = PASS
REENTRY_ISOLATION = PASS
ENTITY_EQUIVALENCE = PASS
SCHEMA_EQUIVALENCE = PASS
MISSING_STATE_EQUIVALENCE = PASS
REGULATORY_EQUIVALENCE = PASS
STATISTICAL_EQUIVALENCE = PASS
CANDIDATE_SCORE_EQUIVALENCE = PASS
PROVENANCE_EQUIVALENCE = PASS
BYTE_LEVEL_EQUIVALENCE = PASS

REENTRY_EQUIVALENCE_BENCHMARK = PASS
```

READY_FOR_NEXT_INTEGRATIVE_STAGE
