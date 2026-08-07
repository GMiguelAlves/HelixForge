# STAR_IMPORT

Implements the direct gene-count provider of Import API 1.0 using the same
algorithm as `import_star_counts.py`: configured column selection, `N_*`
filtering, gene-ID normalization, outer sample union, integer counts, and CPM.
The process consumes manifest-backed sources and does not reconstruct STAR
paths. Length and SummarizedExperiment roles are explicitly unavailable.
