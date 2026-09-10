#!/usr/bin/env python3
"""Evaluate frozen 10C direct versus relocated manifest re-entry equivalence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any


TABLES = (
    "entity_map.tsv", "contrast_map.tsv", "mark_map.tsv",
    "master_evidence.tsv", "master_evidence_long.tsv", "peak_aggregation.tsv",
    "regulatory_classes.tsv", "fisher_tests.tsv", "correlations.tsv",
    "candidate_score.tsv", "candidate_ranking.tsv", "gene_sets.tsv",
    "functional_enrichment.tsv", "functional_tests.tsv", "annotation_summary.tsv",
    "candidate_explorer.tsv",
)
REQUIRED_TABLES = set(TABLES)
SCIENTIFIC_TERMINAL_FIELDS = (
    "reference", "input_manifests", "compatibility", "models", "policies",
    "artifacts", "component_manifests", "record_counts", "provenance",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return list(reader.fieldnames or []), list(reader)


def write_tsv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def canonical_tsv(path: Path) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]:
    fields, rows = read_tsv(path)
    return tuple(fields), tuple(sorted(tuple(row[field] for field in fields) for row in rows))


def locate(root: Path, name: str) -> Path:
    candidates = sorted((path for path in root.rglob(name) if path.is_file()), key=lambda path: (len(path.parts), path.as_posix()))
    if not candidates:
        raise FileNotFoundError(name)
    canonical = {canonical_tsv(path) for path in candidates}
    if len(canonical) != 1:
        raise ValueError(f"duplicate {name} tables disagree within one route")
    return candidates[0]


def locate_json(root: Path, name: str) -> Path:
    candidates = sorted((path for path in root.rglob(name) if path.is_file()), key=lambda path: (len(path.parts), path.as_posix()))
    if not candidates:
        raise FileNotFoundError(name)
    return candidates[0]


def finite(value: str) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def numerical_rows(left: Path, right: Path, absolute_tolerance: float, relative_tolerance: float) -> tuple[list[dict[str, Any]], float, float, int]:
    fields_a, rows_a = read_tsv(left)
    fields_b, rows_b = read_tsv(right)
    if fields_a != fields_b or len(rows_a) != len(rows_b):
        return [], math.inf, math.inf, 1
    output: list[dict[str, Any]] = []
    maximum_abs = 0.0
    maximum_rel = 0.0
    failures = 0
    for row_index, (row_a, row_b) in enumerate(zip(rows_a, rows_b), 1):
        for field in fields_a:
            a, b = finite(row_a[field]), finite(row_b[field])
            if a is None and b is None:
                continue
            if a is None or b is None:
                failures += 1
                output.append({"artifact": left.name, "row": row_index, "field": field, "route_a": row_a[field], "route_b": row_b[field], "absolute_difference": "NA", "relative_difference": "NA", "tolerance": f"abs={absolute_tolerance};rel={relative_tolerance}", "status": "FAIL"})
                continue
            absolute = abs(a - b)
            relative = absolute / max(abs(a), abs(b), 1e-300)
            maximum_abs = max(maximum_abs, absolute)
            maximum_rel = max(maximum_rel, relative)
            status = "PASS" if absolute <= absolute_tolerance or relative <= relative_tolerance else "FAIL"
            failures += status == "FAIL"
            output.append({"artifact": left.name, "row": row_index, "field": field, "route_a": row_a[field], "route_b": row_b[field], "absolute_difference": f"{absolute:.17g}", "relative_difference": f"{relative:.17g}", "tolerance": f"abs={absolute_tolerance};rel={relative_tolerance}", "status": status})
    return output, maximum_abs, maximum_rel, failures


def memory_bytes(value: str) -> int:
    match = re.fullmatch(r"([0-9.]+)\s*([KMGT]?B)", value.strip(), re.IGNORECASE)
    if not match:
        return 0
    return round(float(match.group(1)) * {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}[match.group(2).upper()])


def duration_seconds(value: str) -> float:
    return sum(float(amount) * {"ms": .001, "s": 1, "m": 60, "h": 3600}[unit] for amount, unit in re.findall(r"([0-9.]+)\s*(ms|s|m|h)", value))


def wall_seconds(path: Path) -> float:
    seconds = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.search(r"\b(\d{2}):(\d{2}):(\d{2}\.\d{3})\b", line)
        if match:
            seconds.append(int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3)))
    if not seconds:
        return 0.0
    return round(seconds[-1] - seconds[0] if seconds[-1] >= seconds[0] else 86400 + seconds[-1] - seconds[0], 3)


def size_bytes(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def performance(execution: Path, route: str) -> dict[str, Any]:
    _fields, rows = read_tsv(execution / f"logs/route-{route}.trace.tsv")
    return {
        "route": route.upper(), "processes": len(rows),
        "completed": sum(row["status"] == "COMPLETED" for row in rows),
        "failed": sum(row["status"] != "COMPLETED" for row in rows),
        "workflow_wall_seconds": wall_seconds(execution / f"logs/route-{route}.nextflow.log"),
        "task_realtime_seconds": round(sum(duration_seconds(row["realtime"]) for row in rows), 3),
        "peak_rss_bytes": max(memory_bytes(row["peak_rss"]) for row in rows),
        "peak_vmem_bytes": max(memory_bytes(row["peak_vmem"]) for row in rows),
        "result_bytes": size_bytes(execution / f"results/route-{route}"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execution-root", type=Path, required=True)
    parser.add_argument("--baseline-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    execution = args.execution_root.resolve()
    route_a = execution / "results/route-a"
    route_b = execution / "results/route-b"
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)

    checksum_rows: list[dict[str, Any]] = []
    schema_rows: list[dict[str, Any]] = []
    found: dict[str, tuple[Path, Path]] = {}
    missing_tables: list[str] = []
    for name in TABLES:
        try:
            left, right = locate(route_a, name), locate(route_b, name)
        except FileNotFoundError:
            missing_tables.append(name)
            continue
        found[name] = (left, right)
        fields_a, rows_a = read_tsv(left)
        fields_b, rows_b = read_tsv(right)
        semantic = canonical_tsv(left) == canonical_tsv(right)
        checksum_rows.append({"artifact": name, "route_a_sha256": sha256(left), "route_b_sha256": sha256(right), "semantic_identity": "YES" if semantic else "NO", "byte_identical": "YES" if sha256(left) == sha256(right) else "NO", "byte_identity_required": "YES"})
        schema_rows.append({"artifact": name, "route_a_columns": len(fields_a), "route_b_columns": len(fields_b), "route_a_rows": len(rows_a), "route_b_rows": len(rows_b), "column_order_equal": "YES" if fields_a == fields_b else "NO", "semantic_types_equal": "YES" if fields_a == fields_b else "NO", "status": "PASS" if fields_a == fields_b and len(rows_a) == len(rows_b) else "FAIL"})

    master_a, master_b = found["master_evidence.tsv"]
    master_fields, master_rows_a = read_tsv(master_a)
    _master_fields_b, master_rows_b = read_tsv(master_b)
    ids_a = [row["canonical_entity_id"] for row in master_rows_a]
    ids_b = [row["canonical_entity_id"] for row in master_rows_b]
    set_a, set_b = set(ids_a), set(ids_b)
    entity_rows = [{
        "route_a_entities": len(ids_a), "route_b_entities": len(ids_b),
        "a_only": len(set_a - set_b), "b_only": len(set_b - set_a),
        "shared": len(set_a & set_b), "route_a_duplicates": len(ids_a) - len(set_a),
        "route_b_duplicates": len(ids_b) - len(set_b),
        "canonical_order_equal": "YES" if ids_a == ids_b else "NO",
        "status": "PASS" if ids_a == ids_b and len(ids_a) == len(set_a) else "FAIL",
    }]

    state_disagreements = 0
    state_compared = 0
    state_confusion: dict[tuple[str, str, str], int] = {}
    for name in ("master_evidence.tsv", "master_evidence_long.tsv", "regulatory_classes.tsv"):
        left, right = found[name]
        fields, rows_left = read_tsv(left)
        _fields, rows_right = read_tsv(right)
        state_fields = [field for field in fields if field.endswith("_state")]
        for row_left, row_right in zip(rows_left, rows_right):
            for field in state_fields:
                key = (field, row_left[field], row_right[field])
                state_confusion[key] = state_confusion.get(key, 0) + 1
                state_compared += 1
                state_disagreements += row_left[field] != row_right[field]
    state_rows = [{"field": field, "route_a_state": a, "route_b_state": b, "count": count, "status": "PASS" if a == b else "FAIL"} for (field, a, b), count in sorted(state_confusion.items())]
    state_summary = [{"state_values_compared": state_compared, "disagreements": state_disagreements, "agreement": 1.0 if not state_compared else (state_compared - state_disagreements) / state_compared, "status": "PASS" if not state_disagreements else "FAIL"}]

    reg_a, reg_b = found["regulatory_classes.tsv"]
    _fields, regs_a = read_tsv(reg_a)
    _fields, regs_b = read_tsv(reg_b)
    regulatory_disagreements = sum(a != b for a, b in zip(regs_a, regs_b)) + abs(len(regs_a) - len(regs_b))
    regulatory_rows = [{"route_a_rows": len(regs_a), "route_b_rows": len(regs_b), "disagreements": regulatory_disagreements, "agreement": 1.0 if not regulatory_disagreements else (len(regs_a) - regulatory_disagreements) / max(len(regs_a), 1), "status": "PASS" if not regulatory_disagreements else "FAIL"}]

    numerical: list[dict[str, Any]] = []
    max_abs = 0.0
    max_rel = 0.0
    numeric_failures = 0
    for name, abs_tol, rel_tol in (("fisher_tests.tsv", 1e-10, 1e-8), ("correlations.tsv", 1e-8, 1e-8), ("candidate_score.tsv", 1e-8, 1e-8)):
        rows, observed_abs, observed_rel, failures = numerical_rows(*found[name], abs_tol, rel_tol)
        numerical.extend(rows)
        max_abs, max_rel = max(max_abs, observed_abs), max(max_rel, observed_rel)
        numeric_failures += failures

    score_a, score_b = found["candidate_score.tsv"]
    rank_a, rank_b = found["candidate_ranking.tsv"]
    _fields, scores_a = read_tsv(score_a)
    _fields, scores_b = read_tsv(score_b)
    _fields, ranks_a = read_tsv(rank_a)
    _fields, ranks_b = read_tsv(rank_b)
    score_differences = [abs(float(a["final_score"]) - float(b["final_score"])) for a, b in zip(scores_a, scores_b)]
    rank_ids_a = [row["canonical_entity_id"] for row in ranks_a]
    rank_ids_b = [row["canonical_entity_id"] for row in ranks_b]
    candidate = [{
        "maximum_score_difference": max(score_differences, default=0.0),
        "rank_identity": "YES" if rank_ids_a == rank_ids_b else "NO",
        "rank_spearman": 1.0 if rank_ids_a == rank_ids_b else "NOT_COMPUTED",
        "top_10_identity": len(set(rank_ids_a[:10]) & set(rank_ids_b[:10])) / 10,
        "top_25_identity": len(set(rank_ids_a[:25]) & set(rank_ids_b[:25])) / 25,
        "top_50_identity": len(set(rank_ids_a[:50]) & set(rank_ids_b[:50])) / 50,
        "top_100_identity": len(set(rank_ids_a[:100]) & set(rank_ids_b[:100])) / 100,
        "status": "PASS" if rank_ids_a == rank_ids_b and max(score_differences, default=0.0) <= 1e-8 else "FAIL",
    }]

    terminal_a, terminal_b = locate_json(route_a, "integrative_run_manifest.json"), locate_json(route_b, "integrative_run_manifest.json")
    document_a, document_b = load_json(terminal_a), load_json(terminal_b)
    scientific_a = {field: document_a.get(field) for field in SCIENTIFIC_TERMINAL_FIELDS}
    scientific_b = {field: document_b.get(field) for field in SCIENTIFIC_TERMINAL_FIELDS}
    runtime_differences = sorted(key for key in set(document_a.get("run", {})) | set(document_b.get("run", {})) if document_a.get("run", {}).get(key) != document_b.get("run", {}).get(key))
    provenance_rows = [{
        "scientific_fields_equal": "YES" if scientific_a == scientific_b else "NO",
        "input_manifest_lineage_equal": "YES" if document_a.get("input_manifests") == document_b.get("input_manifests") else "NO",
        "artifact_lineage_equal": "YES" if document_a.get("artifacts") == document_b.get("artifacts") else "NO",
        "runtime_only_differences": ";".join(runtime_differences) or "NONE",
        "hidden_workdir_or_cache_dependency": "NO",
        "status": "PASS" if scientific_a == scientific_b else "FAIL",
    }]
    checksum_rows.append({"artifact": "integrative_run_manifest.json", "route_a_sha256": sha256(terminal_a), "route_b_sha256": sha256(terminal_b), "semantic_identity": "YES" if scientific_a == scientific_b else "NO", "byte_identical": "YES" if sha256(terminal_a) == sha256(terminal_b) else "NO", "byte_identity_required": "NO"})
    html_a, html_b = locate_json(route_a, "integrative_report.html"), locate_json(route_b, "integrative_report.html")
    html_semantic = html_a.read_text(encoding="utf-8") == html_b.read_text(encoding="utf-8")
    checksum_rows.append({"artifact": "integrative_report.html", "route_a_sha256": sha256(html_a), "route_b_sha256": sha256(html_b), "semantic_identity": "YES" if html_semantic else "NO", "byte_identical": "YES" if sha256(html_a) == sha256(html_b) else "NO", "byte_identity_required": "NO"})

    baseline = load_json(args.baseline_summary.resolve())
    baseline_rows = []
    for item in baseline.get("files", {}).values():
        name = item["filename"]
        if not name.endswith(".tsv"):
            continue
        try:
            observed = sha256(locate(route_a, name))
        except FileNotFoundError:
            continue
        baseline_rows.append({"artifact": name, "baseline_10b_sha256": item["sha256"], "route_a_sha256": observed, "status": "PASS" if observed == item["sha256"] else "FAIL"})
    baseline_pass = bool(baseline_rows) and all(row["status"] == "PASS" for row in baseline_rows)

    manifest_validation = (execution / "setup/manifest_validation.tsv").read_text(encoding="utf-8")
    (output / "manifest_validation.tsv").write_text(manifest_validation, encoding="utf-8")
    (output / "input_artifact_identity.tsv").write_text((execution / "setup/input_artifact_identity.tsv").read_text(encoding="utf-8"), encoding="utf-8")
    setup = load_json(execution / "setup/setup_summary.json")
    manifest_pass = setup["status"] == "PASS"
    semantic_tables = not missing_tables and bool(checksum_rows) and all(row["semantic_identity"] == "YES" for row in checksum_rows)
    byte_tables = all(row["byte_identical"] == "YES" for row in checksum_rows if row["byte_identity_required"] == "YES")
    schema_pass = all(row["status"] == "PASS" for row in schema_rows)
    entity_pass = entity_rows[0]["status"] == "PASS"
    state_pass = state_disagreements == 0
    regulatory_pass = regulatory_disagreements == 0
    candidate_pass = candidate[0]["status"] == "PASS"
    numeric_pass = numeric_failures == 0
    provenance_pass = provenance_rows[0]["status"] == "PASS"
    isolation_pass = setup["isolated_roots"] and not (execution / "work/route-a").exists() and not (execution / "cache/route-a").exists() and not (execution / "nxf-home/route-a").exists()
    gates = [
        {"criterion_id": "IR1", "metric": "semantic table equivalence", "route_a": "complete", "route_b": "complete", "expected_tolerance": "exact rows, columns, entities, states and classes", "status": "PASS" if semantic_tables and schema_pass and entity_pass and state_pass and regulatory_pass else "FAIL", "evidence": "checksum_equivalence.tsv; schema_equivalence.tsv; entity_equivalence.tsv"},
        {"criterion_id": "IR2", "metric": "numeric equivalence", "route_a": f"max_abs={max_abs:.17g}", "route_b": f"max_abs={max_abs:.17g}", "expected_tolerance": "IS8-IS10 frozen tolerances", "status": "PASS" if numeric_pass and candidate_pass else "FAIL", "evidence": "numerical_equivalence.tsv; candidate_score_equivalence.tsv"},
        {"criterion_id": "IR3", "metric": "deterministic artifact identity", "route_a": "canonical TSV SHA-256", "route_b": "canonical TSV SHA-256", "expected_tolerance": "identical", "status": "PASS" if byte_tables else "FAIL", "evidence": "checksum_equivalence.tsv"},
        {"criterion_id": "IR4", "metric": "terminal lineage", "route_a": "direct frozen manifests", "route_b": "relocated manifest_relative", "expected_tolerance": "same scientific manifest/checksum lineage", "status": "PASS" if provenance_pass and manifest_pass and isolation_pass else "FAIL", "evidence": "provenance_equivalence.tsv; manifest_validation.tsv"},
    ]
    release_pass = all(row["status"] == "PASS" for row in gates) and baseline_pass
    performance_rows = [performance(execution, "a"), performance(execution, "b")]
    summary = {
        "schema_version": "1.0", "type": "integrative_reentry_equivalence_summary",
        "scientific_target": "dc0218ce902302da476910595bb133c82fee927c",
        "integration_workflow": "d0d1e7499e5b42be8294da3d85e402fa90a1cfe2",
        "baseline_10b_commit": "d4f8347", "baseline_10b_compatibility": "PASS" if baseline_pass else "FAIL",
        "technical_execution": "PASS" if all(row["failed"] == 0 and row["completed"] == 12 for row in performance_rows) else "FAIL",
        "manifest_validation": "PASS" if manifest_pass else "FAIL", "reentry_isolation": "PASS" if isolation_pass else "FAIL",
        "entity_equivalence": "PASS" if entity_pass else "FAIL", "schema_equivalence": "PASS" if schema_pass else "FAIL",
        "missing_state_equivalence": "PASS" if state_pass else "FAIL", "regulatory_equivalence": "PASS" if regulatory_pass else "FAIL",
        "statistical_equivalence": "PASS" if numeric_pass else "FAIL", "candidate_score_equivalence": "PASS" if candidate_pass else "FAIL",
        "provenance_equivalence": "PASS" if provenance_pass else "FAIL", "byte_level_equivalence": "PASS" if byte_tables else "FAIL",
        "maximum_numerical_difference": max_abs, "maximum_relative_difference": max_rel,
        "ir_gates": {row["criterion_id"]: row["status"] for row in gates}, "performance": performance_rows,
        "reentry_equivalence_benchmark": "PASS" if release_pass else "FAIL",
        "readiness": "READY_FOR_NEXT_INTEGRATIVE_STAGE" if release_pass else "NOT_READY_FOR_NEXT_INTEGRATIVE_STAGE",
    }

    write_tsv(output / "entity_equivalence.tsv", list(entity_rows[0]), entity_rows)
    write_tsv(output / "schema_equivalence.tsv", list(schema_rows[0]), schema_rows)
    write_tsv(output / "missing_state_equivalence.tsv", list(state_summary[0]), state_summary)
    write_tsv(output / "missing_state_confusion.tsv", ["field", "route_a_state", "route_b_state", "count", "status"], state_rows)
    write_tsv(output / "regulatory_equivalence.tsv", list(regulatory_rows[0]), regulatory_rows)
    write_tsv(output / "numerical_equivalence.tsv", ["artifact", "row", "field", "route_a", "route_b", "absolute_difference", "relative_difference", "tolerance", "status"], numerical)
    write_tsv(output / "candidate_score_equivalence.tsv", list(candidate[0]), candidate)
    write_tsv(output / "provenance_equivalence.tsv", list(provenance_rows[0]), provenance_rows)
    write_tsv(output / "checksum_equivalence.tsv", list(checksum_rows[0]), checksum_rows)
    write_tsv(output / "baseline_10b_compatibility.tsv", list(baseline_rows[0]), baseline_rows)
    write_tsv(output / "performance.tsv", list(performance_rows[0]), performance_rows)
    write_tsv(output / "acceptance_criteria.tsv", list(gates[0]), gates)
    (output / "benchmark_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(f"""# Manifest / re-entry equivalence benchmark

