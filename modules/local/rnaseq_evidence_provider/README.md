# RNA Evidence Provider

Thin DSL2 adapter for Standardized Evidence Model v1. The process stages the
terminal RNA run manifest, a binding document, and every scientific input as a
tracked `path`. The provider never scans a result directory.

`bindings` contains ordered entries such as:

```json
{"bindings":[{"artifact_id":"run.import.abundance","declared_index":0}]}
```

`declared_index` addresses the matching item in `declared_artifacts`. A
`relative_path` may select a file inside a declared directory. Optional evidence
datasets are omitted when their source type is not bound.
