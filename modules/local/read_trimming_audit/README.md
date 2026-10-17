# READ_TRIMMING_AUDIT

One streaming audit process, called before and after optional read trimming.
Validates four-line FASTQ structure, sequence/quality lengths, gzip integrity,
SE/PE cardinality, PE record counts, mate ordering and synchronized read IDs.
Empty outputs are rejected before alignment. It records file SHA-256, read and
base counts, explicit policy and versions without changing any FASTQ.

Output auditing also checks identity/control preservation against the raw
manifest, records retained-read fraction and requires Trim Galore/Cutadapt
versions. It does not implement or replace trimming algorithms.

The Python source is embedded in the task command, so no accidental host-code
mount is required and source changes invalidate its deep cache. Uses the pinned
import-Python runtime (with Nextflow metrics support) or Python 3.12 Conda.
Resources: one CPU, 2 GB, four hours; terminate on failure, no retries.
Docker uses `read_trimming_audit_container`; Apptainer can consume that OCI image
through the existing container conversion profile. No runtime is installed by
the module. Stub output explicitly says validation was not performed.

See [tests](tests/README.md).
