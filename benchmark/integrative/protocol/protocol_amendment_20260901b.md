# Protocol amendment — differential-binding carriers for shared regions

## Original rule

The positive synthetic fixture must include one-region→multiple-gene
associations while preserving the frozen gene-level differential-binding
states and effects.

## Problem

The first run A attempt stopped in `CHIPSEQ_EVIDENCE_PROVIDER` before any
integrative output was produced. Evidence Model 1.1 defines a unique
differential-binding observation by region, contrast and source artifact; the
gene identifier is deliberately not part of that identity. Reusing the shared
region as the differential-binding carrier for each associated gene therefore
created 16 duplicate scientific observations.

## Discovery state

- Date: 2026-09-01
- HelixForge integrative outputs observed: **NO**
- Failure observed: provider contract validation only
- Truth, classes, effects, thresholds or acceptance results observed: **NO**

## Correction

Shared regions remain unchanged in peak→gene annotations and continue to map
to every frozen candidate gene. For each affected gene, its already frozen
differential-binding observation is carried by a deterministic, unique, known
region that is not added to peak→gene evidence. This satisfies the released
observation-identity contract without changing gene-level peak aggregation.

## Preserved parameters

All 1,000 truth rows, class counts, marks, contexts, effects, missing states,
shared-region associations, aggregation expectations, Candidate Score
expectations, statistical tests, thresholds and `IS*` gates remain unchanged.

```text
PROTOCOL_IMPLEMENTATION_CONFLICT = RESOLVED_PRE_INTEGRATION_OUTPUT
AMENDMENT_BIAS_RISK = LOW
```
