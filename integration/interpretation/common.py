from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from typing import Any

from integration.evidence.io import read_json, read_tsv, sha256, write_tsv


def number(value: Any, default: float | None = None) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(result) or math.isinf(result) else result


def integer(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def truth(value: Any) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "y"}


def format_number(value: float | None, digits: int = 8) -> str:
    return "" if value is None else f"{value:.{digits}g}"


def load_integration(directory: Path) -> tuple[dict[str, Any], dict[str, list[dict[str, str]]]]:
    root = directory.resolve()
    manifest_path = root / "integration_manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"missing integration manifest: {manifest_path}")
    manifest = read_json(manifest_path)
    if manifest.get("type") != "molecular_evidence_integration" or manifest.get("status") != "complete":
        raise ValueError("interpretation requires a complete Molecular Evidence Integration manifest")
    data: dict[str, list[dict[str, str]]] = {}
    for dataset in manifest.get("datasets", []):
        target = (root / dataset.get("path", "")).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            raise ValueError(f"integration dataset escapes or is missing: {dataset.get('path')}")
        if dataset.get("checksum", {}).get("value") != sha256(target):
            raise ValueError(f"integration dataset checksum mismatch: {target.name}")
        data[dataset["dataset_type"]] = read_tsv(target)[1]
    for required in ("master_evidence_long", "master_evidence", "peak_aggregation"):
        if required not in data:
            raise ValueError(f"integration dataset {required} is required")
    return manifest, data


def load_policy(path: Path) -> dict[str, Any]:
    policy = read_json(path)
    for field in ("interpretation_model_version", "classification_version", "candidate_score_version", "rna", "chip", "score", "statistics"):
        if field not in policy:
            raise ValueError(f"interpretation policy missing {field}")
    return policy


def load_mark_roles(path: Path) -> dict[str, dict[str, str]]:
    fields, rows = read_tsv(path)
    required = {"mark", "canonical_name", "regulatory_role", "context", "evidence_source", "notes"}
    if not required.issubset(fields):
        raise ValueError(f"mark-role catalog missing columns {sorted(required - set(fields))}")
    roles = {row["mark"]: row for row in rows}
    if len(roles) != len(rows):
        raise ValueError("mark-role catalog contains duplicate marks")
    allowed = {"ACTIVATING", "REPRESSIVE", "CONTEXT_DEPENDENT", "STRUCTURAL", "UNKNOWN"}
    if any(row["regulatory_role"] not in allowed for row in rows):
        raise ValueError("mark-role catalog contains an unsupported regulatory role")
    return roles


def load_context(path: Path | None, genes: set[str]) -> dict[str, dict[str, str]]:
    if path is None:
        return {}
    fields, rows = read_tsv(path)
    if "canonical_entity_id" not in fields:
        raise ValueError("prioritization context requires canonical_entity_id")
    result: dict[str, dict[str, str]] = {}
    for index, row in enumerate(rows, 2):
        gene = row.get("canonical_entity_id", "")
        if not gene or gene in result:
            raise ValueError(f"prioritization context row {index}: missing or duplicate canonical_entity_id")
        if gene not in genes:
            raise ValueError(f"prioritization context row {index}: unknown canonical entity {gene}")
        result[gene] = row
    return result


def significant(row: dict[str, str], policy: dict[str, Any], assay: str) -> bool:
    effect = number(row.get("effect"))
    padj = number(row.get("padj"))
    settings = policy[assay]
    return effect is not None and padj is not None and abs(effect) >= float(settings["absolute_log2fc_threshold"]) and padj <= float(settings["padj_threshold"])


def bh_adjust(values: list[float]) -> list[float]:
    if not values:
        return []
    adjusted = [1.0] * len(values)
    previous = 1.0
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    for rank, (index, value) in reversed(list(enumerate(ordered, 1))):
        previous = min(previous, value * len(values) / rank)
        adjusted[index] = max(0.0, min(1.0, previous))
    return adjusted


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    dx = [value - statistics.mean(xs) for value in xs]
    dy = [value - statistics.mean(ys) for value in ys]
    ssx, ssy = sum(value * value for value in dx), sum(value * value for value in dy)
    if ssx <= 0 or ssy <= 0:
        return None
    return sum(x * y for x, y in zip(dx, dy)) / math.sqrt(ssx * ssy)


def ranks(values: list[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    output = [0.0] * len(values)
    index = 0
    while index < len(ordered):
        end = index
        while end + 1 < len(ordered) and ordered[end + 1][1] == ordered[index][1]:
            end += 1
        rank = (index + end + 2) / 2.0
        for position in range(index, end + 1):
            output[ordered[position][0]] = rank
        index = end + 1
    return output


def spearman(xs: list[float], ys: list[float]) -> float | None:
    return None if len(xs) != len(ys) or len(xs) < 2 else pearson(ranks(xs), ranks(ys))


def write_manifest(path: Path, document: dict[str, Any]) -> None:
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def dataset(output: Path, dataset_type: str, filename: str, fields: list[str], rows: list[dict[str, Any]]) -> dict[str, Any]:
    target = output / filename
    count = write_tsv(target, fields, rows)
    return {"dataset_type": dataset_type, "path": filename, "records": count, "checksum": {"algorithm": "sha256", "value": sha256(target)}}
