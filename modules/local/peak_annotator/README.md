# PEAK_ANNOTATOR

Initial Peak Annotation API provider (`python_interval_v1`). It implements the
explicit priority-overlap model documented in `docs/peak_annotation_api.md`
without calling the legacy R wrapper or a scheduler.

Chromosome-specific features are queried through a deterministic interval
index rather than a complete scan per peak. The implementation rationale,
complexity, scientific-equivalence evidence, Slurm measurements, and limits
are documented in `docs/peak_annotation_optimization.md`.