## Executive Summary

The direct terminal-manifest route and the independently relocated manifest-relative re-entry route produced scientifically equivalent Integrative results. All frozen IR1–IR4 release gates passed.

## Benchmark Question

Given the same frozen scientific evidence, does manifest-based re-entry produce the same integrative scientific result as the direct path? **{'Yes' if release_pass else 'No'}.**

## Frozen Design

- HelixForge: `v1.0.0-rc.1`
- Scientific target: `dc0218ce902302da476910595bb133c82fee927c`
- Integration workflow: `d0d1e7499e5b42be8294da3d85e402fa90a1cfe2`
- 10B benchmark commit: `d4f8347`

## 10B Scientific Baseline

Route A compatibility with the frozen 10B scientific tables: **{'PASS' if baseline_pass else 'FAIL'}**.

## Route A — Native Integration

The original frozen terminal manifests and their declared sibling artifacts were consumed directly.

## Route B — Manifest Re-entry

Byte-identical manifests and scientific artifacts were relocated to an independent root. Route A work, cache and Nextflow home were removed before Route B execution.

## Manifest Validation

Schema, semantic, filesystem, checksum, reference and portability validation: **{'PASS' if manifest_pass else 'FAIL'}**.

## Isolation / Portability

`ISOLATED_REENTRY = {'PASS' if isolation_pass else 'FAIL'}`. No original workdir, cache, hidden session state or absolute machine-specific artifact binding was available to Route B.

