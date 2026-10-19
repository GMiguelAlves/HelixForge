# Regional catalog 1.0.0: prospective independent validation

This is a separate validation protocol, not a reclassification of the frozen
ChIP-seq benchmarks. Its seeds and generated data were not used in the previous
HP1/H3K27me3 development comparisons. All scientific execution must take place
in an explicitly allocated compute environment.

The [protocol](protocol.json) is frozen before scientific execution. It defines
three seeds and six scenarios: balanced signal, heterogeneous enrichment, one
unenriched library, library-specific domains, variable intradomain signal and
no enrichment. There are 24 shared domain envelopes, three width classes, six
potential private domains and adjacent-domain gaps to test inappropriate fusion.

The generator creates SE aligned reads and independent matched Inputs. The
known simulated fragment distribution is used with MACS3 3.0.4; it is not an
estimate of the physical fragment distribution in a biological experiment.
There is no aligner, mappability/repeat model, sequencing-error model or claim
that synthetic acceptance certifies biological reproducibility.

The caller outputs pass through the real Consensus context and the actual
regional provider. An independent evaluator uses BEDTools directly, without
importing production interval algorithms, to check union/core identities and
measure recovery, base-level false positives, fragmentation and merging.
Private domains are positive truth for a candidate catalog but negative truth
for the shared-region assessment. Null results cannot pass by silently skipping
precision checks: their explicit false-positive and supported-count gates apply.

Every seed/scenario is reported separately. Unmet gates fail; they are not
relaxed after observing results. These prospective criteria are specific to
this validation, not universal thresholds or a calibrated occupancy FDR.

```bash
python validation/broad_consensus/regional_catalog_v1/run_case.py \
  --repo /path/to/HelixForge --output /path/to/new_validation --case 0
```

Case indexes 0–17 enumerate seeds first, then scenarios in protocol order.
The runner requires a Slurm allocation, MACS3 3.0.4, BEDTools and samtools.
Separate Nextflow module smoke/stub/cache tests use
[regional_catalog.nf](../../../tests/native_chipseq_consensus/regional_catalog.nf).
Passing the synthetic validation does not establish that all candidate regions
are biological occupancy or resolve caller-specific fragmentation universally.
