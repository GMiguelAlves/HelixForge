# Reusable Bowtie2 index validation

The Reference API separates construction from validation of an explicit index
bundle. Reuse is independent of the original Nextflow cache/work directory;
a mismatching bundle is rejected rather than silently rebuilt. See the
[usage contract](../api/alignment_api.md#reusing-a-bowtie2-index).

## Covered behavior

| Case | Required result |
|---|---|
| Build from the reduced reference | Six shards and schema 1.2 provenance manifest |
| Independent execution with supplied bundle | Validation and alignment, no index construction |
| Identical resume | Eligible tasks cached |
| Change one FASTQ | Index validation cached; affected alignment rerun |
| Change expected build parameters | Rejection before alignment, no fallback |
| Mismatching Bowtie2 version | Rejection before alignment, no fallback |
| Mismatching reference FASTA | Rejection before alignment, no fallback |
| Missing/corrupt shard | Rejection before alignment, no fallback |

The fixture also checks that supplied index files remain unchanged and that
the built-index/reused-index BAMs have equivalent nonempty sorted SAM records.
This is not a byte-identity claim for compressed BAMs or their headers.

## Reproduce

```bash
python3 -m unittest tests.native_bowtie2_prebuilt.test_index_bundle \
  tests.native_quantification.test_salmon_prebuilt_index -v

NEXTFLOW_BIN=/path/to/official/nextflow \
  python3 tests/native_bowtie2_prebuilt/run_functional.py \
  --docker --output /path/to/new-validation-directory
```

Without `--docker`, required Bowtie2/SAMtools/Python tools must be on `PATH`;
on HPC, run the fixture inside a compute allocation. The driver installs
nothing and refuses to overwrite its output directory. `--image` selects an
explicit candidate; the default is the release-pinned joint runtime.

## Evidence boundaries

The reduced real-tool suite passed with Bowtie2 2.5.5/SAMtools 1.23.1 in a
Slurm allocation. OCI certification separately covers Bowtie2 2.5.4/SAMtools
1.20 and includes process metrics support. These are separate environments,
not interchangeable version-certification claims. Tests include strict error
matching so unrelated failures cannot satisfy negative cases.

The workflow and index tasks preserve alignment scientific options. The
enhanced runtime includes `procps`, and the helper source participates in the
task hash without requiring an undeclared checkout mount. Full runtime
references are in the [inventory](../guides/runtime-inventory.md).

Salmon already provides the equivalent explicit index-reuse boundary through
`SALMON_INDEX_VALIDATE`. Validation may reread/checksum a supplied index;
this is not reconstruction. Neither provider infers provenance from a directory
merely existing on disk.
