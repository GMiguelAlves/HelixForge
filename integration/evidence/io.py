from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable


NULLS = {"", "na", "nan", "null", "none", "."}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_tsv(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> int:
    materialized = list(rows)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        for row in materialized:
            writer.writerow({key: "" if row.get(key) is None else row.get(key) for key in fields})
    return len(materialized)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def optional_number(value: Any) -> str:
    text = str(value if value is not None else "").strip()
    if text.lower() in NULLS:
        return ""
    number = float(text)
    if not math.isfinite(number):
        return ""
    return text


def first_column(fields: list[str], choices: Iterable[str]) -> str | None:
    exact = {field: field for field in fields}
    folded = {field.casefold(): field for field in fields}
    for choice in choices:
        if choice in exact:
            return exact[choice]
        if choice.casefold() in folded:
            return folded[choice.casefold()]
    return None


def safe_id(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value).strip("_")


def load_bindings(path: Path, declared: list[Path]) -> dict[str, Path]:
    document = read_json(path)
    entries = document.get("bindings", [])
    allowed = {item.resolve() for item in declared}
    allowed_roots = [item.resolve() for item in declared if item.is_dir()]
    bindings: dict[str, Path] = {}
    for entry in entries:
        artifact_id = entry.get("artifact_id", "")
        if "declared_name" in entry:
            declared_name = str(entry["declared_name"])
            matches = [item for item in declared if item.name == declared_name]
            if len(matches) != 1:
                raise ValueError(
                    f"binding {artifact_id} declared_name {declared_name!r} "
                    f"matched {len(matches)} declared artifacts"
                )
            candidate = matches[0]
        elif "declared_index" in entry:
            index = int(entry["declared_index"])
            if index < 0 or index >= len(declared):
                raise ValueError(f"binding {artifact_id} has invalid declared_index {index}")
            candidate = declared[index]
            relative = entry.get("relative_path")
            if relative:
                candidate = candidate / relative
        else:
            candidate = Path(entry.get("path", ""))
            if not candidate.is_absolute():
                candidate = (path.parent / candidate).resolve()
                if not candidate.exists():
                    candidate = (Path.cwd() / entry.get("path", "")).resolve()
        resolved = candidate.resolve()
        if not artifact_id or artifact_id in bindings:
            raise ValueError(f"invalid or duplicate artifact binding: {artifact_id!r}")
        if resolved not in allowed and not any(resolved.is_relative_to(root) for root in allowed_roots):
            raise ValueError(f"binding {artifact_id} is not a declared staged artifact: {resolved}")
        if not resolved.is_file():
            raise ValueError(f"binding {artifact_id} is not a file: {resolved}")
        bindings[artifact_id] = resolved
    return bindings
