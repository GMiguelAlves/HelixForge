# Operational stage reordering

```text
OPERATIONAL_STAGE_REORDERING = RECORDED

Frozen order:      10B -> 10C -> 10D -> 10E -> 10F
Operational order: 10B -> 10C -> 10E

10D_STATUS = NOT_STARTED
10D_SKIPPED_TEMPORARILY = YES
10D_CANCELLED = NO
```

The benchmark protocol numbering was not changed.

Stage 10E was executed before Stage 10D as an operational risk-reduction
decision because contract fixtures are small and inexpensive, while 10D
requires acquisition and processing of the real GSE133183 dataset.

No 10D or 10E criteria, fixtures, gates or scientific expectations were
changed by this execution-order decision.

This is an administrative execution-order record, not a scientific protocol
amendment. The authoritative negative-contract inventory remains
`datasets/negative_contract_cases.tsv`, whose frozen SHA-256 is
`ba87581f3f6d8ce5ab58a510f801ad361844e239b2cab3941ccd3692be961014`.
