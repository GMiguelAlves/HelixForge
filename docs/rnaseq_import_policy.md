# RNA-seq Import policy

Policy version: `production_v1`

The Import API is a scientific boundary. A run must declare both its library
protocol and `countsFromAbundance`; HelixForge does not infer either value from
filenames, organism, or prior runs.

## Production policy

| Library protocol | `countsFromAbundance` | Transcript IDs | Gene IDs | `ignoreTxVersion` | `ignoreAfterBar` |
|---|---|---|---|---:|---:|
| `full_length` | `lengthScaledTPM` | preserve | preserve | `false` | `false` |
| `three_prime` | `no` | preserve | preserve | `false` | `false` |

These are the only combinations accepted by `production_v1`. Full-length
libraries use length-scaled gene counts for the current matrix-based DESeq2
interface. Three-prime tagged libraries must not receive transcript-length
correction. Unmapped transcripts, normalization collisions, duplicate sample
identities, negative values, and invalid numeric values are fatal errors.

Example:

```bash
nextflow run . -profile slurm \
  --workflow rnaseq \
  --rnaseq_import_policy production_v1 \
  --rnaseq_library_protocol full_length \
  --rnaseq_counts_from_abundance lengthScaledTPM
```

## Historical compatibility

`legacy_compatibility_v1` is an explicit regression mode reproducing the old
tximport choices: `countsFromAbundance=no`, `ignoreTxVersion=true`,
`ignoreAfterBar=true`, version removal, and the established transcript/gene
prefix removal. It is not the production default and may be rejected by the
Differential Expression API for a full-length matrix-only analysis.

The legacy behavior remains documented so historical comparisons are
reproducible; it is never activated silently.
