# Provenance contract

`scientific_target.json` freezes the exact code and upstream baseline lineage.
Future execution must add input manifests, reference checksums, policy
checksums, container digests, Nextflow/Java versions, Slurm job IDs and compact
trace summaries. Large work products remain outside Git and are represented by
checksums plus a Portuguese README in each retained audit archive.

All four benchmark arms have completed. The
[`integrative_benchmark_freeze_manifest.json`](integrative_benchmark_freeze_manifest.json)
links their reviewed reports, exact commits, compact evidence and external
audit-archive identities. The archives themselves remain in private maintainer
storage and are not committed because operational logs may contain
cluster-specific paths.
