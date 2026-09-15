# HelixForge v1.0.1

HelixForge `v1.0.1` is a backward-compatible maintenance release. It adds an
explicit path for validating and reusing an existing Salmon index without
placing index construction in the execution graph.

Users may provide:

```text
--salmon_prebuilt_index <index-directory>
--salmon_prebuilt_index_manifest <manifest.json>
```

The manifest-bound validator checks transcriptome and index checksums, Salmon
and index versions, k-mer size, and optional inventory measurements before
quantification. A mismatch fails before `SALMON_QUANT`; a successful check
never modifies the supplied index.

When these parameters are absent, the existing `SALMON_INDEX -> SALMON_QUANT`
behavior is unchanged. Scientific defaults, import policy, output contracts,
and the frozen benchmark conclusions from `v1.0.0` are unchanged.
