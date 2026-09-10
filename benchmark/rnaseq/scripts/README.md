# RNA-seq benchmark utilities

This directory retains only portable builders, validators, evaluators and
figure generators needed to inspect or reproduce the frozen Polyester and
GSE52778 evidence.

| Directory | Retained responsibility |
|---|---|
| `common/` | reference construction and independent-result comparisons |
| `synthetic/` | fixture/truth construction, validation, evaluation and figures |
| `gse52778/` | metadata/input validation, independent analysis, QC, concordance and figures |

Cluster-specific Slurm launchers, runtime installers, download drivers and
shell wrappers were removed after the baseline freeze. They encoded one
institutional filesystem/runtime session and are not part of the reusable
benchmark API. Their exact historical versions remain available at the
annotated tag `rnaseq-benchmark-v1.0.0-rc.1`.

Scientific inputs, criteria, metrics and frozen outputs were not removed. Raw
reads, references, environments and Nextflow work directories remain outside
Git and are represented by manifests and checksums.
