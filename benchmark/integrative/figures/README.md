# Figures

`baseline/` contains deterministic SVG figures derived exclusively from the
frozen, versioned benchmark TSV and JSON summaries. They do not recalculate
scientific results and are referenced by the final baseline report.

Regenerate them with:

```bash
python benchmark/integrative/scripts/render_benchmark_figures.py
```
