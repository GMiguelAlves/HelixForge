#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from integration_contract import compatibility_errors, filesystem_errors, load_json, schema_contract_errors, semantic_errors


def jsonschema_errors(document: dict, schema_root: Path) -> list[str]:
    try:
        from jsonschema import Draft202012Validator
        from referencing import Registry, Resource
    except ImportError as error:
        return [f"JSON Schema validation requires jsonschema>=4.23 (the module environment pins it): {error}"]
    resources = []
    for path in schema_root.rglob("*.json"):
        value = load_json(path)
        if value.get("$id"):
            resources.append((value["$id"], Resource.from_contents(value)))
    registry = Registry().with_resources(resources)
    schema = load_json(schema_root / "integration-api.schema.json")
    validator = Draft202012Validator(schema, registry=registry, format_checker=Draft202012Validator.FORMAT_CHECKER)
    return [error.message for error in sorted(validator.iter_errors(document), key=lambda item: list(item.path))]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--schema-root", type=Path, default=Path(__file__).resolve().parents[1] / "schemas" / "integration")
    parser.add_argument("--layer", choices=("schema", "semantic", "filesystem", "all"), default="all")
    parser.add_argument("--producer-base", action="append", default=[], metavar="ID=PATH")
    parser.add_argument("--compatible-with", type=Path)
    args = parser.parse_args()
    document = load_json(args.manifest)
    errors: list[str] = []
    if args.layer in {"schema", "all"}:
        errors.extend(jsonschema_errors(document, args.schema_root))
    if args.layer in {"semantic", "all"}:
        errors.extend(schema_contract_errors(document))
        errors.extend(semantic_errors(document))
    if args.layer in {"filesystem", "all"}:
        bases = {}
        for entry in args.producer_base:
            if "=" not in entry:
                errors.append(f"invalid --producer-base {entry!r}; expected ID=PATH")
                continue
            identifier, value = entry.split("=", 1)
            bases[identifier] = Path(value)
        errors.extend(filesystem_errors(document, args.manifest, bases))
    if args.compatible_with:
        errors.extend(compatibility_errors(document, load_json(args.compatible_with)))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(f"valid Integration API manifest: {document.get('id')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
