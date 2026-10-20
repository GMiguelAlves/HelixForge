# Native Peak Annotation tests

- `test_peak_annotation.py`: small parameter, coordinate, priority, seqname,
  and invalid-build tests;
- `run_stub.sh`: subworkflow stub, `-resume`, and top-level
  `chipseq_run_mode=annotation` stub.

These checks validate annotation contracts and orchestration, not biological
occupancy or broad-domain reconstruction. Retired experimental broad-provider
manifests must fail explicitly without falling back to a supported method.
