#!/usr/bin/env python3
"""Lightweight architecture and contract checks; no scientific tools required."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def config_parameter_names() -> set[str]:
    text = (ROOT / "nextflow.config").read_text(encoding="utf-8")
    names: set[str] = set()
    inside = False
    depth = 0
    for line in text.splitlines():
        if re.match(r"^\s*params\s*\{", line):
            inside = True
            depth = 1
            continue
        if not inside:
            continue
        depth += line.count("{") - line.count("}")
        match = re.match(r"^\s{4}([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        if match:
            names.add(match.group(1))
        if depth == 0:
            break
    return names


def test_parameter_inventory_is_complete() -> None:
    schema = json.loads((ROOT / "nextflow_schema.json").read_text(encoding="utf-8"))
    assert config_parameter_names() == set(schema["properties"])
    chip_modes = set(schema["properties"]["chipseq_run_mode"]["enum"])
    assert {"annotation", "tracks", "report"} <= chip_modes


def test_common_manifest_envelope() -> None:
    schema = json.loads((ROOT / "schemas/manifest-v1.schema.json").read_text(encoding="utf-8"))
    assert set(schema["required"]) == {"schema_version", "type", "id", "status"}
    example = json.loads((ROOT / "assets/manifests/manifest.example.json").read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(example)


def test_workflow_composition_guards() -> None:
    rna = (ROOT / "subworkflows/local/rnaseq/alignment_quantification.nf").read_text(encoding="utf-8")
    assert "if (run_alignment && native_alignment_enabled)" in rna
    assert "if (run_quantification && native_quantification_enabled)" in rna
    assert "if (run_mode in ['alignment', 'quant', 'quantification'])" in rna

    chip = (ROOT / "subworkflows/local/chipseq/native_foundation.nf").read_text(encoding="utf-8")
    assert ".combine(indexes_by_key, by: 0)" in chip
    assert "index_key" in chip
    assert "CHIPSEQ_REPORT(report_records)" in chip
    assert "mode == 'full'" in chip
    idr = (ROOT / "modules/local/idr_provider/main.nf").read_text(encoding="utf-8")
    assert "run_idr.py" in idr
    assert "not_implemented" not in idr
    consensus_context = (ROOT / "modules/local/consensus_context/main.nf").read_text(encoding="utf-8")
    assert "set -o pipefail" in consensus_context

    chip_workflow = (ROOT / "workflows/chipseq.nf").read_text(encoding="utf-8")
    assert "LEGACY_STEP" not in chip_workflow
    assert "chipseq_native_" not in chip_workflow
    assert "legacy_root" not in chip_workflow
    assert not (ROOT / "pipelines/chipseq/legacy").exists()
    assert (ROOT / "pipelines/chipseq/config/pipeline_config.sh").is_file()

    de = (ROOT / "subworkflows/local/rnaseq/differential_expression.nf").read_text(encoding="utf-8")
    assert "RNASEQ_BATCH_STEP" not in de
    assert "RNASEQ_BATCH_STEP.out.status" not in de
    assert "RNASEQ_DEG_STEP" not in de
    assert "rnaseq_native_de=false is no longer supported" in de

    workflow = (ROOT / "workflows/rnaseq.nf").read_text(encoding="utf-8")
    assert "legacy_root" not in workflow
    assert not (ROOT / "pipelines/rnaseq/legacy").exists()
    assert (ROOT / "pipelines/rnaseq/config/pipeline_config.sh").is_file()

    production_fixture = (ROOT / "tests/slurm/generate_rnaseq_fixture.py").read_text(encoding="utf-8")
    assert '"covariates": ["batch"]' in production_fixture
    assert '"formula": "~ batch + condition"' in production_fixture
    production_harness = (ROOT / "tests/slurm/run_rnaseq_production_real.sh").read_text(encoding="utf-8")
    assert '"baseline-driver"' in production_harness
    assert "--rnaseq_report_enabled true" in production_harness
    assert "--rnaseq_report_genes" in production_harness


def test_manifest_identity_and_lineage_guards() -> None:
    expected = {
        "modules/local/peak_qc_aggregate/resources/usr/bin/peak_qc_aggregate.py": "chipseq.peak_qc.aggregate",
        "modules/local/consensus_aggregate/resources/usr/bin/consensus_aggregate.py": "chipseq.consensus.aggregate",
        "modules/local/peak_annotation_aggregate/resources/usr/bin/peak_annotation_aggregate.py": "chipseq.peak_annotation.aggregate",
        "modules/local/track_aggregate/resources/usr/bin/track_aggregate.py": "chipseq.tracks.aggregate",
    }
    for relative, identifier in expected.items():
        assert identifier in (ROOT / relative).read_text(encoding="utf-8")

    for module in ("bam_select", "bam_duplicates", "bam_blacklist", "bam_index_qc"):
        source = (ROOT / f"modules/local/{module}/main.nf").read_text(encoding="utf-8")
        assert "path(upstream_manifest)" in source
        assert "upstream_manifests" in source


def test_branding_and_legacy_boundary() -> None:
    old_brand = "omics" + "flow"
    violations: list[str] = []
    tracked = subprocess.check_output(
        ["git", "-c", f"safe.directory={ROOT.as_posix()}", "ls-files", "-z"], cwd=ROOT
    ).decode().split("\0")
    for filename in filter(None, tracked):
        relative = Path(filename)
        if len(relative.parts) >= 3 and relative.parts[0] == "pipelines" and relative.parts[2] == "legacy":
            continue
        path = ROOT / relative
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if old_brand not in text.lower():
            continue
        violations.append(str(relative))
    assert not violations, f"obsolete branding outside immutable legacy boundary: {violations}"


def test_integrative_legacy_is_retired() -> None:
    retired = (
        "pipelines/integrative/legacy",
        "subworkflows/local/integrative/integration.nf",
        "modules/local/legacy_step",
        "bin/run_legacy_step.sh",
        "bin/check_legacy_scripts.sh",
    )
    for relative in retired:
        path = ROOT / relative
        assert not path.is_file()
        assert not path.is_dir() or not any(candidate.is_file() for candidate in path.rglob("*"))

    active_roots = ("workflows", "subworkflows", "modules")
    active = "\n".join(
        path.read_text(encoding="utf-8")
        for root in active_roots
        for path in (ROOT / root).rglob("*.nf")
    )
    assert "LEGACY_STEP" not in active
    assert "pipelines/integrative/legacy" not in active

    params = config_parameter_names()
    assert "legacy_dry_run" not in params
    assert "integrative_config" not in params


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
    print(f"architecture consolidation checks: PASS ({len(tests)})")
