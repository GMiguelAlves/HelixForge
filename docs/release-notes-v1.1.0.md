# HelixForge v1.1.0

HelixForge `v1.1.0` adds a backward-compatible, native single-end RNA-seq path
for Salmon. Existing paired-end inputs and scientific defaults are unchanged.
This is a minor release because single-end support is a new workflow feature;
the public scientific model versions remain unchanged.

## Single-end scope

Single-end metadata must declare `library_layout=single`, one R1 FASTQ, and
positive `fragment_length_mean` and `fragment_length_sd` values justified by
the library preparation. The path covers FastQC, Trim Galore, ordered merge of
technical runs, MultiQC, Salmon `-r` quantification, tximport, DESeq2, Gene
Report and the terminal RNA-seq manifest. Mixed library layouts within one
dataset and single-end STAR are rejected. The paired-end Salmon path remains
available without changing its legacy metadata requirements.

## Validation and limits

- Local Docker execution completed the reduced four-sample single-end fixture
  and an identical `-resume`; the paired-end Salmon stub regression passed.
- On Slurm with Nextflow 25.10.7 and Java 21, two real-tool synthetic cases
  completed: four single-end biological samples with one technical run each,
  and one sample split across two ordered technical runs. The latter verified
  lossless FASTQ concatenation before Salmon.
- Both cases produced four quantifications, 30-gene Import matrices, one
  DESeq2 contrast, Gene Report plots and a terminal manifest. In identical
  resumes, every scientific task was cached; the terminal manifest was
  regenerated for the new session.
- This certifies the tested reduced single-end workflow behavior. It does
  **not** establish biological validity for a particular single-end study,
  other fragment-length priors, or OCI/Apptainer execution on the Slurm site.
  The paired-end route remains the established biological production baseline.

The detailed evidence and reproduction procedure are in the
[single-end Slurm validation record](rnaseq-single-end-slurm-validation.md)
and [single-end guide](rnaseq-single-end.md).

## Other changes

The RNA-seq Gene Report has a reorganized presentation and export layout,
without changing its scientific calculations. Validation harnesses now use the
official Nextflow launcher for reliable task-cache persistence. No change was
made to STAR's experimental status, ChIP-seq, Integrative, or the frozen v1
benchmark classifications.
