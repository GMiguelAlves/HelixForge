# CONSENSUS_INTERVALS

Shared audited engine included under separate `CONSENSUS_UNION`,
`CONSENSUS_INTERSECTION`, and `CONSENSUS_SUPPORT` process aliases. BEDTools
creates atomic intervals with exact replicate support. The explicit strategy
determines only the support threshold; it is a tracked cache input.

The provider does not combine scores, summits, signal, p-values, or q-values.
Those values remain in `replicate_evidence.tsv` with their source replicate.
