# Integrative legacy characterization

This fixture freezes the scientific behavior of the remaining Integrative
legacy engine before native migration. It does not invoke Nextflow and does not
modify `integrative_core.py`.

The reduced dataset contains eight genes, two RNA contrasts, two life-cycle
stages, activating/repressive/reader ChIP marks, promoter/gene-body/distal
peaks, differential binding, optional RNA evidence and functional annotations.
Together these records exercise every current Integrative class.

Run the characterization test:

```bash
python tests/integrative_legacy_characterization/test_characterization.py
```

Regenerate the baseline only after reviewing a deliberate legacy-source or
fixture change:

```bash
python tests/integrative_legacy_characterization/generate_golden.py
```

The golden text is normalized only for line endings, absolute fixture paths and
timestamps. Scientific values are not normalized. `baseline_manifest.json`
records the source commit, commands, environment and input/output checksums.

R 4.5.1 was present when the baseline was created, but `ggplot2` was not. No R
dependency chain was installed for this characterization pass. Plot files are
specified in `docs/integrative-legacy-audit.md` and classified as
`VISUAL_NOT_REGRESSION_CRITICAL`; the Python-generated report is characterized
without figures.

