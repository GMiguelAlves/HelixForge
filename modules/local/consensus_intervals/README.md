# CONSENSUS_INTERVALS

Shared audited engine included under separate `CONSENSUS_UNION`,
`CONSENSUS_INTERSECTION`, and `CONSENSUS_SUPPORT` process aliases. BEDTools
creates atomic intervals with exact replicate support. The explicit strategy
determines only the support threshold; it is a tracked cache input.

The provider does not combine scores, summits, signal, p-values, or q-values.
Those values remain in `replicate_evidence.tsv` with their source replicate.

For broad peaks, these outputs are exact per-base support cores, not full
biological domains. Consult the [representation guide](../../../docs/guides/broad-peak-consensus.md)
for retained-coverage review and the distinction between cores, candidate
regions and gene associations. Changing this interpretation does not change
the current provider's interval output.