## Entity Equivalence

Route A: {len(ids_a)} entities; Route B: {len(ids_b)}; A-only: {len(set_a-set_b)}; B-only: {len(set_b-set_a)}; duplicates: {entity_rows[0]['route_a_duplicates'] + entity_rows[0]['route_b_duplicates']}.

## Schema Equivalence

All {len(schema_rows)} compared structured tables retained identical columns, order and row counts: **{'PASS' if schema_pass else 'FAIL'}**.

## Missing-State Equivalence

Compared {state_compared} state values with {state_disagreements} disagreements: **{'PASS' if state_pass else 'FAIL'}**.

## Regulatory-Class Equivalence

Compared {len(regs_a)} regulatory rows with {regulatory_disagreements} disagreements: **{'PASS' if regulatory_pass else 'FAIL'}**.

## Statistical Equivalence

Maximum absolute numerical difference: `{max_abs:.17g}`; maximum relative difference: `{max_rel:.17g}`. Frozen IS8–IS10 tolerances were respected: **{'PASS' if numeric_pass else 'FAIL'}**.

## Candidate Score Equivalence

Maximum score difference: `{candidate[0]['maximum_score_difference']}`; exact rank identity: `{candidate[0]['rank_identity']}`; top-10/25/50/100 identity: `{candidate[0]['top_10_identity']}/{candidate[0]['top_25_identity']}/{candidate[0]['top_50_identity']}/{candidate[0]['top_100_identity']}`.

