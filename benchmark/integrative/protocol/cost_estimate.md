# Cost and resource estimate

No resource was consumed during this design freeze. Estimates below are
planning bounds, not measured performance.

| Arm | Input scale | Expected Slurm jobs | Concurrent cap | Scratch estimate | Wall-time planning bound |
|---|---|---:|---:|---:|---:|
| Synthetic truth | 1,000 genes, compact TSV/JSON | 10–20 | 5 | < 5 GB | < 2 h |
| Re-entry | same synthetic artifacts, relocated | 10–20 | 5 | < 10 GB | < 2 h |
| Negative contracts | small invalid fixtures | 1–5 | 2 | < 1 GB | < 30 min |
| Real GSE133183 upstream production | 16 selected libraries | 40–90 | at most 10 when nodes are free | 100–200 GB | 1–3 days on shared infrastructure |
| Real integration only | compact terminal artifacts | 10–25 | 5 | < 20 GB | < 4 h |

The accession-level preflight on Slurm job `16456` replaced the provisional
estimate. The 16 selected runs contain 32 paired ENA FASTQs totaling 228.694
GiB and 508,495,000,800 deposited bases. A deliberately conservative
all-at-once envelope is 5,484.848 GiB, including an estimated 1,183.932 GiB of
uncompressed FASTQ representation, references/indexes, results, workflow work
and a 25% margin. The preflight observed 7,199.665 GiB free in project scratch.

Execution will be checkpointed by modality and will not retain simultaneous
full RNA-seq and ChIP-seq work trees. This limits the practical high-water mark
while preserving the official FASTQs until both upstream terminal manifests
have been audited. The benchmark must use the established server
policy: compute only through Slurm, conservative queue occupancy, heavy data in
the user's project scratch, compact audit evidence in a named home archive and
removal only of verified benchmark-owned temporary/intermediate data.

If an image or runtime requires a cascading dependency installation, execution
stops as `RESOURCE_BLOCKED`; the benchmark does not install a large toolchain
merely to make a test pass.
