# SALMON_INDEX_VALIDATE

Validates a prebuilt Salmon index and emits it through the Quantification API
without invoking `salmon index`. The supplied manifest must identify the exact
transcriptome, Salmon version, index version, k-mer size, and composite index
checksum.

The composite checksum is compatible with `SALMON_INDEX`: each index file is
hashed in sorted relative-path order under a declared directory prefix, and
those checksum lines are hashed again. `composite_sha256_prefix` records the
prefix used by an externally audited index; native `SALMON_INDEX` manifests
use `salmon_index`.

This module is read-only with respect to the supplied index. A mismatch fails
before any quantification process can start.
