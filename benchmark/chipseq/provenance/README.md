# ChIP-seq benchmark provenance contract

Every synthetic or real arm produces one top-level benchmark manifest that
binds source data, scientific design, software, execution and results. It
supplements HelixForge module/run manifests; it does not replace them.

Required properties are defined by
[`chipseq_benchmark_manifest.schema.json`](chipseq_benchmark_manifest.schema.json).
An illustrative, non-executed record is in
[`benchmark_manifest.example.json`](benchmark_manifest.example.json).

## Integrity rules

- `benchmark_target.commit` must equal the reviewed target commit.
- Every input, reference, truth and released output has size and SHA-256.
- Public sources additionally record provider accession and published MD5.
- Simulator name, version, commit, seeds and parameters are mandatory for
  synthetic arms.
- Tool versions and immutable container references are mandatory.
- Slurm job IDs, Nextflow session ID, executor, host class, Java and Nextflow
  versions are recorded after execution.
- The exact frozen design JSON and MACS3 configuration are checksum-linked.
- Result classification uses only the frozen metrics and criteria.
- A manifest marked `complete` cannot contain missing required evidence.

The run archive stores a checksum list covering the manifest itself and every
retained evidence file. Credentials, SSH paths, access tokens and unrelated
cluster details must never enter the manifest.
