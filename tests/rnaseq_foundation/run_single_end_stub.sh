#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
case_root=${1:-"$(mktemp -d /tmp/helixforge-single-end-stub.XXXXXX)"}
mkdir -p "$case_root"
cat > "$case_root/local.config" <<'EOF'
process {
    withLabel: native_module { cpus = 1; memory = 1.GB }
    withLabel: compatibility_adapter { cpus = 1; memory = 1.GB }
}
EOF

"${NEXTFLOW_BIN:-nextflow}" run "$repo_root/main.nf" \
    -c "$case_root/local.config" -profile local -stub-run -ansi-log false \
    -work-dir "$case_root/work" \
    --workflow rnaseq --rnaseq_run_mode full --rnaseq_stub_layout single \
    --rnaseq_counts_from_abundance lengthScaledTPM \
    --rnaseq_library_protocol full_length \
    --rnaseq_de_spec "$repo_root/tests/fixtures/native_de/analysis_spec.json" \
    --rnaseq_report_genes "$repo_root/tests/fixtures/native_rnaseq_report/genes.txt" \
    --outdir "$case_root/results"

python3 - "$case_root" <<'PY'
import csv
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
manifest = json.loads((root / "results/rnaseq/rnaseq_run_manifest.json").read_text())
assert manifest["samples"]
assert all(sample["library_layout"] == "single" for sample in manifest["samples"])
assert all((sample["fragment_length_mean"], sample["fragment_length_sd"]) == (200, 80)
           for sample in manifest["samples"])
quant_manifests = list((root / "results/pipeline_info/native_quantification/salmon_quant").glob("*.manifest.json"))
assert quant_manifests
for path in quant_manifests:
    document = json.loads(path.read_text())
    assert document["library_layout"] == "single"
    assert (document["fragment_length_mean"], document["fragment_length_sd"]) == (200, 80)
with (root / "results/pipeline_info/execution_trace.tsv").open(newline="") as handle:
    processes = [row["name"] for row in csv.DictReader(handle, delimiter="\t")]
assert any("TRIM_GALORE_SINGLE" in name for name in processes)
assert any("MERGE_FASTQ_SINGLE" in name for name in processes)
assert all(".R2" not in name for name in processes)
assert any("SALMON_IMPORT" in name for name in processes)
assert any("DESEQ2_MODEL" in name for name in processes)
PY

printf '[OK] single-end RNA-seq stub: %s\n' "$case_root"
