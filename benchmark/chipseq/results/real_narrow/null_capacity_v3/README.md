# Real Narrow RN3 exact-GC capacity preflight

This directory preserves the compact, inference-free output of Slurm job
`16269`. The preflight evaluated the final registered RN3 null contract using
operational strata defined by chromosome, exact interval width and exact
integer GC-base count.

## Outcome

```ini
PREFLIGHT_STATUS = FAIL_NOT_EVALUABLE
NULL_SETS_GENERATED = false
RN3_CALCULATED = false
RN3 = NOT_EVALUABLE_UNDER_FROZEN_CONTROL_REQUIREMENTS
```

Of 31,426 required strata, 1,511 had candidate capacity `M_g` below observed
demand `k_g`, affecting 1,546 observed peaks. The frozen failure policy was
therefore activated before null generation. No fourth null-generator model is
permitted.

The candidate universe is the deterministic, uniformly sampled eligible
parent pool used by the registered implementation. It is a finite operational
universe, not an exhaustive enumeration of every possible genomic start.

## Files

- `summary.json`: machine-readable result and capacity summaries;
- `manifest.json`: compact provenance manifest (identical scientific content);
- `exact_gc_capacity.tsv`: `M_g`, `k_g` and `M_g/k_g` for each operational
  stratum;
- `parent_pool_capacity.tsv`: capacity of the descriptive parent pools;
- `checksums.sha256`: checksums of all preserved evidence files.

The checksum manifest was regenerated locally from the copied, byte-identical
artifacts because the original job script mistakenly included the checksum
file itself while it was still being written. This audit-only correction does
not change any scientific artifact or result. The generator has been corrected
to exclude its own checksum file in future executions.
