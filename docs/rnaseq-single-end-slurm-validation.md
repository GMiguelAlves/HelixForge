# RNA-seq single-end: reduced Slurm validation

Status: **PASS for the tested synthetic cases**. This is an operational and
scientific smoke validation of the native single-end Salmon path, not a
biological benchmark or a claim about all library preparations.

## Scope and environment

- Nextflow 25.10.7 through its official launcher, Java 21, Slurm `general`.
- Site Conda environments; no Docker or Apptainer claim is made here.
- Maximum of eight concurrent Nextflow tasks after checking cluster capacity.
- Four biological samples, 30 synthetic genes, a synthetic transcriptome,
  `fragment_length_mean=200`, `fragment_length_sd=80`, one DESeq2 contrast.
- Full path: R1 FASTQ → FastQC → Trim Galore → merge → MultiQC → Salmon index
  and quantification → tximport → DESeq2 → Gene Report → terminal manifest.
- The fixture generator and validators ran in Slurm compute-node jobs. The
  management node only launched and monitored Nextflow and submitted helpers.

| Case | Technical runs | Fresh tasks | Identical resume | Scientific result |
| --- | ---: | ---: | --- | --- |
| One run per sample | 4 | 47 completed | 46 cached; terminal manifest completed | PASS |
| One sample split across two runs | 5 | 50 completed | 49 cached; terminal manifest completed | PASS |

Both cases produced four Salmon quantifications, the expected count,
abundance and length matrices, a DESeq2 contrast, and a Gene Report with
12 non-empty plots. The imported count matrix retained all 30 genes, all four
samples, count correlation approximately 1.0 and total-count ratio 1.0
against the synthetic truth. Salmon mapped at least 98% of processed reads in
each sample. The technical-run case verified that the merged gzip file was
the ordered byte-for-byte concatenation of the two trimmed run files and that
read totals were preserved. FastQC produced five raw and five post-trim
archives, but four post-merge archives; MultiQC was present. Salmon command
logs contained `-r --fldMean 200 --fldSD 80` and no paired-end input flags.

The repeat used the same case, work directory and Nextflow cache. The resume
guard verified cache recoverability before re-entry. Every scientific process
was `CACHED`; only the terminal run manifest was regenerated with the new
session identifier. The baseline and resume scientific validators passed.

The local single-end contract suite passed seven tests. Its fixture tests
also verify that the paired-end generator default remains unchanged. Existing
paired-end production evidence is documented separately; no paired-end
real-tool re-run was performed for this record.

## Reproduction and audit

Use `tests/slurm/run_rnaseq_single_end_real.sh` with an **existing** absolute
`VALIDATION_BASE`, a fresh child case directory, site `CONDA_BASE`, the official
Nextflow 25.10.7 launcher as `NEXTFLOW_BIN`, and the Slurm partition. Select
`baseline` or `technical` as the third argument. The driver refuses to
overwrite an existing case and does not remove files automatically.

Case-local evidence includes `fixture_manifest.json`, scientific and
single-end validation JSON, baseline/resume traces, Nextflow logs, helper
job logs, the resume receipt, and the terminal RNA-seq manifest. No private
server path or raw synthetic FASTQ is committed to this repository.

The initial attempt stopped **before scientific execution** because Slurm
spooled the helper script and a relative source-root lookup pointed into the
spool directory. The helper now receives the source root explicitly. In the
first completed case, a validator parsed the colon inside the terminal
manifest's run tag as part of its process name; the parser was corrected and
the existing completed trace was revalidated in a compute-node job. These
were harness defects, not changes to the scientific pipeline.

## Remaining scope

This validates the reduced synthetic single-end route on this Slurm site.
Biological single-end data, other fragment priors, OCI/Apptainer execution,
and selective cache invalidation were not tested here. The paired-end path
remains the certified production baseline until a real single-end project is
reviewed separately.
