# HelixForge v1.0.2

HelixForge `v1.0.2` is a backward-compatible maintenance release that closes
the RNA-seq Report API re-entry gap discovered during the first real
species-project executions.

## RNA-seq report re-entry

The new `rnaseq_run_mode=report_reentry` consumes retained Import and
Differential Expression API artifacts and schedules only:

```text
RNASEQ_REPORT_CONTEXT -> RNASEQ_GENE_REPORT
```

It does not require FASTQs, the originating Nextflow work directory, cache,
Salmon outputs, or rerunning tximport and DESeq2. Inputs remain explicit path
values staged by Nextflow; the Report API validates manifest types, declared
checksums, sample order, candidate syntax, identifiers, and numeric values.

The existing cumulative `report` mode and optional report generation in
`full` are unchanged. Report re-entry creates an independent report manifest
and does not rewrite an accepted terminal RNA-seq manifest.

Although this adds a selectable mode, it restores the already documented
portability of retained API artifacts and changes no existing workflow,
schema, scientific default, output meaning, container, or model. It is
therefore released as a compatibility patch rather than a new scientific
feature line.
