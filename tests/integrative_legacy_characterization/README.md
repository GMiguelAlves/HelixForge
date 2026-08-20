# Archived Integrative scientific characterization

This directory preserves the deterministic inputs, reviewed golden products,
checksums and baseline provenance from the retired Integrative implementation.
The executable legacy source and its characterization drivers are available
only from the annotated tag `integrative-legacy-v1.0.0`.

The reduced dataset contains eight genes, two RNA contrasts, two life-cycle
stages, activating/repressive/reader ChIP marks, promoter/gene-body/distal
peaks, differential binding, optional RNA evidence and functional annotations.
Together these records exercise every current Integrative class.

Current native contract and workflow tests consume these fixtures directly.
They verify the archived checksums and compare scientific tables without
executing a second implementation. To reproduce the historical baseline, use
an isolated worktree at the retirement tag; do not mix its outputs with a
current native run.

The golden text is normalized only for line endings, absolute fixture paths and
timestamps. Scientific values are not normalized. `baseline_manifest.json`
records the source commit, commands, environment and input/output checksums.

R 4.5.1 was present when the baseline was created, but `ggplot2` was not. No R
dependency chain was installed for this characterization pass. Plot files are
specified in `docs/integrative-legacy-audit.md` and classified as
`VISUAL_NOT_REGRESSION_CRITICAL`; the Python-generated report is characterized
without figures.
