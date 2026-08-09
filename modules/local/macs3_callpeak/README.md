# MACS3_CALLPEAK

First provider for Peak Calling API v1. The module executes a validated request without inferring peak type or organism. Paired libraries use `BAMPE`; single-end libraries use `BAM`. Upstream duplicate handling remains authoritative, so the native default is the explicit `--keep-dup all` policy.

MACS3 is pinned to 3.0.4, using the Bioconda build corresponding to Python 3.12.
