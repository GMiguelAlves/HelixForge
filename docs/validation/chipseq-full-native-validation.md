# Native ChIP-seq full-workflow validation

The native coordinator composes QC, optional trimming, Bowtie2, BAM
processing, MACS3, Peak QC, consensus or optional IDR, optional Differential
Binding, annotation, tracks, reporting and the terminal assay manifest.
There is no legacy coordinator or fallback.

## Functional coverage

- Complete reduced real-tool paths, including a separate optional-IDR case.
- `full` with DB disabled and enabled, retaining compatible upstream cache.
- Accepted consensus/IDR continuation into annotation, tracks and reporting.
- Report-only re-entry without scientific producers.
- Early rejection of incompatible continuation inputs.
- Shared read trimming, pre/post FastQC and terminal artifacts.

The consolidated trimmed, DB-enabled fixture completed 132 tasks. Its
identical resume reused all 131 non-terminal tasks with unchanged hashes;
only the terminal manifest refreshed its generated execution name.

| Controlled change | Required behavior verified |
|---|---|
| One FASTQ mate | Affected sample QC/trimming/alignment repeated; other sample branches and index retained |
| Reference sequence | Index and alignments rebuilt; read QC/trimming retained |
| Contrast direction | Count/model products retained; contrast and aggregation repeated |
| Trimming quality | Trimming repeated; raw FastQC and reference index retained |
| Alignment task script | Alignments repeated; QC/trimming and index retained |

Descendants are cached by their actual inputs. An upstream rerun does not
force a descendant whose inputs remain unchanged to run again. See
[cache and invalidation](../guides/nextflow.md#cache-and-invalidation).

## Reproduction and scope

The versioned composition fixture is documented in
[`tests/native_chipseq_composition/`](../../tests/native_chipseq_composition/README.md).
It exercises real tools, stubs, DB composition and continuation; the controlled
mutation matrix is a separate release validation, not a new biological or
performance benchmark. The complete native paths have Slurm coverage;
the v1.2.0 mutation fixture used the local executor inside a Slurm allocation
with existing Conda toolchains. It does not additionally certify per-task
Slurm submission or automatic Conda environment creation.

OCI provider certification is separate from host-tool execution and does not
establish full Apptainer certification. See the
[container scope](chipseq-container-certification.md). Scientific acceptance
remains bounded by the frozen
[ChIP-seq benchmark](../../benchmark/chipseq/reports/chipseq_benchmark_final_report.md)
and its `PASS_WITH_LIMITATIONS` classification.
