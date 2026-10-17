# CHIPSEQ_CONTINUATION_CONTEXT

Validates a declared input inventory before any post-consensus provider starts.
Requires metadata/reference/annotation/peak/BAM/BAI checksums, compatible
identities and explicit replicate/control associations. Never scans results,
merges replicates, fits DB, or reconstructs missing upstream artifacts.
All paths are staged inputs indexed by their declared role, not inferred order.
The normalized plan retains original producer IDs and DB `not_requested`.

One CPU, 1 GB, two hours (large BAM checksum reads), deep cache, terminate on
failure. Uses the existing metadata container or declared Conda environment.
Stub skips checksum certification and explicitly reports `stub` status.
