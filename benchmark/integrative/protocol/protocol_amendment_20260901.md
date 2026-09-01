# Protocol amendment — RNA missing-observation carrier

## Original rule

The frozen truth assigns 40 background entities an explicit RNA `MISSING`
observation and labels its intended carrier as `RNA_EXPRESSION_MEASUREMENT`.

## Problem

The released RNA Evidence Provider does not emit an expression observation for
an empty/NA abundance cell. It skips that cell, so `MISSING` cannot be
represented in `master_evidence_long.tsv` through an abundance matrix. The
same Evidence Model explicitly preserves an empty differential-expression
effect as an observation with `measurement_state=MISSING`.

## Discovery time and observed results

Discovered during fixture preflight on 2026-09-01, before fixture execution and
before any HelixForge synthetic integration output was produced or inspected.

## Correction

For exactly the same 40 frozen entities, encode the explicit RNA missing value
in the differential-expression effect field instead of the abundance cell.
`rna_observation_state=MISSING` remains the authoritative truth expectation.
The original `explicit_missing_observation` text is retained in the immutable
truth table as provenance of the initial carrier choice.

## Bias risk

`LOW`. The correction changes only which supported RNA observation carries the
same missing state. It cannot improve a regulatory class because these genes
remain frozen background/no-peak entities and the missing effect is not
significant.

## Preserved parameters

- truth table and all truth checksums;
- 1,000 entities and class balance;
- 40 RNA `MISSING` cases;
- regulatory expectations and Candidate Score priorities;
- effect tiers and significance thresholds;
- reference, annotation, mark, context and contrast identities;
- all `IS*` thresholds.

```text
PROTOCOL_IMPLEMENTATION_CONFLICT = RESOLVED_PRE_EXECUTION
SCIENTIFIC_RESULTS_OBSERVED = NO
AMENDMENT_BIAS_RISK = LOW
```
