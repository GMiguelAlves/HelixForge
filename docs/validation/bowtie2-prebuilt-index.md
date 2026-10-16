# Reusable Bowtie2 index validation

Issue: [#101](https://github.com/GMiguelAlves/HelixForge/issues/101).

## Scope

The Reference API now distinguishes index construction from validation of an
explicit supplied bundle. The default scientific alignment command is unchanged.
The build path additionally exports portable provenance. Its publication filter
was corrected to publish the declared index directory to the configured target;
the previous child-file filter could leave that target empty. Alignment checksum
collection follows staged directory links so it hashes the actual shards.

This is not a new full ChIP-seq study or a recertification of all workflow stages.
DB composition and trimming remain separate issues.

## Checks performed on October 16, 2026

| Check | Result |
| --- | --- |
| Focused Python tests: Bowtie2 bundles, existing Salmon reuse, ChIP metadata/full coordinator | 28 passed |
| Nextflow lint: changed modules, Reference dispatcher, ChIP coordinator and alignment fixture | No errors; final module lint also had no warnings |
| Nextflow 25.10.7 build-path stub | PASS |
| Nextflow 25.10.7 reuse-path stub | PASS; validation rather than index construction |
| Top-level ChIP alignment stub with prebuilt parameters | PASS; validation, three alignments, FastQC/MultiQC |
| Portable publication stub | PASS; all six shards published |
| Broad Python discovery | 336 executed: 323 passed, 12 skipped, one environment-related failure |

The broad-suite failure was
`tests.integration_api.test_contracts.SchemaExamplesTest.test_examples_pass_json_schema`:
the available WSL Python had jsonschema 4.10.3 and no `referencing`; the contract
requires jsonschema >=4.23. No system dependency was changed to hide the failure.
The existing CI installs jsonschema 4.23.0 and its dependencies. Its result must
be checked separately; local broad-suite success is not claimed.

## Real tools in Slurm

Eight cases passed in compute allocation 28787 with the official Nextflow
25.10.7 launcher and existing Conda tools (Bowtie2 2.5.5, samtools 1.23.1).
Nextflow used its local executor inside that allocation; this tests real provider
execution on compute, not a new certification of dynamic Slurm task submission.

| Case | Observed outcome |
| --- | --- |
| Build from the reduced synthetic reference | Complete six-shard bundle and schema 1.2 manifest |
| Independent execution with supplied bundle, no resume | Validation + alignment; no index build |
| Identical resume | All eligible tasks cached |
| Change one FASTQ and resume | Validation cached; alignment rerun; no index build |
| Change expected index parameters | Rejected before alignment, no fallback build |
| Supply a mismatching build version | Rejected before alignment, no fallback build |
| Supply another reference FASTA | Rejected before alignment, no fallback build |
| Remove a shard from a separate bundle copy | Rejected before alignment, no fallback build |

The original index remained unchanged. Sorted SAM records from the built-index
and reused-index BAMs were nonempty and identical. This is a semantic BAM-record
comparison, not a claim of byte-identical compressed BAM headers/files.

An earlier attempt stopped in the existing Conda Perl before validation; a
private per-validation alias selected system Perl for the original Bowtie2
wrapper. No installed environment or shared system file was changed. Two
subsequent attempts exposed the publication-filter issue; their failed evidence
was retained, followed by a passing local publication stub and final real run.

The cluster run used Bowtie2 2.5.5, so it does not certify the pinned 2.5.4 OCI
image. The dedicated `Reusable Bowtie2 index` CI workflow runs the same real-tool
suite using a candidate built from the joint alignment Dockerfile, which fixes
Bowtie2 2.5.4 and samtools 1.20. That CI evidence is separate.

The first PR CI exposed two additional integration defects: this document was
missing from the documentation index, and the existing published alignment
digest lacked `ps`, required by Nextflow metrics. The index link was added and
the alignment Dockerfile now installs `procps`. Container certification also
checks `ps` explicitly. Metrics/trace assertions are not disabled to bypass the
failure. The PR tests the rebuilt candidate; the old published digest is not
claimed to have changed, and publication/pinning of the rebuilt image belongs
to the release process.

Private logs, fixtures and outputs were archived with a Portuguese README in
user-controlled home storage, ZIP integrity and SHA-256 were checked, and only
the new validation scratch directory was removed. No private paths or raw logs
are included here.

## RNA-seq verification

The existing production Salmon branch already bypasses `SALMON_INDEX` when
`salmon_prebuilt_index` and its manifest are supplied, and instead runs
`SALMON_INDEX_VALIDATE`. Its three direct unit tests passed unchanged. This
work did not change RNA-seq science or claim a new full RNA-seq Slurm execution.
Validation can reread/checksum an existing index without reconstructing it.

See [the usage contract](../api/alignment_api.md#reusing-a-bowtie2-index).
