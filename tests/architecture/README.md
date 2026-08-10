# Architecture consolidation tests

Run without scientific dependencies:

```bash
python tests/architecture/test_consolidation.py
```

The checks cover parameter inventory, the common manifest envelope, RNA/ChIP
composition guards, aggregate identities, BAM manifest lineage and the
HelixForge naming boundary. They do not validate scientific equivalence.
