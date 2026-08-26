# Stage 9B.2 protocol/implementation audit

Audit start: 2026-08-26

| ID | Classification | Observation | Resolution before execution |
|---|---|---|---|
| 9B2-D01 | `BENCHMARK_FINDING` | The Stage 9A protocol defines `public_100` as a deterministic 5,000,000-pair cap per sample, while the Stage 9B.2 instruction explicitly requires all reads from the eight selected libraries and forbids subsampling. | Treat Stage 9B.2 as the full-data biological benchmark. Do not modify or execute `subsampling_plan.tsv`; record the actual paired reads per run and reserve depth-series work for a later decision. |
| 9B2-D02 | `BENCHMARK_FINDING` | GEO describes 75 bp paired-end library sequencing, while the official ENA run descriptors contain a 126 bp spot composed of two 63 bp application reads. | Preserve the study-level 75 bp description as library provenance, but record and process the deposited 63+63 bp paired FASTQs. This does not conflict with `airway_samples.tsv`, which freezes accessions, paired URLs, sizes and MD5 values but has no read-length field. |
| 9B2-D03 | `BENCHMARK_FINDING` | Four selected runs expose an additional orphan/unpaired ENA FASTQ. `prefetch` plus SRA conversion would materialize data outside the frozen paired-input contract and require large uncompressed temporary storage. | Download the exact official ENA `_1.fastq.gz` and `_2.fastq.gz` exports frozen in `airway_samples.tsv` with resumable `curl`, official MD5, local SHA-256, gzip and paired-record validation. Exclude the additional orphan files and record their presence. |
| 9B2-D04 | `DOCUMENTATION_CORRECTION` | `reference_sources.tsv` named the release checksum file `CHECKSUMS`, but the official GENCODE release 49 directory publishes it as `MD5SUMS`; the former URL returns HTTP 404. | Use the official release `MD5SUMS`, freeze the three upstream MD5 values in the generated reference manifest, and retain the failed metadata-only Slurm attempt in the audit log. No scientific input changes. |

No discrepancy changes HelixForge scientific code, the RC import policy, the
paired donor design or the Dexamethasone-versus-Untreated contrast.
