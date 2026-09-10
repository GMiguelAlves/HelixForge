# GSE133183 real biological integration

**Classification:** `PASS_WITH_LIMITATIONS`

## Frozen criteria

| Criterion | Type | Status | Metric |
|---|---|---|---|
| IB1 | RELEASE_GATE | PASS | contract/reference compatibility |
| IB2 | RELEASE_GATE | PASS | technical completion |
| IB3 | SANITY_CHECK | PASS | entity/state accounting |
| IB4 | EXPECTED_RANGE | FAIL | H3K27me3 depletion direction |
| IB5 | EXPECTED_RANGE | NOT_EVALUABLE | directional enrichment |
| IB6 | DESCRIPTIVE | PASS | preregistered examples |
| IB7 | DESCRIPTIVE | PASS | candidate review inventories |
| IB8 | DESCRIPTIVE | PASS | functional analysis provenance |

## Principal observations

- Canonical genes: 78,517.
- Significant H3K27me3 regions: 0; decreased: 0; increased: 0.
- Significant H3K27ac regions: 14,957; decreased: 14,847; increased: 110.
- Directional Fisher tests available: 0.
- Functional-analysis status: `complete_empty` with 0 formal tests.

## Interpretation

Technical and contract gates are evaluated independently from expected biological ranges and descriptive outputs.
`NOT_EVALUABLE` does not invent evidence and is retained as a documented limitation.
