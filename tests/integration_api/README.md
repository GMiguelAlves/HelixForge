# Integration API v1 contract tests

These dependency-light tests validate the human examples, semantic failures,
filesystem failures, RNA/ChIP reference compatibility and a projection of the
deterministic Integration stage-1 RNA fixture. When `jsonschema` is available,
the same examples are validated against the complete Draft 2020-12 schema set.

```bash
python3 -m unittest tests.integration_api.test_contracts
```
