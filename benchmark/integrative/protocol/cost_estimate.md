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

The selected GEO processed archive is 145.1 MB. Raw selected FASTQ transfer is
provisionally estimated at 20–40 GB and must be replaced with an accession-level
ENA/SRA audit before download. The benchmark must use the established server
policy: compute only through Slurm, conservative queue occupancy, heavy data in
the user's project scratch, compact audit evidence in a named home archive and
removal only of verified benchmark-owned temporary/intermediate data.

If an image or runtime requires a cascading dependency installation, execution
stops as `RESOURCE_BLOCKED`; the benchmark does not install a large toolchain
merely to make a test pass.
