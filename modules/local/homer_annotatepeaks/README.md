# HOMER_ANNOTATEPEAKS

Runs the nf-core/chipseq 2.1.0 annotation invocation with HOMER 4.11:
`annotatePeaks.pl peaks.bed genome.fa -gid -gtf annotation.gtf -cpu N`.
The original `annotatePeaks.txt` is retained without changing annotations.
No built-in human/mouse genome or automatic database download is used.

Select `homer_4_11` with explicit mode `homer_native`. Compatibility overlap
windows and feature-priority settings do not control HOMER. Nearest-promoter
associations are not equivalent to overlap-only assignments and do not establish
regulatory causality. Some descriptive columns can be absent with custom GTFs.

The pinned Conda package metadata must be available to verify HOMER's version.
The lightweight `HOMER_ANNOTATION_ADAPTER` process separately normalizes the
output and transports consensus evidence. Python is not required in the HOMER
image. Stubs never invoke HOMER or claim scientific validation.
