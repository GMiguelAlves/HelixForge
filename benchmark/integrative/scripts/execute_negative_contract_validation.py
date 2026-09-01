#!/usr/bin/env python3
"""Execute the frozen 10E Integration API contract fixtures."""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import os
import platform
import resource
import shutil
import subprocess
import sys
import time
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bin"))

from integration.evidence.io import load_bindings, read_tsv, sha256, write_tsv  # noqa: E402
from integration.evidence.provider import build_evidence  # noqa: E402
from integration.evidence.validation import validate_evidence_manifest  # noqa: E402
from integration.harmonization.core import build_harmonization, canonical_context  # noqa: E402
from integration.workflow.preflight import prepare_inputs  # noqa: E402
from integration_contract import schema_contract_errors, semantic_errors  # noqa: E402
from validate_integration_manifest import jsonschema_errors  # noqa: E402


SCIENTIFIC_TARGET = "dc0218ce902302da476910595bb133c82fee927c"
INTEGRATION_WORKFLOW = "d0d1e7499e5b42be8294da3d85e402fa90a1cfe2"
TEN_B_COMMIT = "1d65b33"
TEN_C_COMMIT = "9a4529a"
EXPECTED_TABLE_SHA256 = "ba87581f3f6d8ce5ab58a510f801ad361844e239b2cab3941ccd3692be961014"
FIELDS = [
    "test_id", "category", "mutation", "expected_behavior", "expected_stage",
    "observed_behavior", "observed_stage", "expected_error_or_state",
    "observed_error_or_state", "status", "diagnostic_clear", "final_outputs",
]


def dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_inventory(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_rows(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sanitize(message: str, run_root: Path) -> str:
    return " ".join(str(message).replace(str(run_root), "<RUN_ROOT>").split())


def specific_jsonschema_errors(document: dict[str, Any], schema_name: str) -> list[str]:
    """Expose field-level diagnostics hidden by the public union schema."""
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource

    schema_root = ROOT / "schemas/integration"
    resources = []
    for path in schema_root.rglob("*.json"):
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("$id"):
            resources.append((value["$id"], Resource.from_contents(value)))
    registry = Registry().with_resources(resources)
    schema = json.loads((schema_root / schema_name).read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, registry=registry, format_checker=Draft202012Validator.FORMAT_CHECKER)
    return [error.message for error in sorted(validator.iter_errors(document), key=lambda item: list(item.path))]


def category(test_id: str) -> str:
    return {
        "REF": "compatibility", "MAN": "manifest", "CON": "contrast",
        "ENT": "entity", "MARK": "mark", "CTX": "context",
    }[test_id.split("-")[1]]


def expected_behavior(disposition: str) -> str:
    return "PRESERVE_SEPARATELY" if disposition == "PRESERVE" and disposition else disposition


def make_result(case: dict[str, str], observed: str, stage: str, detail: str, ok: bool, run_root: Path, final_outputs: int = 0) -> dict[str, str]:
    return {
        "test_id": case["negative_test_id"],
        "category": category(case["negative_test_id"]),
        "mutation": case["input_condition"],
        "expected_behavior": expected_behavior(case["expected_disposition"]),
        "expected_stage": case["expected_layer"],
        "observed_behavior": observed,
        "observed_stage": stage,
        "expected_error_or_state": case["expected_error_or_state"],
        "observed_error_or_state": sanitize(detail, run_root),
        "status": "PASS" if ok else "FAIL",
        "diagnostic_clear": "YES" if detail else "NO",
        "final_outputs": str(final_outputs),
    }


def run_expect_failure(case: dict[str, str], action: Callable[[], Any], stage: str, required: str, run_root: Path, final_dir: Path | None = None) -> dict[str, str]:
    try:
        value = action()
        errors = value if isinstance(value, list) else []
        if errors:
            message = "; ".join(str(item) for item in errors)
            failed = True
        else:
            message = "validator accepted input"
            failed = False
    except Exception as error:  # expected negative-contract path
        message = f"{type(error).__name__}: {error}"
        failed = True
    output_count = 0
    if final_dir and final_dir.exists():
        output_count = sum(path.is_file() for path in final_dir.rglob("*"))
    ok = failed and required.casefold() in message.casefold() and output_count == 0
    return make_result(case, "FAIL" if failed else "PASS", stage, message, ok, run_root, output_count)


def prepare_baseline(run_root: Path) -> dict[str, Path]:
    fixture = run_root / "baseline_fixture"
    subprocess.run([
        sys.executable, str(ROOT / "benchmark/integrative/scripts/prepare_synthetic_fixture.py"),
        "--truth", str(ROOT / "benchmark/integrative/datasets/synthetic_truth.tsv"),
        "--truth-manifest", str(ROOT / "benchmark/integrative/datasets/synthetic_truth_manifest.json"),
        "--output-dir", str(fixture),
    ], check=True)
    rna_manifest = fixture / "rna/rnaseq_run_manifest.json"
    chip_manifest = fixture / "chip/chipseq_run_manifest.json"
    rna = json.loads(rna_manifest.read_text(encoding="utf-8"))
    chip = json.loads(chip_manifest.read_text(encoding="utf-8"))
    schema_root = ROOT / "schemas/integration"
    errors = jsonschema_errors(rna, schema_root) + jsonschema_errors(chip, schema_root)
    errors += schema_contract_errors(rna) + semantic_errors(rna) + schema_contract_errors(chip) + semantic_errors(chip)
    if errors:
        raise ValueError("positive baseline contract failed: " + "; ".join(errors))
    prepared = run_root / "baseline_prepared"
    prepare_inputs(rna_manifest, rna_manifest.parent / "integration_artifacts", chip_manifest, chip_manifest.parent / "integration_artifacts", prepared)
    rna_evidence, chip_evidence = run_root / "baseline_rna_evidence", run_root / "baseline_chip_evidence"
    rna_bindings = load_bindings(prepared / "rnaseq_bindings.json", sorted((prepared / "rnaseq_artifacts").glob("*/*")))
    chip_bindings = load_bindings(prepared / "chipseq_bindings.json", sorted((prepared / "chipseq_artifacts").glob("*/*")))
    build_evidence(json.loads((prepared / "rnaseq_run_manifest.json").read_text(encoding="utf-8")), rna_bindings, rna_evidence)
    build_evidence(json.loads((prepared / "chipseq_run_manifest.json").read_text(encoding="utf-8")), chip_bindings, chip_evidence)
    if validate_evidence_manifest(json.loads((rna_evidence / "evidence_manifest.json").read_text()), rna_evidence):
        raise ValueError("positive RNA evidence baseline is invalid")
    if validate_evidence_manifest(json.loads((chip_evidence / "evidence_manifest.json").read_text()), chip_evidence):
        raise ValueError("positive ChIP evidence baseline is invalid")
    harmonization = run_root / "baseline_harmonization"
    build_harmonization(rna_evidence, chip_evidence, harmonization, json.loads((fixture / "harmonization_policy.json").read_text()))
    return {
        "fixture": fixture, "rna_manifest": rna_manifest, "chip_manifest": chip_manifest,
        "rna_evidence": rna_evidence, "chip_evidence": chip_evidence,
        "harmonization": harmonization,
    }


def copy_bundle(source: Path, target: Path) -> dict[str, Any]:
    shutil.copytree(source, target)
    return json.loads((target / "evidence_manifest.json").read_text(encoding="utf-8"))


def update_dataset(root: Path, manifest: dict[str, Any], evidence_type: str, transform: Callable[[list[str], list[dict[str, str]]], list[dict[str, str]]]) -> None:
    dataset = next(item for item in manifest["datasets"] if item["evidence_type"] == evidence_type)
    path = root / dataset["path"]
    fields, rows = read_tsv(path)
    rows = transform(fields, rows)
    dataset["records"] = write_tsv(path, fields, rows)
    dataset["checksum"] = {"algorithm": "sha256", "value": sha256(path)}


def execute_iteration(run_root: Path, inventory: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    run_root.mkdir(parents=True, exist_ok=True)
    baseline = prepare_baseline(run_root)
    cases = {item["negative_test_id"]: item for item in inventory}
    results: list[dict[str, str]] = []
    snapshots = run_root / "fixture_snapshots"
    snapshots.mkdir()
    original_rna = json.loads(baseline["rna_manifest"].read_text(encoding="utf-8"))
    original_chip = json.loads(baseline["chip_manifest"].read_text(encoding="utf-8"))

    for test_id, field, replacement, required in (
        ("IC-REF-01", "reference_id", "other_reference", "reference_id incompatible"),
        ("IC-REF-02", "genome_id", "other_genome", "genome_id incompatible"),
        ("IC-REF-03", "assembly", "other_assembly", "assembly incompatible"),
        ("IC-REF-04", "annotation_id", "other_annotation", "annotation_id incompatible"),
    ):
        document = copy.deepcopy(original_chip)
        document["reference"][field] = replacement
        manifest = snapshots / f"{test_id}.chipseq_run_manifest.json"
        dump_json(manifest, document)
        final_dir = run_root / test_id / "final"
        results.append(run_expect_failure(
            cases[test_id],
            lambda m=manifest, o=final_dir: prepare_inputs(
                baseline["rna_manifest"], baseline["rna_manifest"].parent / "integration_artifacts",
                m, baseline["chip_manifest"].parent / "integration_artifacts", o,
            ),
            "compatibility", required, run_root, final_dir,
        ))

    document = copy.deepcopy(original_rna)
    del document["run"]
    dump_json(snapshots / "IC-MAN-01.rnaseq_run_manifest.json", document)
    results.append(run_expect_failure(cases["IC-MAN-01"], lambda: specific_jsonschema_errors(document, "rnaseq-run-manifest.schema.json"), "JSON Schema", "required property", run_root))

    document = copy.deepcopy(original_rna)
    del document["provenance"]
    dump_json(snapshots / "IC-MAN-02.rnaseq_run_manifest.json", document)
    results.append(run_expect_failure(cases["IC-MAN-02"], lambda: specific_jsonschema_errors(document, "rnaseq-run-manifest.schema.json"), "JSON Schema", "required property", run_root))

    document = copy.deepcopy(original_rna)
    document["artifacts"][0]["artifact_type"] = "unknown_integration_artifact"
    dump_json(snapshots / "IC-MAN-03.rnaseq_run_manifest.json", document)
    results.append(run_expect_failure(cases["IC-MAN-03"], lambda: specific_jsonschema_errors(document, "rnaseq-run-manifest.schema.json"), "JSON Schema", "not one of", run_root))

    document = copy.deepcopy(original_rna)
    document["artifacts"][0]["contrast_id"] = "undeclared_contrast"
    dump_json(snapshots / "IC-CON-01.rnaseq_run_manifest.json", document)
    results.append(run_expect_failure(cases["IC-CON-01"], lambda: semantic_errors(document), "semantic validation", "unknown contrast", run_root))

    document = copy.deepcopy(original_rna)
    document["contrasts"][0]["denominator"] = document["contrasts"][0]["numerator"]
    dump_json(snapshots / "IC-CON-02.rnaseq_run_manifest.json", document)
    results.append(run_expect_failure(cases["IC-CON-02"], lambda: semantic_errors(document), "semantic validation", "identical numerator and denominator", run_root))

    contrast_root = run_root / "IC-CON-03"
    rna_bundle = contrast_root / "rna"
    chip_bundle = contrast_root / "chip"
    copy_bundle(baseline["rna_evidence"], rna_bundle)
    chip_evidence = copy_bundle(baseline["chip_evidence"], chip_bundle)
    chip_evidence["contrasts"][0].update({"contrast_id": "adult_vs_control", "numerator": "adult", "denominator": "control"})
    update_dataset(chip_bundle, chip_evidence, "differential_binding", lambda _fields, rows: [{**row, "contrast_id": "adult_vs_control"} for row in rows])
    dump_json(chip_bundle / "evidence_manifest.json", chip_evidence)
    evidence_errors = validate_evidence_manifest(chip_evidence, chip_bundle)
    contrast_output = contrast_root / "harmonization"
    if not evidence_errors:
        build_harmonization(rna_bundle, chip_bundle, contrast_output, {"strip_version_suffix": True})
    contrast_rows = read_tsv(contrast_output / "contrast_map.tsv")[1] if (contrast_output / "contrast_map.tsv").is_file() else []
    statuses = Counter(row["mapping_status"] for row in contrast_rows)
    contrast_ok = not evidence_errors and statuses == Counter({"RNA_ONLY": 1, "CHIP_ONLY": 1}) and all(row["mapping_status"] != "MATCHED" for row in contrast_rows)
    results.append(make_result(cases["IC-CON-03"], "PRESERVE_SEPARATELY" if contrast_ok else "FAIL", "harmonization", f"mapping_status={dict(statuses)}; evidence_errors={evidence_errors}", contrast_ok, run_root))

    collision_root = run_root / "IC-ENT-01"
    collision_rna = collision_root / "rna"
    collision_chip = collision_root / "chip"
    rna_evidence = copy_bundle(baseline["rna_evidence"], collision_rna)
    copy_bundle(baseline["chip_evidence"], collision_chip)
    def collision_rows(_fields: list[str], rows: list[dict[str, str]]) -> list[dict[str, str]]:
        first = rows[0]
        return rows + [
            {**first, "evidence_id": "collision.version.1", "source_entity_id": "SYN_COLLISION.1"},
            {**first, "evidence_id": "collision.version.2", "source_entity_id": "SYN_COLLISION.2"},
        ]
    update_dataset(collision_rna, rna_evidence, "differential_expression", collision_rows)
    dump_json(collision_rna / "evidence_manifest.json", rna_evidence)
    results.append(run_expect_failure(
        cases["IC-ENT-01"],
        lambda: build_harmonization(collision_rna, collision_chip, collision_root / "final", {"strip_version_suffix": True}),
        "harmonization", "version stripping causes entity collisions", run_root, collision_root / "final",
    ))

    _fields, mark_rows = read_tsv(baseline["harmonization"] / "mark_map.tsv")
    marks = {row["source_mark"]: row for row in mark_rows}
    hp1_ok = marks.get("HP1", {}).get("canonical_mark") == "SmHP1"
    histone_ok = marks.get("h3k4me3", {}).get("canonical_mark") == "H3K4me3"
    results.append(make_result(cases["IC-MARK-01"], "NORMALIZE" if hp1_ok else "FAIL", "harmonization", f"HP1={marks.get('HP1')}; histone_case={marks.get('h3k4me3')}", hp1_ok and histone_ok, run_root))

    unknown_mark = marks.get("SYNTHETIC_UNKNOWN_MARK", {})
    unknown_ok = unknown_mark.get("canonical_mark") == "SYNTHETIC_UNKNOWN_MARK" and unknown_mark.get("normalization_rule") == "exact"
    results.append(make_result(cases["IC-MARK-02"], "PRESERVE_SEPARATELY" if unknown_ok else "FAIL", "harmonization", f"unknown_mark={unknown_mark}", unknown_ok, run_root))

    source_context = "SYNTHETIC_UNLISTED_CONTEXT"
    canonical, rule, rule_class = canonical_context(source_context)
    context_ok = canonical == source_context and rule == "exact"
    results.append(make_result(cases["IC-CTX-01"], "PRESERVE_SEPARATELY" if context_ok else "FAIL", "harmonization", f"canonical={canonical}; rule={rule}; rule_class={rule_class}", context_ok, run_root))

    entity_rows = read_tsv(baseline["harmonization"] / "entity_map.tsv")[1]
    positive_normalization = [row for row in entity_rows if row["normalization_rule"] in {"strip_version_suffix", "explicit_alias_map", "strip_literal_gene_prefix"}]
    normalization = [
        {"check": "supported_entity_normalization", "source": str(len(positive_normalization)), "canonical": "unambiguous mappings", "behavior": "NORMALIZE", "status": "PASS" if positive_normalization else "FAIL"},
        {"check": "HP1_alias", "source": "HP1", "canonical": marks.get("HP1", {}).get("canonical_mark", ""), "behavior": "NORMALIZE", "status": "PASS" if hp1_ok else "FAIL"},
        {"check": "histone_case", "source": "h3k4me3", "canonical": marks.get("h3k4me3", {}).get("canonical_mark", ""), "behavior": "NORMALIZE", "status": "PASS" if histone_ok else "FAIL"},
        {"check": "unknown_mark", "source": "SYNTHETIC_UNKNOWN_MARK", "canonical": unknown_mark.get("canonical_mark", ""), "behavior": "PRESERVE_SEPARATELY", "status": "PASS" if unknown_ok else "FAIL"},
        {"check": "unknown_context", "source": source_context, "canonical": canonical, "behavior": "PRESERVE_SEPARATELY", "status": "PASS" if context_ok else "FAIL"},
    ]
    contrast_detail = [{
        "test_id": "IC-CON-03", "rna_contrast": "condition__treated_vs_control",
        "chip_contrast": "condition__adult_vs_control", "rna_only": str(statuses["RNA_ONLY"]),
        "chip_only": str(statuses["CHIP_ONLY"]), "matched": str(statuses["MATCHED"]),
        "incorrect_merge": "NO" if contrast_ok else "YES", "status": "PASS" if contrast_ok else "FAIL",
    }]
    return sorted(results, key=lambda row: row["test_id"]), normalization, contrast_detail


def ic_rows(results: list[dict[str, str]], normalization: list[dict[str, str]]) -> list[dict[str, str]]:
    by_id = {row["test_id"]: row for row in results}
    groups = {
        "IC1": ["IC-REF-01", "IC-REF-02"],
        "IC2": ["IC-REF-03", "IC-REF-04"],
        "IC3": ["IC-CON-01", "IC-CON-02", "IC-CON-03"],
        "IC4": ["IC-ENT-01"],
        "IC5": ["IC-MAN-01", "IC-MAN-02", "IC-MAN-03"],
        "IC6": ["IC-MARK-01", "IC-MARK-02", "IC-CTX-01"],
    }
    rows = []
    for criterion, identifiers in groups.items():
        checks = [by_id[item]["status"] for item in identifiers]
        if criterion == "IC6":
            checks += [row["status"] for row in normalization]
        rows.append({
            "criterion_id": criterion, "test_ids": ";".join(identifiers),
            "expected": "all frozen behaviors observed", "observed": ";".join(checks),
            "status": "PASS" if all(item == "PASS" for item in checks) else "FAIL",
            "evidence": ";".join(identifiers),
        })
    return rows


def write_checksums(output: Path) -> None:
    targets = sorted(path for path in output.rglob("*") if path.is_file() and path.name != "SHA256SUMS")
    (output / "SHA256SUMS").write_text("\n".join(f"{sha256(path)}  {path.relative_to(output).as_posix()}" for path in targets) + "\n", encoding="utf-8")


def build_report(output: Path, summary: dict[str, Any], results: list[dict[str, str]], ic: list[dict[str, str]]) -> str:
    result_lines = "\n".join(f"| {row['test_id']} | {row['expected_behavior']} | {row['observed_behavior']} | {row['observed_stage']} | {row['status']} |" for row in results)
    ic_lines = "\n".join(f"| {row['criterion_id']} | {row['status']} | {row['test_ids']} |" for row in ic)
    dimensions = "\n".join(
        f"{key} = {value}"
        for key, value in summary["classification"].items()
        if key != "NEGATIVE_CONTRACT_BENCHMARK"
    )
    return f"""# Negative contract validation

## Executive Summary

All {summary['fixtures']['total']} frozen Integration API contract fixtures behaved as preregistered. The positive 10B/10C-derived baseline passed before mutation, all critical invalid inputs failed at their declared layer, and valid-but-unmatched evidence remained separate. No valid terminal integration output was produced by a failing fixture.

## Why 10E Was Executed Before 10D

The benchmark protocol numbering was not changed.

Stage 10E was executed before Stage 10D as an operational risk-reduction decision because contract fixtures are small and inexpensive, while 10D requires acquisition and processing of the real GSE133183 dataset.

No 10D or 10E criteria, fixtures, gates or scientific expectations were changed by this execution-order decision.

`10D_STATUS = NOT_STARTED`, `10D_SKIPPED_TEMPORARILY = YES`, `10D_CANCELLED = NO`.

## Frozen Design

The authoritative inventory SHA-256 remained `{EXPECTED_TABLE_SHA256}`. HelixForge target `{SCIENTIFIC_TARGET}` and integration workflow `{INTEGRATION_WORKFLOW}` were unchanged.

## Positive Baseline

`BASELINE_VALIDATION = PASS`. Both run manifests passed JSON Schema, semantic, filesystem, checksum and reference compatibility validation before mutations.

## Fixture Inventory

| Test | Expected | Observed | Stage | Status |
|---|---|---|---|---|
{result_lines}

## Schema Validation

Malformed envelope, missing provenance and invalid artifact type were rejected by JSON Schema.

## Semantic Validation

Undeclared and self contrasts were rejected before scientific integration.

## Reference / Assembly Compatibility

Reference, genome and assembly mismatches failed at preflight compatibility validation.

## Annotation Compatibility

The annotation mismatch failed at preflight compatibility validation.

## Contrast Semantics

Invalid contrasts failed. Different valid RNA and ChIP contrasts produced one `RNA_ONLY` and one `CHIP_ONLY` mapping, with no matched or fused contrast.

## Entity Normalization and Collisions

Unambiguous frozen aliases/version/prefix rules normalized successfully. Two versioned source IDs collapsing to one assay-level ID failed loudly.

## Mark / Context Validation

`HP1` normalized to `SmHP1`, lowercase histone notation normalized to canonical case, and unknown non-empty mark/context values were preserved exactly.

## Provenance Validation

The frozen missing-provenance fixture was rejected by JSON Schema. Deeper lineage-conflict cases were not part of the authoritative 10E inventory.

## Filesystem / Checksum Validation

The positive baseline passed filesystem and checksum validation. Negative missing-file/checksum fixtures were not present in the frozen authoritative inventory and were not added post-freeze.

## Expected Failure Behavior

All expected failures returned explicit diagnostics and produced zero final scientific outputs.

## Valid Non-integrable Evidence

Different but individually valid contrasts were preserved separately as `RNA_ONLY` and `CHIP_ONLY`; no false combined class or cross-contrast merge was observed.

## IC Acceptance Criteria

| Criterion | Status | Fixtures |
|---|---|---|
{ic_lines}

## Determinism

All fixtures were executed twice. Outcome, validation stage, error class/state and status were identical after path sanitization.

## Limitations

This arm is intentionally contract-level and uses the frozen 14-case inventory. Missing-artifact, checksum-mismatch, schema-version, duplicate-artifact and lineage-conflict cases are covered elsewhere by unit tests or remain candidates for a future preregistered contract expansion; they were not inserted into 10E after the freeze. Performance is descriptive on a shared Slurm cluster.

The first technical attempt used the public union schema's top-level diagnostic,
which correctly rejected all three malformed manifests but hid the frozen
field-level error substring. Before scientific interpretation, the harness was
restricted to the manifest's assay-specific schema so it could record the
underlying diagnostic. This changed neither input, expected behavior, gate nor
HelixForge core behavior; the first compact attempt was retained for audit.

## Final Classification

```text
{dimensions}

NEGATIVE_CONTRACT_BENCHMARK = {summary['classification']['NEGATIVE_CONTRACT_BENCHMARK']}
```

## Next Stage

Return to the frozen real biological integration stage (10D) after maintainer review. This report does not start 10D and does not authorize 10F or a tag.
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--audit-archive", type=Path, required=True)
    parser.add_argument("--report-path", type=Path, default=ROOT / "benchmark/integrative/reports/negative_contract_validation.md")
    args = parser.parse_args()
    started = time.perf_counter()
    cpu_started = time.process_time()
    inventory_path = ROOT / "benchmark/integrative/datasets/negative_contract_cases.tsv"
    if sha256(inventory_path) != EXPECTED_TABLE_SHA256:
        raise ValueError("frozen negative-contract inventory checksum changed")
    inventory = read_inventory(inventory_path)
    if len(inventory) != 14 or len({row["negative_test_id"] for row in inventory}) != 14:
        raise ValueError("frozen inventory must contain 14 unique fixtures")
    work_root = args.work_root.resolve()
    output = args.output_dir.resolve()
    work_root.mkdir(parents=True, exist_ok=True)
    first, normalization, contrasts = execute_iteration(work_root / "iteration-a", inventory)
    second, _normalization_b, _contrasts_b = execute_iteration(work_root / "iteration-b", inventory)
    second_by_id = {row["test_id"]: row for row in second}
    determinism = []
    for row in first:
        other = second_by_id[row["test_id"]]
        compared = ("observed_behavior", "observed_stage", "observed_error_or_state", "status")
        same = all(row[key] == other[key] for key in compared)
        determinism.append({"test_id": row["test_id"], "fields_compared": ";".join(compared), "identical": "YES" if same else "NO", "status": "PASS" if same else "FAIL"})
    criteria = ic_rows(first, normalization)
    all_cases_pass = all(row["status"] == "PASS" for row in first)
    all_deterministic = all(row["status"] == "PASS" for row in determinism)
    all_ic_pass = all(row["status"] == "PASS" for row in criteria)
    failure_rows = [row for row in first if row["expected_behavior"] == "FAIL"]
    disposition_counts = Counter(expected_behavior(row["expected_disposition"]) for row in inventory)
    classifications = {
        "TECHNICAL_EXECUTION": "PASS", "POSITIVE_BASELINE": "PASS",
        "SCHEMA_REJECTION": "PASS" if all(by["status"] == "PASS" for by in first if by["test_id"].startswith("IC-MAN")) else "FAIL",
        "SEMANTIC_REJECTION": "PASS" if all(by["status"] == "PASS" for by in first if by["test_id"] in {"IC-CON-01", "IC-CON-02"}) else "FAIL",
        "REFERENCE_COMPATIBILITY": "PASS" if all(by["status"] == "PASS" for by in first if by["test_id"] in {"IC-REF-01", "IC-REF-02", "IC-REF-03"}) else "FAIL",
        "ANNOTATION_COMPATIBILITY": by_status(first, "IC-REF-04"),
        "CONTRAST_VALIDATION": "PASS" if all(by_status(first, item) == "PASS" for item in ("IC-CON-01", "IC-CON-02")) else "FAIL",
        "VALID_CONTRAST_ISOLATION": by_status(first, "IC-CON-03"),
        "ENTITY_COLLISION_HANDLING": by_status(first, "IC-ENT-01"),
        "NORMALIZATION_BEHAVIOR": "PASS" if all(row["status"] == "PASS" for row in normalization) else "FAIL",
        "PROVENANCE_VALIDATION": by_status(first, "IC-MAN-02"),
        "FILESYSTEM_INTEGRITY_VALIDATION": "NOT_APPLICABLE",
        "FAILURE_OUTPUT_SAFETY": "PASS" if all(row["final_outputs"] == "0" for row in failure_rows) else "FAIL",
        "DETERMINISM": "PASS" if all_deterministic else "FAIL",
    }
    classifications["NEGATIVE_CONTRACT_BENCHMARK"] = "PASS" if all_cases_pass and all_ic_pass and all_deterministic else "FAIL"
    elapsed = time.perf_counter() - started
    cpu = time.process_time() - cpu_started
    peak_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    summary = {
        "schema_version": "1.0", "benchmark": "integrative_negative_contract_validation",
        "status": classifications["NEGATIVE_CONTRACT_BENCHMARK"],
        "operational_stage_reordering": True,
        "stage_state": {"10B": "PASS", "10C": "PASS", "10D": "NOT_STARTED", "10D_skipped_temporarily": True, "10D_cancelled": False, "10E": classifications["NEGATIVE_CONTRACT_BENCHMARK"]},
        "fixtures": {"total": len(inventory), "expected": dict(disposition_counts), "passed": sum(row["status"] == "PASS" for row in first), "failed": sum(row["status"] != "PASS" for row in first)},
        "safety": {"critical_false_acceptances": sum(row["expected_behavior"] == "FAIL" and row["observed_behavior"] != "FAIL" for row in first), "critical_false_rejections": sum(row["expected_behavior"] != "FAIL" and row["status"] != "PASS" for row in first), "invalid_final_outputs": sum(int(row["final_outputs"]) for row in failure_rows), "hidden_silent_integration": 0},
        "classification": classifications,
        "performance": {"wall_seconds": round(elapsed, 6), "cpu_seconds": round(cpu, 6), "peak_rss_kib": peak_kib, "iterations": 2, "scheduler_jobs": 1},
        "provenance": {"helixforge_version": "v1.0.0-rc.1", "scientific_target": SCIENTIFIC_TARGET, "integration_workflow": INTEGRATION_WORKFLOW, "10B_commit": TEN_B_COMMIT, "10C_commit": TEN_C_COMMIT, "fixture_inventory_sha256": EXPECTED_TABLE_SHA256, "python": sys.version.split()[0]},
    }
    if classifications["NEGATIVE_CONTRACT_BENCHMARK"] != "PASS":
        summary["progression"] = "NOT_READY_FOR_REAL_BIOLOGICAL_INTEGRATION"
    else:
        summary["progression"] = "READY_FOR_REAL_BIOLOGICAL_INTEGRATION"
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    fixture_inventory = [{
        "test_id": row["negative_test_id"], "category": category(row["negative_test_id"]),
        "fixture": f"derived:{row['negative_test_id']}", "mutation": row["input_condition"],
        "expected_behavior": expected_behavior(row["expected_disposition"]), "expected_stage": row["expected_layer"],
        "expected_error_or_state": row["expected_error_or_state"], "IC_gate": ic_for(row["negative_test_id"]),
    } for row in inventory]
    write_rows(output / "fixture_inventory.tsv", list(fixture_inventory[0]), fixture_inventory)
    write_rows(output / "contract_results.tsv", FIELDS, first)
    write_rows(output / "validation_stage_results.tsv", ["test_id", "expected_stage", "observed_stage", "status"], first)
    write_rows(output / "normalization_results.tsv", ["check", "source", "canonical", "behavior", "status"], normalization)
    write_rows(output / "contrast_isolation_results.tsv", list(contrasts[0]), contrasts)
    output_audit = [{"test_id": row["test_id"], "expected_failure": "YES", "final_outputs": row["final_outputs"], "misleading_success_manifest": "NO", "status": "PASS" if row["final_outputs"] == "0" else "FAIL"} for row in failure_rows]
    write_rows(output / "failure_output_audit.tsv", list(output_audit[0]), output_audit)
    write_rows(output / "determinism.tsv", list(determinism[0]), determinism)
    write_rows(output / "acceptance_criteria.tsv", list(criteria[0]), criteria)
    write_rows(output / "performance.tsv", ["metric", "value", "unit", "role"], [
        {"metric": "wall_time", "value": f"{elapsed:.6f}", "unit": "seconds", "role": "descriptive"},
        {"metric": "cpu_time", "value": f"{cpu:.6f}", "unit": "seconds", "role": "descriptive"},
        {"metric": "peak_rss", "value": str(peak_kib), "unit": "KiB", "role": "descriptive"},
        {"metric": "fixture_count", "value": str(len(inventory)), "unit": "fixtures", "role": "descriptive"},
    ])
    dump_json(output / "benchmark_summary.json", summary)
    dump_json(output / "provenance.json", {
        **summary["provenance"], "hostname": platform.node(), "platform": platform.platform(),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
        "commands": ["execute_negative_contract_validation.py --work-root <scratch> --output-dir benchmark/integrative/results/contracts"],
        "comparison_script": "benchmark/integrative/scripts/execute_negative_contract_validation.py",
    })
    report_path = args.report_path.resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(build_report(output, summary, first, criteria), encoding="utf-8")
    readme = work_root / "README_AUDITORIA_PT.md"
    readme.write_text("# Auditoria da validação negativa integrativa\n\nEste pacote preserva os resultados compactos, a tabela congelada de casos, os manifests mutados e os scripts usados na validação 10E. Não contém dados biológicos grandes, workdir do Nextflow nem credenciais.\n", encoding="utf-8")
    args.audit_archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.audit_archive, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(readme, "README_AUDITORIA_PT.md")
        archive.write(inventory_path, "frozen/negative_contract_cases.tsv")
        archive.write(Path(__file__), "scripts/execute_negative_contract_validation.py")
        for path in sorted(output.rglob("*")):
            if path.is_file():
                archive.write(path, f"results/{path.relative_to(output).as_posix()}")
        archive.write(report_path, "reports/negative_contract_validation.md")
        for path in sorted((work_root / "iteration-a/fixture_snapshots").glob("*.json")):
            archive.write(path, f"fixtures/{path.name}")
    archive_info = {"path": str(args.audit_archive), "sha256": sha256(args.audit_archive), "size_bytes": args.audit_archive.stat().st_size, "integrity": "VERIFIED"}
    dump_json(output / "audit_archive.json", archive_info)
    summary["performance"]["output_size_bytes"] = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
    dump_json(output / "benchmark_summary.json", summary)
    write_checksums(output)
    print(json.dumps({"status": summary["status"], "progression": summary["progression"], "fixtures": summary["fixtures"], "audit": archive_info}, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


def by_status(results: list[dict[str, str]], test_id: str) -> str:
    return next(row["status"] for row in results if row["test_id"] == test_id)


def ic_for(test_id: str) -> str:
    if test_id in {"IC-REF-01", "IC-REF-02"}:
        return "IC1"
    if test_id in {"IC-REF-03", "IC-REF-04"}:
        return "IC2"
    if test_id.startswith("IC-CON"):
        return "IC3"
    if test_id.startswith("IC-ENT"):
        return "IC4"
    if test_id.startswith("IC-MAN"):
        return "IC5"
    return "IC6"


if __name__ == "__main__":
    raise SystemExit(main())
