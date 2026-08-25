# Expected Slurm cost and complexity

These are planning ranges, not measured benchmark results. Stage 9B replaces
them with observed `trace` and `sacct` values. Wall time depends on queue state,
NFS load and node hardware.

| Activity | Parallel jobs | Planning wall time | Memory/job | Scratch footprint |
|---|---:|---:|---:|---:|
| Reference download/preparation/index | 1–2 | 20–120 min | 8–32 GiB | 20–60 GiB |
| Synthetic truth/read generation | 1–3 | 30–180 min | 4–16 GiB | 20–50 GiB |
| Synthetic HelixForge run | up to 5 | 1–4 h | module-defined | 30–100 GiB |
| Public FASTQ download/check | up to 5 | 1–6 h | 1–2 GiB | about 22 GiB source |
| Public 5 M-pair base subset | up to 5 | 30–120 min | 2–4 GiB | 8–20 GiB |
| One public HelixForge depth | up to 5 | 1–5 h | module-defined | 40–120 GiB |
| Three lower-depth robustness runs | up to 5 | 3–12 h total | module-defined | 60–180 GiB if retained |
| Independent reference per case | up to 5 | 1–5 h | 8–32 GiB | 30–100 GiB |
| Metrics/report/provenance | 1–2 | 15–90 min | 4–16 GiB | below 10 GiB |

Operational assumptions:

- normal concurrency is at most five submitted/running jobs owned by the user;
- ten is permitted only after `sinfo`, `squeue` and `scontrol show node` prove
  that one execution node is completely free immediately before submission;
- the head node is limited to inspection, Git, submission and lightweight file
  metadata checks; scientific and bulk I/O tasks are scheduled;
- stages execute serially where outputs can be deleted after checksumming;
- expected peak scratch use is 200–350 GiB with staged cleanup;
- the audit bundle copied to the user's home should remain below 2 GiB and
  contain manifests, logs, metrics, checksums and reports, not raw FASTQs/work.
