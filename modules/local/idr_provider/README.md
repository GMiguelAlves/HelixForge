# IDR_PROVIDER

IDR is not approximated by interval intersection. This provider executes the
official IDR 2.0.4.2 CLI for exactly two premerged biological `narrowPeak`
replicates. Threshold and rank metric are mandatory; the random seed is fixed at
zero and the complete command is recorded.

The filtered IDR output is normalized to the existing Consensus API roles:
`consolidated_peaks.tsv`, `consolidated_peaks.bed`, replicate evidence,
statistics, manifest, versions, execution metadata, raw IDR output, and plot.
`complete_empty` is a valid result and never becomes an interval-consensus
fallback.

The input lists should be sufficiently permissive because IDR compares ranked
peak lists across their signal/noise spectrum. HelixForge does not silently
change the upstream MACS3 cutoff.
