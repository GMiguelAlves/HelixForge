# RNA-seq single-end extension

Status: implemented for the native Salmon path; **not yet operationally certified
on Slurm**. The paired-end Salmon route remains the certified production baseline.

## Metadata contract

For each single-end technical run, set `library_layout=single`, provide
`fastq_1`, and leave `fastq_2` empty. Set `fragment_length_mean` and
`fragment_length_sd` to positive integers based on the library preparation.
There is no implicit fragment-length default. All technical runs belonging to
one biological sample must use the same layout and fragment values. A dataset
must use one layout consistently: paired-end and single-end samples may coexist
in the platform as separate datasets, but cannot be mixed inside one dataset.

Existing paired-end sheets without `library_layout` continue to resolve as
`paired`. A paired record requires R1 and R2 and must not set the single-end
fragment fields. A single-end record with R2 is rejected.

| Field | Single-end | Paired-end |
| --- | --- | --- |
| `library_layout` | `single`, required | `paired` or omitted for legacy sheets |
| `fastq_1` | required | required |
| `fastq_2` | empty | required |
| `fragment_length_mean` | positive integer, required | empty |
| `fragment_length_sd` | positive integer, required | empty |

Salmon receives `-r`, `--fldMean`, and `--fldSD` for single-end data. The
values and layout appear in its execution metadata and quantification manifest,
then in the terminal RNA-seq manifest sample record. The normalized sample
table retains the same fields through Import and DESeq2.

Single-end STAR alignment is rejected. The supported extension is
`FASTQ → FastQC → Trim Galore → merge → Salmon → tximport → DESeq2`.
The fragment prior affects Salmon effective lengths and abundance estimates;
users should choose values appropriate for their preparation.
The source of the fragment-length prior (library protocol, publication or
empirical estimate) must be recorded in the project documentation alongside
the values retained by HelixForge provenance.

## Validation

The single-end stub can be exercised with `--rnaseq_stub_layout single` and
`-stub-run`; this switch is only for test fixtures. The reduced real fixture
can be generated with
`tests/slurm/generate_rnaseq_fixture.py --layout single`.
It is a synthetic, four-sample dataset (`control_1`, `control_2`,
`treated_1`, `treated_2`) derived from
`tests/fixtures/native_de/counts_matrix.tsv`. The generator writes one R1
FASTQ per sample, a synthetic transcriptome and annotation, metadata with
`fragment_length_mean=200` and `fragment_length_sd=80`, and a DESeq2 analysis
specification with condition and batch.

This fixture completed the full single-end path locally with Nextflow 25.10.7
and Docker: QC, trimming, merge, Salmon, tximport, DESeq2, and the terminal
RNA-seq manifest. The manifest contained all four single-end samples and nine
integration artifacts. An identical `-resume` run cached all scientific tasks.
The paired-end Salmon stub regression also passed. This Docker validation is
local evidence; Slurm certification remains pending. The complete single-end
stub is also part of the release CI smoke, so metadata, QC, trimming, merge,
Salmon, Import, DESeq2 and the terminal manifest are checked together on each
release candidate.

Production certification additionally requires a completed Slurm run, an
identical `-resume` with cached tasks, and paired-end regression evidence.
The site harness is `tests/slurm/run_rnaseq_single_end_real.sh`; pass a new
persistent case directory and partition, with `CONDA_BASE` and
`NEXTFLOW_BIN` set for the site.
