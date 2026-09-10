# Real biological integration — GSE133183

## Outcome

The complete terminal-manifest route executed successfully on Slurm and is
classified as `PASS_WITH_LIMITATIONS`. All technical release gates and the
entity/state accounting check passed. The limitations are biological or
methodological findings and do not indicate a workflow execution failure.

| Criterion | Result | Interpretation |
|---|---|---|
| IB1 | PASS | RNA-seq and multi-mark ChIP-seq contracts are reference-compatible. |
| IB2 | PASS | All 12 processes, the HTML report and terminal manifest completed. |
| IB3 | PASS | 78,517 unique genes partition exactly into declared RNA/ChIP states. |
| IB4 | FAIL | No H3K27me3 region met the frozen differential-significance thresholds. |
| IB5 | NOT_EVALUABLE | The current statistics output has no directional concordance Fisher tests. |
| IB6 | PASS | Every preregistered example was reported without retrospective selection. |
| IB7 | PASS | Top-20 overall and directional candidate inventories were produced. |
| IB8 | PASS | Background, annotation checksum and Benjamini–Hochberg method are recorded. |

## Biological observations

Differential Binding tested 271,544 H3K27ac and 467,451 H3K27me3 regions.
H3K27ac had 14,957 significant regions under the frozen policy
(`padj <= 0.05`, `|log2FC| >= 1`): 14,847 decreased and 110 increased. The
independent upstream summary confirms that H3K27me3 had zero significant
regions, so IB4 is an unmet expected range rather than an evaluation defect.

The final evidence model contains 78,517 canonical genes. RNA evidence is
measured for 78,477 genes and ChIP evidence for 60,723. Regulatory
interpretation reports 13 concordant-activation and 22 concordant-repression
records, alongside 68 discordant records. The literature examples FGF18,
UBTD2, FBXW11, IGF2, HBB, HBZ and HBE1 are all represented, but none is forced
into a favorable regulatory class.

The functional provider completed honestly as `complete_empty`: the frozen
template supplied no external functional terms, while the background,
annotation identity and multiple-testing method remain explicit. Pathway
enrichment is therefore not claimed by this benchmark.

## Performance

The 12-process integration route completed in approximately 37 minutes of
wall-clock time on the shared cluster. `REGULATORY_INTERPRETATION` dominated
runtime at 25 minutes 10 seconds. `MOLECULAR_EVIDENCE_INTEGRATION` had the
largest observed memory footprint at 10.6 GB RSS. These measurements are
descriptive and are not a controlled cluster benchmark.

## Reproducibility and audit

The run consumed only the three validated terminal manifests. Differential
Binding tables remained byte-identical while their exact region IDs and
coordinates were annotated with the frozen native provider. The failed
pre-result attempts were retained separately for audit. Compact evaluation
tables, checksums, candidates and task performance are stored in
[`results/real/evaluation`](../results/real/evaluation/).

The absence of significant H3K27me3 and the missing directional enrichment
test are recorded as follow-up investigations. Neither justifies changing the
frozen thresholds or tuning the completed result post hoc.

A private compact audit archive was retained outside the repository. Its
sanitized filename and SHA-256 identity are recorded in
[`provenance/real_biological_audit_archive.json`](../provenance/real_biological_audit_archive.json);
the archive itself is not published because execution logs can contain
cluster-specific paths.

Tracked follow-ups:

- [#66 — expose the Differential Binding region universe in ChIP manifests](https://github.com/GMiguelAlves/HelixForge/issues/66)
- [#67 — emit directional enrichment tests from Integrative statistics](https://github.com/GMiguelAlves/HelixForge/issues/67)
- [#68 — investigate absent H3K27me3 differential signal in GSE133183](https://github.com/GMiguelAlves/HelixForge/issues/68)
