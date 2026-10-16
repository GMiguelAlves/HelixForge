# BOWTIE2_INDEX_VALIDATE

Reuses six `.bt2` or `.bt2l` shards after validating the FASTA checksum,
optional genome identity, basename, per-file checksums, portable bundle digest,
build arguments (tokenized without changing their order) and exact Bowtie2
build/runtime version. A supplied invalid bundle fails; it never triggers a
fallback build. The supplied directory is not changed or copied into a shared
publication location. The output is a task-local read-only-use symlink.

Uses the same pinned Bowtie2 container and Conda environment as BOWTIE2_INDEX.
Python 3.12 is explicit in that Conda environment. One CPU, 2 GB, one hour,
deep cache, no retries. All scheduling belongs to Nextflow.

The manifest must come from the enhanced BOWTIE2_INDEX (schema 1.2).
Historical schema 1.1 and stub manifests do not provide enough provenance and
are deliberately rejected. There is no automatic conversion that invents
missing build information. Stub execution declares `stub`, not validation.

See [tests](tests/README.md) and the
[Alignment API](../../../docs/api/alignment_api.md).
