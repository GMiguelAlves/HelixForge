# SALMON_INDEX_VALIDATE

Validates a prebuilt Salmon index and emits it through the Quantification API
without invoking `salmon index`. The supplied manifest must identify the exact
transcriptome, Salmon version, index version, k-mer size, and composite index
checksum.

The composite checksum is compatible with `SALMON_INDEX`: each index file is
hashed in sorted relative-path order under the canonical `salmon_index/`
prefix, and those checksum lines are hashed again.

This module is read-only with respect to the supplied index. A mismatch fails
before any quantification process can start.
