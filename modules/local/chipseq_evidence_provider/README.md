# ChIP Evidence Provider

Thin DSL2 adapter for Standardized Evidence Model v1. Only manifest artifacts
with explicit entries in the binding document are parsed. BAMs remain supporting
artifacts, tracks remain visualization artifacts, and reports remain provenance;
none are staged unless a caller deliberately declares them.

Bindings use `artifact_id`, `declared_index`, and optional `relative_path`, as
documented by the RNA provider. Peak sets, consensus/IDR, peak-gene associations
and differential binding remain separate evidence types.