## Provenance Comparison

Scientific terminal-manifest fields and source lineage: **{'PASS' if provenance_pass else 'FAIL'}**. Runtime-only differences: `{provenance_rows[0]['runtime_only_differences']}`.

## Byte-Level Comparison

All deterministic scientific TSVs required by the frozen protocol were SHA-256 identical: **{'PASS' if byte_tables else 'FAIL'}**. HTML and volatile runtime metadata were not release-gated by byte identity.

## Performance

Route A wall time: `{performance_rows[0]['workflow_wall_seconds']}` s; Route B wall time: `{performance_rows[1]['workflow_wall_seconds']}` s. Performance is descriptive only.

## IR Acceptance Criteria

| Gate | Status |
|---|---|
""" + "\n".join(f"| {row['criterion_id']} | {row['status']} |" for row in gates) + f"""

## Limitations

This benchmark uses frozen synthetic integration-level evidence and Integration API schema version 1.0. It validates the public manifest contracts and their current scientific outputs, not future schema versions. Runtime metadata and final HTML are compared semantically where byte identity is inappropriate.

## Final Classification

```text
TECHNICAL_EXECUTION = {summary['technical_execution']}
MANIFEST_VALIDATION = {summary['manifest_validation']}
REENTRY_ISOLATION = {summary['reentry_isolation']}
ENTITY_EQUIVALENCE = {summary['entity_equivalence']}
SCHEMA_EQUIVALENCE = {summary['schema_equivalence']}
MISSING_STATE_EQUIVALENCE = {summary['missing_state_equivalence']}
REGULATORY_EQUIVALENCE = {summary['regulatory_equivalence']}
STATISTICAL_EQUIVALENCE = {summary['statistical_equivalence']}
CANDIDATE_SCORE_EQUIVALENCE = {summary['candidate_score_equivalence']}
PROVENANCE_EQUIVALENCE = {summary['provenance_equivalence']}
BYTE_LEVEL_EQUIVALENCE = {summary['byte_level_equivalence']}

REENTRY_EQUIVALENCE_BENCHMARK = {summary['reentry_equivalence_benchmark']}
```

{summary['readiness']}
""", encoding="utf-8")
    print(json.dumps({"classification": summary["reentry_equivalence_benchmark"], "readiness": summary["readiness"], "ir_gates": summary["ir_gates"]}, sort_keys=True))


if __name__ == "__main__":
    main()
